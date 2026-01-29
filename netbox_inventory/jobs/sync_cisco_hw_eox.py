import json
from datetime import datetime

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import MultipleObjectsReturned

from core.choices import JobIntervalChoices
from dcim.models import Device, DeviceType, Manufacturer, Module, ModuleType
from netbox.jobs import JobRunner, system_job

from netbox_inventory.models import hardware

WEEKLY_MINUTES = getattr(JobIntervalChoices, "INTERVAL_WEEKLY", 10080)


@system_job(interval=WEEKLY_MINUTES)
class SyncCiscoHwEoXDates(JobRunner):
    class Meta:
        name = "Netbox Inventory - Sync Cisco HW EoX Dates"
        description = "Sync HW EoX Date from Cisco Services API (CSAPI)"

    LIFECYCLE_ONLY_ACTIVE_PIDS = True
    API_IS_SOURCE_OF_TRUTH = True
    USE_EOS_FOR_MISSING_DATA = True

    # ---------- small generic helpers ----------

    @staticmethod
    def _as_bool(value, default=False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _get_nested(data, path, default=None):
        cur = data
        try:
            for key in path:
                cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return default
        return cur

    @staticmethod
    def _parse_date(date_str: str):
        if not date_str:
            return None
        return datetime.strptime(date_str, "%Y-%m-%d").date()

    def _set_if_changed(self, obj, field_name: str, new_value) -> bool:
        """
        Set obj.<field_name> = new_value if different. Returns True if changed.
        """
        if getattr(obj, field_name) != new_value:
            setattr(obj, field_name, new_value)
            return True
        return False

    # ---------- domain helpers ----------

    def api_logon(self):
        plugin_settings = settings.PLUGINS_CONFIG.get("netbox_inventory", {}) or {}

        client_id = plugin_settings.get("cisco_support_api_client_id", "")
        client_secret = plugin_settings.get("cisco_support_api_client_secret", "")

        self.LIFECYCLE_ONLY_ACTIVE_PIDS = self._as_bool(plugin_settings.get("lifecycle_only_active_pids", True), True)
        self.API_IS_SOURCE_OF_TRUTH = self._as_bool(plugin_settings.get("api_is_source_of_truth", True), True)
        self.USE_EOS_FOR_MISSING_DATA = self._as_bool(plugin_settings.get("use_eos_for_missing_data", True), True)

        if not client_id or not client_secret:
            self.logger.error("Cisco API client credentials are not configured in PLUGINS_CONFIG.")
            return None

        token_url = "https://id.cisco.com/oauth2/default/v1/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        r = requests.post(token_url, data=data, timeout=30)
        if r.status_code != 200:
            self.logger.error(f"Token request failed ({r.status_code}): {r.text}")
            return None

        tokens = r.json()
        access_token = tokens.get("access_token")
        if not access_token:
            self.logger.error(f"Token response missing access_token: {tokens}")
            return None

        return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    def _resolve_hw_target(self, pid: str, hardware_type: str):
        """
        Returns tuple: (hw_obj, hw_count, content_type) or (None, 0, None) if not resolvable.
        """
        if hardware_type == "devicetype":
            content_type = ContentType.objects.get(app_label="dcim", model="devicetype")
            try:
                hw_obj = DeviceType.objects.get(part_number=pid)
            except MultipleObjectsReturned:
                self.logger.warning(f"Multiple DeviceType objects exist with Part Number {pid}")
                return None, 0, None
            except DeviceType.DoesNotExist:
                self.logger.warning(f"No DeviceType found for Part Number {pid}")
                return None, 0, None

            hw_count = Device.objects.filter(device_type=hw_obj).count()
            return hw_obj, hw_count, content_type

        if hardware_type == "moduletype":
            content_type = ContentType.objects.get(app_label="dcim", model="moduletype")
            try:
                hw_obj = ModuleType.objects.get(part_number=pid)
            except MultipleObjectsReturned:
                self.logger.warning(f"Multiple ModuleType objects exist with Part Number {pid}")
                return None, 0, None
            except ModuleType.DoesNotExist:
                self.logger.warning(f"No ModuleType found for Part Number {pid}")
                return None, 0, None

            hw_count = Module.objects.filter(module_type=hw_obj).count()
            return hw_obj, hw_count, content_type

        self.logger.warning("Invalid hardware_type argument defined.")
        return None, 0, None

    def _get_or_create_lifecycle(self, pid: str, hw_obj, hw_count: int, content_type):
        """
        Returns HardwareLifecycle instance or None if we should skip (or deleted).
        """
        try:
            hw_lifecycle = hardware.HardwareLifecycle.objects.get(
                assigned_object_id=hw_obj.id,
                assigned_object_type_id=content_type.id,
            )
            self.logger.info(f"{pid} - existing lifecycle record (ID:{hw_lifecycle.id})")

            if hw_count == 0 and self.LIFECYCLE_ONLY_ACTIVE_PIDS:
                self.logger.info(f"{pid} - no active HW; deleting lifecycle record (only tracking active PIDs)")
                hw_lifecycle.delete()
                return None

            return hw_lifecycle

        except hardware.HardwareLifecycle.DoesNotExist:
            if hw_count == 0 and self.LIFECYCLE_ONLY_ACTIVE_PIDS:
                self.logger.info(f"{pid} - no active HW; not creating lifecycle record (only tracking active PIDs)")
                return None

            self.logger.info(f"{pid} - lifecycle record will be created")
            return hardware.HardwareLifecycle(
                assigned_object_id=hw_obj.id,
                assigned_object_type_id=content_type.id,
            )

    def _apply_eox_fields(self, pid: str, hw_lifecycle, eox_data) -> tuple[bool, bool, bool]:
        """
        Applies all supported EOX fields. Returns:
        (value_changed, end_of_sale_defined, end_of_support_defined)
        """
        # map: (field on lifecycle, path in Cisco JSON, value_transform, "missing log msg")
        date_fields = [
            ("announcement_date", ["EOXRecord", 0, "EOXExternalAnnouncementDate", "value"], self._parse_date, "announcement_date"),
            ("end_of_sale", ["EOXRecord", 0, "EndOfSaleDate", "value"], self._parse_date, "end_of_sale_date"),
            ("end_of_maintenance", ["EOXRecord", 0, "EndOfSWMaintenanceReleases", "value"], self._parse_date, "end_of_sw_maintenance_releases"),
            ("end_of_security", ["EOXRecord", 0, "EndOfSecurityVulSupportDate", "value"], self._parse_date, "end_of_security_vul_support_date"),
            ("last_contract_renewal", ["EOXRecord", 0, "EndOfServiceContractRenewal", "value"], self._parse_date, "end_of_service_contract_renewal"),
            ("last_contract_attach", ["EOXRecord", 0, "EndOfSvcAttachDate", "value"], self._parse_date, "end_of_service_contract_attach"),
            ("end_of_support", ["EOXRecord", 0, "LastDateOfSupport", "value"], self._parse_date, "last_date_of_support"),
        ]

        value_changed = False
        end_of_sale_defined = False
        end_of_support_defined = False

        for field_name, path, transform, log_label in date_fields:
            raw = self._get_nested(eox_data, path)
            if not raw:
                self.logger.info(f"{pid} - has no {log_label}")
                continue

            new_value = transform(raw)
            if new_value is None:
                self.logger.info(f"{pid} - has no {log_label}")
                continue

            if self._set_if_changed(hw_lifecycle, field_name, new_value):
                value_changed = True

            if field_name == "end_of_sale":
                end_of_sale_defined = True
            elif field_name == "end_of_support":
                end_of_support_defined = True

        # non-date field: bulletin URL
        notice_url = self._get_nested(eox_data, ["EOXRecord", 0, "LinkToProductBulletinURL"])
        if notice_url:
            if self._set_if_changed(hw_lifecycle, "notice_url", notice_url):
                value_changed = True
        else:
            self.logger.info(f"{pid} - has no product bulletin url")

        return value_changed, end_of_sale_defined, end_of_support_defined

    def _apply_missing_date_fallbacks(self, pid: str, hw_lifecycle):
        if not self.USE_EOS_FOR_MISSING_DATA:
            return

        if hw_lifecycle.end_of_support is None:
            return

        if hw_lifecycle.end_of_security is None:
            self.logger.info(f"{pid} - no end_of_security; using end_of_support instead")
            hw_lifecycle.end_of_security = hw_lifecycle.end_of_support

        if hw_lifecycle.end_of_maintenance is None:
            self.logger.info(f"{pid} - no end_of_maintenance; using end_of_support instead")
            hw_lifecycle.end_of_maintenance = hw_lifecycle.end_of_support

    # ---------- refactored method Ruff was mad about ----------

    def update_lifecycle_data(self, pid, hardware_type, eox_data):
        self.logger.info(f"{pid} - {hardware_type}")

        hw_obj, hw_count, content_type = self._resolve_hw_target(pid, hardware_type)
        if not hw_obj:
            return

        hw_lifecycle = self._get_or_create_lifecycle(pid, hw_obj, hw_count, content_type)
        if hw_lifecycle is None:
            return

        value_changed, eos_defined, eol_defined = self._apply_eox_fields(pid, hw_lifecycle, eox_data)

        if value_changed and eos_defined and eol_defined:
            self._apply_missing_date_fallbacks(pid, hw_lifecycle)
            self.logger.info(f"{pid} - saving lifecycle record")
            hw_lifecycle.save()

    # ---------- rest of your class unchanged ----------

    def get_product_ids(self, manufacturer):
        results = {}

        try:
            manufacturer_results = Manufacturer.objects.get(name=manufacturer)
        except Manufacturer.DoesNotExist:
            self.logger.error(f'Manufacturer "{manufacturer}" does not exist')
            return results

        self.logger.info(f'Found manufacturer "{manufacturer_results}"')

        for devicetype in DeviceType.objects.filter(manufacturer=manufacturer_results):
            if not devicetype.part_number:
                self.logger.warning(f'Found device type "{devicetype}" WITHOUT Part Number - SKIPPING')
                continue

            if self.LIFECYCLE_ONLY_ACTIVE_PIDS:
                if devicetype.instances.count() > 0:
                    results[devicetype.part_number] = "devicetype"
                else:
                    self.logger.info(f'No Instances of "{devicetype}" - only tracking active PIDs; skipping')
            else:
                results[devicetype.part_number] = "devicetype"

        for moduletype in ModuleType.objects.filter(manufacturer=manufacturer_results):
            if not moduletype.part_number:
                self.logger.warning(f'Found module type "{moduletype}" WITHOUT Part Number - SKIPPING')
                continue

            if self.LIFECYCLE_ONLY_ACTIVE_PIDS:
                if moduletype.instances.count() > 0:
                    results[moduletype.part_number] = "moduletype"
                else:
                    self.logger.info(f'No Instances of "{moduletype}" - only tracking active PIDs; skipping')
            else:
                results[moduletype.part_number] = "moduletype"

        return results

    def run(self, *args, **kwargs):
        manufacturer = "Cisco"

        headers = self.api_logon()
        if not headers:
            return

        product_ids = self.get_product_ids(manufacturer)
        self.logger.info("Querying API for PIDs: " + ", ".join(product_ids.keys()))

        for pid, hw_type in product_ids.items():
            url = f"https://apix.cisco.com/supporttools/eox/rest/5/EOXByProductID/1/{pid}?responseencoding=json"
            self.logger.info(f"Calling {url}")

            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200:
                self.update_lifecycle_data(pid, hw_type, r.json())
            else:
                self.logger.error(f"API Error ({r.status_code}): {r.text}")

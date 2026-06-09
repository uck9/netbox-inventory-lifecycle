from django.utils.translation import gettext_lazy as _

from utilities.choices import ChoiceSet

#
# Assets
#


class AssetStatusChoices(ChoiceSet):
    key = 'Asset.status'

    CHOICES = [
        ('stored', 'Stored', 'green'),
        ('used', 'Used', 'blue'),
        ('in-transit', 'In Transit', 'cyan'),
        ('disposed', 'Disposed', 'red'),
        ('retired', 'Retired', 'gray'),
    ]


class AssetAllocationStatusChoices(ChoiceSet):
    key = 'Asset.allocation'

    UNALLOCATED = 'unallocated'
    ALLOCATED = 'allocated'
    CONSUMED = 'consumed'

    CHOICES = [
        (UNALLOCATED, 'Unallocated', 'yellow'),
        (ALLOCATED, 'Allocated', 'green'),
        (CONSUMED, 'Consumed', 'blue'),
    ]

class HardwareKindChoices(ChoiceSet):
    CHOICES = [
        ('device', 'Device'),
        ('module', 'Module'),
        ('inventoryitem', 'Inventory Item'),
        ('rack', 'Rack'),
    ]


#
# Purchases
#


class PurchaseStatusChoices(ChoiceSet):
    key = 'Purchase.status'

    CHOICES = [
        ('open', 'Open', 'cyan'),
        ('partial', 'Partial', 'blue'),
        ('closed', 'Closed', 'green'),
    ]

#
# Contract Types
#

class ContractTypeChoices(ChoiceSet):
    key = 'Contract.contract_type'

    CHOICES = [
        ('support-ea', 'Support - Enterprise Agreement', 'blue'),
        ('support-alc', 'Support - À la carte', 'red'),
        ('warranty', 'Warranty', 'blue'),
        ('other', 'Other', 'gray'),
    ]


class ContractStatusChoices(ChoiceSet):
    key = 'Contract.status'

    CHOICES = [
        ('draft', 'Draft', 'gray'),
        ('active', 'Active', 'green'),
        ('expired', 'Expired', 'red'),
        ('renewed', 'Renewed', 'orange'),
        ('cancelled', 'Cancelled', 'red'),
    ]




#
# Disposals
#


class AssetDisposalReasonChoices(ChoiceSet):
    key = 'AssetDisposal.reason'

    SCRAPPED = 'scrapped'
    SOLD = 'sold'
    LOST= 'lost'
    RETURNED_TO_VENDOR = 'returned_to_vendor'
    OTHER = 'other'

    CHOICES = [
        (SCRAPPED, 'Scrapped', 'red'),
        (SOLD, 'Sold', 'green'),
        (LOST, 'Lost', 'orange'),
        (RETURNED_TO_VENDOR, 'Returned to Vendor', 'blue'),
        (OTHER, 'Other', 'gray'),
    ]


#
# Asset Support Source
#
class AssetSupportSourceChoices(ChoiceSet):
    key = 'Asset.support_source'

    COMPUTED = 'computed'
    MANUAL = 'manual'
    IMPORT = 'imported'
    API = 'api'

    CHOICES = [
        (COMPUTED, 'Computed', 'blue'),
        (MANUAL, 'Manual', 'green'),
        (IMPORT, 'Imported', 'purple'),
        (API, 'API', 'cyan'),
    ]
#
# Asset Support Status
#
class AssetSupportStateChoices(ChoiceSet):
    key = 'Asset.support_state'

    COVERED = 'covered'
    UNCOVERED = 'uncovered'
    EXCLUDED = 'excluded'
    UNKNOWN = 'unknown'
    DISPOSED = 'disposed'

    CHOICES = [
        (COVERED, 'Covered', 'green'),
        (UNCOVERED, 'Uncovered', 'red'),
        (EXCLUDED, 'Excluded', 'orange'),
        (UNKNOWN, 'Unknown', 'gray'),
        (DISPOSED, 'Disposed', 'dark'),
    ]

#
# Asset Support Reason
#
class AssetSupportReasonChoices(ChoiceSet):
    key = 'Asset.support_reason'

    # Covered detail
    COVERED_BY_CONTRACT = 'covered_contract'
    COVERED_BY_WARRANTY = 'covered_warranty'

    # Operational Gaps (fixable)
    CONTRACT_MISSING = "contract_missing"
    CONTRACT_EXPIRED = "contract_expired"
    COVERAGE_PENDING = "coverage_pending"
    DATA_MISSING = "data_missing"

    # Intentional Exclusions
    LAB = 'lab'
    SPARE = 'spare'
    DECOMMISSION_PLANNED = 'decommission_planned'

    # Structural (not fixable)
    PAST_END_OF_SUPPORT = 'past_end_of_support'
    VENDOR_UNSUPPORTED = 'vendor_unsupported'

    CHOICES = [
        (COVERED_BY_CONTRACT, _("Covered by contract"), "green"),
        (COVERED_BY_WARRANTY, _("Covered by warranty"), "green"),

        (CONTRACT_MISSING, _("Contract missing"), "orange"),
        (CONTRACT_EXPIRED, _("Contract expired"), "orange"),
        (COVERAGE_PENDING, _("Coverage pending"), "cyan"),
        (DATA_MISSING, _("Data missing"), "gray"),

        (VENDOR_UNSUPPORTED, _("Vendor unsupported"), "purple"),
        (PAST_END_OF_SUPPORT, _("Past end of support"), "purple"),

        (LAB, _("Lab"), "blue"),
        (SPARE, _("Spare"), "blue"),
        (DECOMMISSION_PLANNED, _("Decommission planned"), "blue"),
    ]


#
# Asset Warranty Type
#
class AssetWarrantyTypeChoices(ChoiceSet):
    key = 'Asset.warranty_type'

    WARR_1YR_LTD_HW = 'WARR-1YR-LTD-HW'
    WARR_ELTD_LIFE_HW = 'WARR-ELTD-LIFE-HW'
    WARR_LTD_LIFE_HW = 'WARR-LTD-LIFE-HW'
    OTHER = 'other'

    CHOICES = [
        (WARR_1YR_LTD_HW, 'Cisco - WARR-1YR-LTD-HW', 'blue'),
        (WARR_ELTD_LIFE_HW, 'Cisco - WARR-ELTD-LIFE-HW', 'green'),
        (WARR_LTD_LIFE_HW, 'Cisco - WARR-LTD-LIFE-HW', 'cyan'),
        (OTHER, 'Other', 'gray'),
    ]

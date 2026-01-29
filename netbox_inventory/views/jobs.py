from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect
from django.urls import reverse

from netbox.views import generic

from ..jobs.sync_cisco_hw_eox import SyncCiscoHwEoXDates  # your JobRunner subclass


@permission_required("netbox_inventory.change_hardwarelifecycle")  # pick the right perm
def run_cisco_eox_sync(request):
    # Enqueue an immediate run (does not affect the weekly schedule)
    SyncCiscoHwEoXDates.enqueue()  # JobRunner has enqueue() :contentReference[oaicite:1]{index=1}

    messages.success(request, "Queued Cisco HW EoX sync job.")
    return redirect(request.META.get("HTTP_REFERER", "/"))

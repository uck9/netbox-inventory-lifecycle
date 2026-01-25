from netbox.views import generic

from ..filtersets import LicenseSKUFilterSet
from ..forms import LicenseSKUForm
from ..forms.filters import LicenseSKUFilterForm
from ..models import LicenseSKU
from ..tables import LicenseSKUTable

__all__ = (
    "LicenseSKUListView",
    "LicenseSKUView",
    "LicenseSKUEditView",
    "LicenseSKUDeleteView",
)

class LicenseSKUListView(generic.ObjectListView):
    queryset = LicenseSKU.objects.all()
    filterset = LicenseSKUFilterSet
    filterset_form = LicenseSKUFilterForm
    table = LicenseSKUTable

class LicenseSKUView(generic.ObjectView):
    queryset = LicenseSKU.objects.all()

class LicenseSKUEditView(generic.ObjectEditView):
    queryset = LicenseSKU.objects.all()
    form = LicenseSKUForm

class LicenseSKUDeleteView(generic.ObjectDeleteView):
    queryset = LicenseSKU.objects.all()

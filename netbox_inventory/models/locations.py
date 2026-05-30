from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel


__all__ = ('InstalledAtLocation',)


class InstalledAtLocation(PrimaryModel):
    """
    A vendor-maintained record of where assets are physically installed.
    Created per manufacturer; one or more may map to the same NetBox site.
    """

    manufacturer = models.ForeignKey(
        to='dcim.Manufacturer',
        on_delete=models.PROTECT,
        related_name='installed_at_locations',
        verbose_name='Manufacturer',
    )
    vendor_site_id = models.CharField(
        max_length=100,
        verbose_name='Vendor Site ID',
        help_text='The vendor\'s own identifier for this installed location',
    )
    address = models.CharField(
        max_length=200,
        verbose_name='Street Address',
    )
    city = models.CharField(
        max_length=100,
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='State / Region',
    )
    country = models.CharField(
        max_length=100,
    )
    postcode = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Postcode / ZIP',
    )
    sites = models.ManyToManyField(
        to='dcim.Site',
        related_name='installed_at_locations',
        blank=True,
        help_text=(
            'NetBox sites this vendor location corresponds to. '
            'Used to detect address mismatches on assets. '
            'One vendor address can span multiple NetBox sites.'
        ),
    )

    clone_fields = ('manufacturer', 'country', 'state', 'city')
    prerequisite_models = ('dcim.Manufacturer',)

    class Meta:
        ordering = ('manufacturer', 'vendor_site_id')
        constraints = (
            models.UniqueConstraint(
                fields=('manufacturer', 'vendor_site_id'),
                name='%(app_label)s_%(class)s_unique_manufacturer_vendor_site_id',
                violation_error_message='An installed-at location with this vendor site ID already exists for this manufacturer.',
            ),
        )
        verbose_name = 'Installed-At Location'
        verbose_name_plural = 'Installed-At Locations'

    def __str__(self):
        return f'{self.vendor_site_id} – {self.full_address}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:installedatlocation', args=[self.pk])

    @property
    def full_address(self):
        parts = [self.address, self.city]
        if self.state:
            parts.append(self.state)
        if self.postcode:
            parts.append(self.postcode)
        parts.append(self.country)
        return ', '.join(p for p in parts if p)

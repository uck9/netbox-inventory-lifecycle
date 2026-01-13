from django.db import models

from netbox.models.features import ContactsMixin

from ..choices import PurchaseStatusChoices
from .mixins import NamedModel


class Supplier(NamedModel, ContactsMixin):
    """
    Supplier is a legal entity that sold some assets that we keep track of.
    This can be the same entity as Manufacturer or a separate one. However
    netbox_inventory keeps track of Suppliers separate from Manufacturers.
    """

    slug = models.SlugField(
        max_length=100,
        unique=True,
    )

    clone_fields = ['description', 'comments']


class Purchase(NamedModel):
    """
    Represents a purchase of a set of Assets from a Supplier.
    """

    name = models.CharField(
        max_length=100,
        help_text='Name of Purchase'
    )
    purchase_requisition = models.CharField(
        max_length=100,
        help_text='Purchase Requisition',
        blank=True,
        null=True
    )
    purchase_order = models.CharField(
        max_length=100,
        help_text='Purchase Order',
        blank=True,
        null=True
    )
    internal_reference = models.CharField(
        max_length=100,
        help_text='Internal reference ID for this purchase',
        blank=True,
        null=True
    )
    supplier = models.ForeignKey(
        help_text='Legal entity this purchase was made from',
        to='netbox_inventory.Supplier',
        on_delete=models.PROTECT,
        related_name='purchases',
        blank=False,
        null=False,
    )
    supplier_reference = models.CharField(
        max_length=100,
        help_text='Supplier order, quote, or external reference ID',
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=30,
        choices=PurchaseStatusChoices,
        help_text='Status of purchase',
    )
    date = models.DateField(
        help_text='Date when this purchase was made',
        blank=True,
        null=True,
    )

    clone_fields = ['supplier', 'date', 'status', 'description', 'comments']

    class Meta:
        ordering = ['supplier', 'name']
        unique_together = (('supplier', 'name'),)

    def get_status_color(self):
        return PurchaseStatusChoices.colors.get(self.status)

    def __str__(self):
        return f'{self.supplier} {self.name}'


class Order(NamedModel):
    """
    Order is a stage in Purchase. Purchase can have multiple orders.
    In each order one or more Assets were received.
    """

    name = models.CharField(max_length=100)
    purchase = models.ForeignKey(
        help_text='Purchase that this order is part of',
        to='netbox_inventory.Purchase',
        on_delete=models.PROTECT,
        related_name='orders',
        blank=False,
        null=False,
    )
    manufacturer = models.ForeignKey(
        to='dcim.Manufacturer',
        on_delete=models.CASCADE,
        related_name='order_manufacturer',
    )

    clone_fields = ['purchase', 'manufacturer', 'description', 'comments']

    class Meta:
        ordering = ['purchase', 'name']
        unique_together = (('purchase', 'name'),)
        verbose_name = 'order'
        verbose_name_plural = 'orders'

    def __str__(self):
        return f'{self.purchase} {self.name}'

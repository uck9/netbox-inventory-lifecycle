from utilities.choices import ChoiceSet

#
# Assets
#


class AssetStatusChoices(ChoiceSet):
    key = 'Asset.status'

    CHOICES = [
        ('stored', 'Stored', 'green'),
        ('used', 'Used', 'blue'),
        ('retired', 'Retired', 'gray'),
    ]


class HardwareKindChoices(ChoiceSet):
    CHOICES = [
        ('device', 'Device'),
        ('module', 'Module'),
        ('inventoryitem', 'Inventory Item'),
        ('rack', 'Rack'),
    ]


#
# Deliveries
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
        ('alc', 'Support - A la carte', 'red'),
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
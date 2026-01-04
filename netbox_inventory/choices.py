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
        ('support-alc', 'Support - A la carte', 'red'),
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


class ProgramCoverageStatusChoices(ChoiceSet):
    key = "ProgramCoverage.status"

    PLANNED = 'planned'
    ACTIVE = 'active'
    EXCLUDED = 'excluded'
    TERMINATED = 'terminated'

    CHOICES = [
        (PLANNED, 'Planned', 'blue'),
        (ACTIVE, 'Active', 'green'),
        (EXCLUDED, 'Excluded', 'gray'),
        (TERMINATED, 'Terminated', 'red'),
    ]


class ProgramEligibilityChoices(ChoiceSet):
    key = "ProgramCoverage.eligibility"

    UNKNOWN = 'unknown'
    ELIGIBLE = 'eligible'
    INELIGIBLE = 'ineligible'

    CHOICES = [
        (UNKNOWN, "Unknown", "blue"),
        (ELIGIBLE, "Eligible", "green"),
        (INELIGIBLE, "Ineligible", "red"),
    ]

class ProgramCoverageSourceChoices(ChoiceSet):
    key = "AssetProgramCoverage.source"

    MANUAL = 'manual'
    SYNC = 'sync'
    IMPORT = 'import'

    CHOICES = [
        (MANUAL, "Manual", "blue"),
        (SYNC, "Sync", "cyan"),
        (IMPORT, "Import", "purple"),
    ]

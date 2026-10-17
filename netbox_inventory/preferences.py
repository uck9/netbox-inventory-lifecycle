from django.utils.translation import gettext_lazy as _

from users.preferences import UserPreference

preferences = {
    'include_disposed_assets': UserPreference(
        label=_('Include disposed assets'),
        choices=(
            ('', _('Plugin default')),
            ('true', _('Yes')),
            ('false', _('No')),
        ),
        description=_(
            'Show disposed assets in the inventory asset list by default. '
            'The list filter can still override this per view.'
        ),
    ),
}

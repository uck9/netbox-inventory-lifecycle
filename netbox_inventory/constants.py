from django.db.models import Q

AUDITFLOW_OBJECT_TYPE_CHOICES = Q(
    app_label='dcim',
    model__in=(
        'site',
        'location',
        'rack',
    ),
)

STATUS_PLANNED = "planned"
STATUS_ACTIVE = "active"
STATUS_EXCLUDED = "excluded"
STATUS_TERMINATED = "terminated"

ELIG_UNKNOWN = "unknown"
ELIG_ELIGIBLE = "eligible"
ELIG_INELIGIBLE = "ineligible"

# Allowed (status -> eligibility set)
ALLOWED_MATRIX = {
    STATUS_PLANNED: {ELIG_ELIGIBLE, ELIG_UNKNOWN},
    STATUS_ACTIVE: {ELIG_ELIGIBLE},
    STATUS_EXCLUDED: {ELIG_ELIGIBLE, ELIG_UNKNOWN},
    STATUS_TERMINATED: {ELIG_INELIGIBLE},
}

# Forced values (status -> eligibility)
FORCE_ELIGIBILITY = {
    STATUS_TERMINATED: ELIG_INELIGIBLE,
    STATUS_ACTIVE: ELIG_ELIGIBLE,
}
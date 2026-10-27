from apps.accounts.policies import require


def require_preview_read(user):
    # Mixed/unknown-department sources need the explicit institutional grant.
    require(user,"imports.results.view")


def require_preview_create(user):
    require_preview_read(user)
    require(user,"imports.preview")

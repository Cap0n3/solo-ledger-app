from typing import cast

from django.http import HttpRequest

from .models import Activity
from .selectors import activity_current
from .types import CURRENT_ACTIVITY_SESSION_KEY, AuthenticatedHttpRequest


def current_activity(request: HttpRequest) -> dict[str, Activity | None]:
    """Expose the current activity to every template (sidebar card).

    Views decorated with `activity_required` already resolved it; other pages
    (password change, error pages) resolve it here for logged-in users.
    """
    resolved_activity: Activity | None = getattr(request, "activity", None)
    if resolved_activity is None and request.user.is_authenticated:
        authenticated_request = cast(AuthenticatedHttpRequest, request)
        resolved_activity = activity_current(
            user=authenticated_request.user,
            selected_activity_id=request.session.get(CURRENT_ACTIVITY_SESSION_KEY),
        )
    return {"current_activity": resolved_activity}

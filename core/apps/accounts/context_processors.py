from typing import cast

from django.http import HttpRequest

from .models import Profession
from .selectors import profession_current
from .types import CURRENT_PROFESSION_SESSION_KEY, AuthenticatedHttpRequest


def current_profession(request: HttpRequest) -> dict[str, Profession | None]:
    """Expose the current profession to every template (sidebar card).

    Views decorated with `profession_required` already resolved it; other pages
    (password change, error pages) resolve it here for logged-in users.
    """
    resolved_profession: Profession | None = getattr(request, "profession", None)
    if resolved_profession is None and request.user.is_authenticated:
        authenticated_request = cast(AuthenticatedHttpRequest, request)
        resolved_profession = profession_current(
            user=authenticated_request.user,
            selected_profession_id=request.session.get(CURRENT_PROFESSION_SESSION_KEY),
        )
    return {"current_profession": resolved_profession}

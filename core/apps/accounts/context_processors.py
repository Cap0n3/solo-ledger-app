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


def _nav_section(*, app_name: str, url_name: str) -> str | None:
    if app_name == "students":
        return "plans" if url_name.startswith("plan_") else "students"
    if app_name == "accounting":
        return "expenses" if url_name.startswith("expense_") else "accounting"
    if app_name == "bank_imports":
        return "bank_imports"
    if app_name == "reports":
        return url_name
    if app_name == "accounts":
        is_settings_page = url_name.startswith(("settings", "lesson_year_"))
        return "settings" if is_settings_page else None
    return None


def navigation(request: HttpRequest) -> dict[str, str | None]:
    """Expose which navigation entry the current page belongs to.

    Error pages have no resolver match and highlight nothing.
    """
    match = request.resolver_match
    if match is None:
        return {"nav_section": None}
    section = _nav_section(app_name=match.app_name, url_name=match.url_name or "")
    return {"nav_section": section}

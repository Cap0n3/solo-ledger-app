import functools
from collections.abc import Callable
from typing import Concatenate, cast

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from .selectors import profession_current
from .types import CURRENT_PROFESSION_SESSION_KEY, ProfessionHttpRequest


def profession_required[**P](
    view: Callable[Concatenate[ProfessionHttpRequest, P], HttpResponse],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Require a logged-in user with a current profession as `request.profession`.

    Anonymous users are redirected to the login page. A user without any
    profession gets a 403, because every business page filters on an profession.
    """

    def wrapper(
        request: HttpRequest, /, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        # The authentication check above guarantees a concrete user.
        profession_request = cast(ProfessionHttpRequest, request)
        profession = profession_current(
            user=profession_request.user,
            selected_profession_id=request.session.get(CURRENT_PROFESSION_SESSION_KEY),
        )
        if profession is None:
            raise PermissionDenied(_("Aucune activité n'est associée à ce compte."))
        profession_request.profession = profession
        return view(profession_request, *args, **kwargs)

    functools.update_wrapper(wrapper, view)
    return wrapper

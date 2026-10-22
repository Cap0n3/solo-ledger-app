import functools
from collections.abc import Callable
from typing import Concatenate, cast

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from .selectors import activity_current
from .types import CURRENT_ACTIVITY_SESSION_KEY, ActivityHttpRequest


def activity_required[**P](
    view: Callable[Concatenate[ActivityHttpRequest, P], HttpResponse],
) -> Callable[Concatenate[HttpRequest, P], HttpResponse]:
    """Require a logged-in user with a current activity, exposed as `request.activity`.

    Anonymous users are redirected to the login page. A user without any
    activity gets a 403, because every business page filters on an activity.
    """

    def wrapper(
        request: HttpRequest, /, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        # The authentication check above guarantees a concrete user.
        activity_request = cast(ActivityHttpRequest, request)
        activity = activity_current(
            user=activity_request.user,
            selected_activity_id=request.session.get(CURRENT_ACTIVITY_SESSION_KEY),
        )
        if activity is None:
            raise PermissionDenied(_("Aucune activité n'est associée à ce compte."))
        activity_request.activity = activity
        return view(activity_request, *args, **kwargs)

    functools.update_wrapper(wrapper, view)
    return wrapper

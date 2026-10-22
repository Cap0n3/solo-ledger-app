"""Request types used for precise annotations in views and decorators.

These classes exist only for typing: Django always passes a plain
`HttpRequest`, so they must never be used with `isinstance`.
"""

from django.http import HttpRequest

from .models import Profession, User

CURRENT_PROFESSION_SESSION_KEY = "current_profession_id"


class AuthenticatedHttpRequest(HttpRequest):
    user: User


class ProfessionHttpRequest(AuthenticatedHttpRequest):
    profession: Profession

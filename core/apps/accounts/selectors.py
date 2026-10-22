from django.db.models import QuerySet

from .models import Profession, User


def profession_list(*, user: User) -> QuerySet[Profession]:
    return Profession.objects.filter(user=user)


def profession_current(
    *, user: User, selected_profession_id: int | None
) -> Profession | None:
    """Resolve the profession the user is currently working on.

    The profession selected in the session wins as long as it still belongs to
    the user; otherwise the oldest profession is used so that the fallback stays
    stable when new professions are added later.
    """
    owned_professions = profession_list(user=user)
    if selected_profession_id is not None:
        selected_profession = owned_professions.filter(
            pk=selected_profession_id
        ).first()
        if selected_profession is not None:
            return selected_profession
    return owned_professions.order_by("created_at", "pk").first()

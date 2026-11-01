from datetime import date

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from core.utils.months import month_start

from .models import LessonYear, Profession, User


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


def lesson_year_list(*, profession: Profession) -> QuerySet[LessonYear]:
    return LessonYear.objects.filter(profession=profession)


def lesson_year_get(*, profession: Profession, lesson_year_id: int) -> LessonYear:
    return get_object_or_404(lesson_year_list(profession=profession), pk=lesson_year_id)


def lesson_year_for_month(*, profession: Profession, month: date) -> LessonYear | None:
    """The lesson year whose billed months include `month` (allocation rule)."""
    return (
        lesson_year_list(profession=profession)
        .filter(first_month__lte=month, last_month__gte=month)
        .first()
    )


def lesson_year_current(*, profession: Profession, today: date) -> LessonYear | None:
    """Default lesson year shown in the interface.

    The one containing today's month; during the break between two years, the
    next one; after the last configured year, the most recent one.
    """
    month = month_start(today)
    containing = lesson_year_for_month(profession=profession, month=month)
    if containing is not None:
        return containing
    upcoming = (
        lesson_year_list(profession=profession)
        .filter(first_month__gt=month)
        .order_by("first_month")
        .first()
    )
    if upcoming is not None:
        return upcoming
    return lesson_year_list(profession=profession).order_by("-first_month").first()

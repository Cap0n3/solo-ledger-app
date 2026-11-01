import logging
from datetime import date

from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.utils.translation import gettext as _

from .models import LessonYear, Profession, User
from .selectors import lesson_year_list

logger = logging.getLogger(__name__)


def user_create(
    *,
    username: str,
    password: str,
    first_name: str = "",
    email: str = "",
    is_superuser: bool = False,
) -> User:
    if is_superuser:
        return User.objects.create_superuser(
            username=username, password=password, first_name=first_name, email=email
        )
    return User.objects.create_user(
        username=username, password=password, first_name=first_name, email=email
    )


def user_profile_update(*, user: User, first_name: str, last_name: str) -> User:
    user.first_name = first_name
    user.last_name = last_name
    user.save(update_fields=["first_name", "last_name"])
    return user


def user_avatar_update(*, user: User, avatar: File[bytes]) -> User:
    """Replace the user's avatar. The previous file is removed from storage."""
    if user.avatar:
        user.avatar.delete(save=False)
    user.avatar = avatar
    user.save(update_fields=["avatar"])
    return user


def user_avatar_remove(*, user: User) -> User:
    """Delete the avatar file and clear the field. No avatar is not an error."""
    if user.avatar:
        user.avatar.delete(save=False)
        user.save(update_fields=["avatar"])
    return user


def profession_create(*, user: User, name: str) -> Profession:
    profession = Profession(user=user, name=name)
    profession.full_clean()
    profession.save()
    return profession


def _lesson_year_validate(lesson_year: LessonYear) -> None:
    """Model rules plus the cross-record rule: years of a profession never overlap."""
    lesson_year.full_clean()
    overlapping = (
        lesson_year_list(profession=lesson_year.profession)
        .filter(
            first_month__lte=lesson_year.last_month,
            last_month__gte=lesson_year.first_month,
        )
        .exclude(pk=lesson_year.pk)
    )
    if overlapping.exists():
        raise ValidationError(
            {
                "first_month": ValidationError(
                    _("Cette année chevauche une année de cours existante."),
                    code="overlap",
                )
            }
        )


def lesson_year_create(
    *, profession: Profession, first_month: date, last_month: date
) -> LessonYear:
    lesson_year = LessonYear(
        profession=profession, first_month=first_month, last_month=last_month
    )
    _lesson_year_validate(lesson_year)
    lesson_year.save()
    logger.info(
        "Lesson year created: lesson_year_id=%s profession_id=%s first=%s last=%s",
        lesson_year.pk,
        profession.pk,
        first_month,
        last_month,
    )
    return lesson_year


def lesson_year_update(
    *, lesson_year: LessonYear, first_month: date, last_month: date
) -> LessonYear:
    lesson_year.first_month = first_month
    lesson_year.last_month = last_month
    _lesson_year_validate(lesson_year)
    lesson_year.save()
    logger.info(
        "Lesson year updated: lesson_year_id=%s first=%s last=%s",
        lesson_year.pk,
        first_month,
        last_month,
    )
    return lesson_year

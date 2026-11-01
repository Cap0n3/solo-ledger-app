import pytest

from core.apps.accounts.selectors import profession_current, profession_list

from .factories import ProfessionFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_profession_current_returns_selected_profession_when_owned():
    user = UserFactory.create()
    ProfessionFactory.create(user=user, name="Alpha")
    selected = ProfessionFactory.create(user=user, name="Beta")

    assert profession_current(user=user, selected_profession_id=selected.pk) == selected


def test_profession_current_ignores_profession_owned_by_another_user():
    user = UserFactory.create()
    own = ProfessionFactory.create(user=user)
    foreign = ProfessionFactory.create()

    assert profession_current(user=user, selected_profession_id=foreign.pk) == own


def test_profession_current_falls_back_to_oldest_profession():
    user = UserFactory.create()
    oldest = ProfessionFactory.create(user=user, name="Zèbre")
    ProfessionFactory.create(user=user, name="Alpha")

    assert profession_current(user=user, selected_profession_id=None) == oldest


def test_profession_current_returns_none_without_profession():
    user = UserFactory.create()

    assert profession_current(user=user, selected_profession_id=None) is None


def test_profession_list_only_returns_own_professions():
    user = UserFactory.create()
    own = ProfessionFactory.create(user=user)
    ProfessionFactory.create()

    assert list(profession_list(user=user)) == [own]


# --- Lesson years -----------------------------------------------------------


def test_lesson_year_for_month_and_current_default():
    import datetime

    from core.apps.accounts.selectors import lesson_year_current, lesson_year_for_month

    from .factories import LessonYearFactory

    profession = ProfessionFactory.create()
    past = LessonYearFactory.create(
        profession=profession,
        first_month=datetime.date(2025, 9, 1),
        last_month=datetime.date(2026, 7, 1),
    )
    current = LessonYearFactory.create(
        profession=profession,
        first_month=datetime.date(2026, 9, 1),
        last_month=datetime.date(2027, 7, 1),
    )
    LessonYearFactory.create()

    assert (
        lesson_year_for_month(profession=profession, month=datetime.date(2026, 12, 1))
        == current
    )
    assert (
        lesson_year_for_month(profession=profession, month=datetime.date(2026, 8, 1))
        is None
    )
    assert (
        lesson_year_current(profession=profession, today=datetime.date(2026, 10, 15))
        == current
    )
    assert (
        lesson_year_current(profession=profession, today=datetime.date(2026, 8, 20))
        == current
    )
    assert (
        lesson_year_current(profession=profession, today=datetime.date(2028, 1, 1))
        == current
    )
    assert (
        lesson_year_current(profession=profession, today=datetime.date(2025, 6, 1))
        == past
    )


def test_lesson_year_current_without_any_year():
    import datetime

    from core.apps.accounts.selectors import lesson_year_current

    assert (
        lesson_year_current(
            profession=ProfessionFactory.create(), today=datetime.date(2026, 10, 1)
        )
        is None
    )

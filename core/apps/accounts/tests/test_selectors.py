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

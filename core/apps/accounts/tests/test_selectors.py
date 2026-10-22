import pytest

from core.apps.accounts.selectors import activity_current, activity_list

from .factories import ActivityFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_activity_current_returns_selected_activity_when_owned():
    user = UserFactory.create()
    ActivityFactory.create(user=user, name="Alpha")
    selected = ActivityFactory.create(user=user, name="Beta")

    assert activity_current(user=user, selected_activity_id=selected.pk) == selected


def test_activity_current_ignores_activity_owned_by_another_user():
    user = UserFactory.create()
    own = ActivityFactory.create(user=user)
    foreign = ActivityFactory.create()

    assert activity_current(user=user, selected_activity_id=foreign.pk) == own


def test_activity_current_falls_back_to_oldest_activity():
    user = UserFactory.create()
    oldest = ActivityFactory.create(user=user, name="Zèbre")
    ActivityFactory.create(user=user, name="Alpha")

    assert activity_current(user=user, selected_activity_id=None) == oldest


def test_activity_current_returns_none_without_activity():
    user = UserFactory.create()

    assert activity_current(user=user, selected_activity_id=None) is None


def test_activity_list_only_returns_own_activities():
    user = UserFactory.create()
    own = ActivityFactory.create(user=user)
    ActivityFactory.create()

    assert list(activity_list(user=user)) == [own]

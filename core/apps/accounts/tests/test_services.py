import pytest
from django.core.exceptions import ValidationError

from core.apps.accounts.services import activity_create

from .factories import ActivityFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_activity_create_attaches_activity_to_user():
    user = UserFactory.create()

    activity = activity_create(user=user, name="Cours de guitare")

    assert activity.user == user
    assert activity.name == "Cours de guitare"


def test_activity_create_rejects_duplicate_name_for_same_user():
    existing = ActivityFactory.create(name="Cours de guitare")

    with pytest.raises(ValidationError):
        activity_create(user=existing.user, name="Cours de guitare")


def test_activity_create_allows_same_name_for_another_user():
    ActivityFactory.create(name="Cours de guitare")
    other_user = UserFactory.create()

    activity = activity_create(user=other_user, name="Cours de guitare")

    assert activity.pk is not None

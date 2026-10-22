import pytest
from django.core.exceptions import ValidationError

from core.apps.accounts.services import profession_create

from .factories import ProfessionFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_profession_create_attaches_profession_to_user():
    user = UserFactory.create()

    profession = profession_create(user=user, name="Cours de guitare")

    assert profession.user == user
    assert profession.name == "Cours de guitare"


def test_profession_create_rejects_duplicate_name_for_same_user():
    existing = ProfessionFactory.create(name="Cours de guitare")

    with pytest.raises(ValidationError):
        profession_create(user=existing.user, name="Cours de guitare")


def test_profession_create_allows_same_name_for_another_user():
    ProfessionFactory.create(name="Cours de guitare")
    other_user = UserFactory.create()

    profession = profession_create(user=other_user, name="Cours de guitare")

    assert profession.pk is not None

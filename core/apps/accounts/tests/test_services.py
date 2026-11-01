import pytest
from django.core.exceptions import ValidationError

from core.apps.accounts.services import (
    profession_create,
    user_avatar_remove,
    user_avatar_update,
)

from .factories import ProfessionFactory, UserFactory, avatar_upload

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


def test_user_avatar_update_stores_file_in_user_folder():
    user = UserFactory.create()

    user_avatar_update(user=user, avatar=avatar_upload())

    user.refresh_from_db()
    name = str(user.avatar)
    assert name.startswith(f"avatars/{user.pk}/")
    assert name.endswith(".png")
    assert "avatar.png" not in name
    assert user.avatar.storage.exists(name)


def test_user_avatar_update_deletes_previous_file():
    user = UserFactory.create()
    user_avatar_update(user=user, avatar=avatar_upload("first.png"))
    first_name = str(user.avatar)

    user_avatar_update(user=user, avatar=avatar_upload("second.png"))

    second_name = str(user.avatar)
    assert second_name != first_name
    assert not user.avatar.storage.exists(first_name)
    assert user.avatar.storage.exists(second_name)


def test_user_avatar_remove_deletes_file_and_clears_field():
    user = UserFactory.create()
    user_avatar_update(user=user, avatar=avatar_upload())
    name = str(user.avatar)
    storage = user.avatar.storage

    user_avatar_remove(user=user)

    user.refresh_from_db()
    assert not user.avatar
    assert not storage.exists(name)


def test_user_avatar_remove_without_avatar_changes_nothing():
    user = UserFactory.create()

    user_avatar_remove(user=user)

    user.refresh_from_db()
    assert not user.avatar

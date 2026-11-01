import io

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from factory.django import DjangoModelFactory
from PIL import Image

from core.apps.accounts.models import Profession, User


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Sequence(lambda n: f"[TEST] User {n}")
    email = factory.LazyAttribute(lambda user: f"{user.username}@example.com")
    password = factory.django.Password("password")


class ProfessionFactory(DjangoModelFactory[Profession]):
    class Meta:
        model = Profession

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Profession {n}")


def avatar_upload(name: str = "avatar.png") -> SimpleUploadedFile:
    """A tiny valid PNG, as a browser would upload it."""
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

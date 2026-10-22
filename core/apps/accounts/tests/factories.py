import factory
from factory.django import DjangoModelFactory

from core.apps.accounts.models import Activity, User


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Sequence(lambda n: f"[TEST] User {n}")
    email = factory.LazyAttribute(lambda user: f"{user.username}@example.com")
    password = factory.django.Password("password")


class ActivityFactory(DjangoModelFactory[Activity]):
    class Meta:
        model = Activity

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Activity {n}")

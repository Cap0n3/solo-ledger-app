"""Create obviously fake development data. Documented in README.md."""

from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.apps.accounting.seed import seed_profession_payments
from core.apps.accounts.models import Profession, User
from core.apps.accounts.selectors import profession_list
from core.apps.accounts.services import profession_create, user_create
from core.apps.students.seed import seed_profession_students

SEED_PASSWORD = "sololedger"
SEED_ADMIN_USERNAME = "test_admin"


@dataclass(frozen=True)
class SeedAccount:
    username: str
    first_name: str
    profession_name: str
    catalog_name: str


SEED_ACCOUNTS = (
    SeedAccount(
        username="test_guitar",
        first_name="[TEST] Guitare",
        profession_name="Cours de guitare",
        catalog_name="guitar",
    ),
    SeedAccount(
        username="test_singing",
        first_name="[TEST] Chant",
        profession_name="Cours de chant",
        catalog_name="singing",
    ),
)


class Command(BaseCommand):
    help = (
        "Create fake development data: two teacher accounts with one profession "
        "each (plans, lesson years, payers and students included), plus a "
        "technical admin account. Safe to run several times. Refused unless "
        "settings.SEED_ALLOWED is true."
    )

    def handle(self, *args: object, **options: object) -> None:
        if not settings.SEED_ALLOWED:
            raise CommandError(
                "Seeding is disabled in this environment (SEED_ALLOWED is false)."
            )
        for account in SEED_ACCOUNTS:
            user = self._user_get_or_create(account)
            profession = self._profession_get_or_create(
                user=user, name=account.profession_name
            )
            seed_profession_students(
                profession=profession,
                catalog_name=account.catalog_name,
                stdout=self.stdout,
            )
            seed_profession_payments(profession=profession, stdout=self.stdout)
        self._admin_get_or_create()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed data ready. Password for every test account: {SEED_PASSWORD}"
            )
        )

    def _user_get_or_create(self, account: SeedAccount) -> User:
        user = User.objects.filter(username=account.username).first()
        if user is not None:
            self.stdout.write(f"User {account.username} already exists")
            return user
        user = user_create(
            username=account.username,
            password=SEED_PASSWORD,
            first_name=account.first_name,
            email=f"{account.username}@example.com",
        )
        self.stdout.write(f"Created user {account.username}")
        return user

    def _profession_get_or_create(self, *, user: User, name: str) -> Profession:
        existing = profession_list(user=user).filter(name=name).first()
        if existing is not None:
            self.stdout.write(f"Profession '{name}' already exists for {user.username}")
            return existing
        profession = profession_create(user=user, name=name)
        self.stdout.write(f"Created profession '{name}' for {user.username}")
        return profession

    def _admin_get_or_create(self) -> None:
        if User.objects.filter(username=SEED_ADMIN_USERNAME).exists():
            self.stdout.write(f"User {SEED_ADMIN_USERNAME} already exists")
            return
        user_create(
            username=SEED_ADMIN_USERNAME,
            password=SEED_PASSWORD,
            first_name="[TEST] Admin",
            email=f"{SEED_ADMIN_USERNAME}@example.com",
            is_superuser=True,
        )
        self.stdout.write(f"Created superuser {SEED_ADMIN_USERNAME}")

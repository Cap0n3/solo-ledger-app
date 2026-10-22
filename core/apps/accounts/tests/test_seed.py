import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.apps.accounts.management.commands.seed import SEED_PASSWORD
from core.apps.accounts.models import Activity, User

pytestmark = pytest.mark.django_db


def test_seed_is_idempotent_and_creates_usable_accounts(settings):
    settings.SEED_ALLOWED = True

    call_command("seed")
    call_command("seed")

    assert User.objects.filter(username__startswith="test_").count() == 3
    assert Activity.objects.count() == 2
    guitar_user = User.objects.get(username="test_guitar")
    assert guitar_user.check_password(SEED_PASSWORD)
    assert guitar_user.first_name.startswith("[TEST]")
    assert guitar_user.email.endswith("@example.com")
    assert guitar_user.activities.get().name == "Cours de guitare"
    assert User.objects.get(username="test_admin").is_superuser


def test_seed_is_refused_when_not_allowed(settings):
    settings.SEED_ALLOWED = False

    with pytest.raises(CommandError):
        call_command("seed")

    assert not User.objects.exists()

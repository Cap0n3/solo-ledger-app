import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.apps.accounting.models import ExpectedPayment, Payment
from core.apps.accounts.management.commands.seed import SEED_PASSWORD
from core.apps.accounts.models import LessonYear, Profession, User
from core.apps.students.models import (
    Payer,
    Plan,
    PlanAssignment,
    Student,
    StudentPause,
)

pytestmark = pytest.mark.django_db


def test_seed_is_idempotent_and_creates_usable_accounts(settings):
    settings.SEED_ALLOWED = True

    call_command("seed")
    call_command("seed")

    assert User.objects.filter(username__startswith="test_").count() == 3
    assert Profession.objects.count() == 2
    guitar = Profession.objects.get(name="Cours de guitare")
    singing = Profession.objects.get(name="Cours de chant")
    assert Plan.objects.filter(profession=guitar).count() == 3
    assert Plan.objects.filter(profession=singing).count() == 8
    assert Student.objects.filter(profession=guitar).count() == 12
    assert Student.objects.filter(profession=singing).count() == 12
    assert Payer.objects.count() == 3
    assert LessonYear.objects.filter(profession=guitar).count() == 2
    assert PlanAssignment.objects.filter(payer__isnull=False).count() == 1
    assert all(
        student.first_name.startswith("[TEST]")
        and student.email.endswith("@example.com")
        for student in Student.objects.all()
    )
    assert StudentPause.objects.count() == 2
    assert ExpectedPayment.objects.filter(profession=guitar).exists()
    assert ExpectedPayment.objects.filter(payer__isnull=False).exists()
    assert ExpectedPayment.objects.filter(is_cancelled=True).exists()
    payment_count = Payment.objects.count()
    assert payment_count > 0
    one_off_incomes = Payment.objects.filter(kind=Payment.Kind.ONE_OFF)
    assert one_off_incomes.filter(student__isnull=True).count() == 2
    assert all(income.label.startswith("[TEST]") for income in one_off_incomes)
    call_command("seed")
    assert Payment.objects.count() == payment_count
    guitar_user = User.objects.get(username="test_guitar")
    assert guitar_user.check_password(SEED_PASSWORD)
    assert guitar_user.first_name.startswith("[TEST]")
    assert guitar_user.email.endswith("@example.com")
    assert guitar_user.professions.get().name == "Cours de guitare"
    assert User.objects.get(username="test_admin").is_superuser


def test_seed_is_refused_when_not_allowed(settings):
    settings.SEED_ALLOWED = False

    with pytest.raises(CommandError):
        call_command("seed")

    assert not User.objects.exists()

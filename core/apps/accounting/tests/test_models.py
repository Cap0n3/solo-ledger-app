import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.apps.accounting.models import Payment
from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.tests.factories import PayerFactory, StudentFactory

from .factories import ExpectedPaymentFactory, PaymentFactory

pytestmark = pytest.mark.django_db


def test_expected_payment_needs_exactly_one_target():
    expected = ExpectedPaymentFactory.create()
    expected.payer = PayerFactory.create(profession=expected.profession)

    with pytest.raises(ValidationError):
        expected.full_clean()


def test_expected_payment_target_must_belong_to_same_profession():
    expected = ExpectedPaymentFactory.create()
    expected.student = StudentFactory.create()

    with pytest.raises(ValidationError) as excinfo:
        expected.full_clean()

    assert "student" in excinfo.value.error_dict


def test_expected_payment_is_unique_per_student_and_month():
    expected = ExpectedPaymentFactory.create()

    with pytest.raises(IntegrityError), transaction.atomic():
        ExpectedPaymentFactory.create(
            profession=expected.profession,
            student=expected.student,
            plan=expected.plan,
            month=expected.month,
        )


def test_expected_payment_due_date_uses_the_profession_due_day():
    profession = ProfessionFactory.create(payment_due_day=15)
    expected = ExpectedPaymentFactory.create(
        profession=profession, month=datetime.date(2026, 11, 1)
    )

    assert expected.due_date == datetime.date(2026, 11, 15)


def test_monthly_payment_needs_a_student_or_a_payer():
    payment = PaymentFactory.create()
    payment.student = None

    with pytest.raises(ValidationError):
        payment.full_clean()


def test_one_off_income_needs_a_label_and_no_student():
    payment = PaymentFactory.create(one_off=True)
    payment.full_clean()
    assert payment.student is None

    payment.label = "  "
    with pytest.raises(ValidationError) as excinfo:
        payment.full_clean()

    assert "label" in excinfo.value.error_dict


def test_one_off_income_never_targets_a_payer():
    profession = ProfessionFactory.create()
    payer = PayerFactory.create(profession=profession)

    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentFactory.create(one_off=True, profession=profession, payer=payer)


def test_payment_student_must_belong_to_same_profession():
    payment = PaymentFactory.create()
    payment.student = StudentFactory.create()

    with pytest.raises(ValidationError) as excinfo:
        payment.full_clean()

    assert "student" in excinfo.value.error_dict


def test_payment_fiscal_year_is_the_year_it_was_received():
    payment = PaymentFactory.build(
        kind=Payment.Kind.MONTHLY,
        received_on=datetime.date(2026, 12, 28),
        amount=Decimal("280.00"),
    )

    assert payment.fiscal_year == 2026

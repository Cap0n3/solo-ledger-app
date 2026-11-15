"""Fake payments for development: every case of the payments milestone.

Everything goes through the services, so seeded data obeys the business rules.
Labels and notes are prefixed with « [TEST] » and nothing here is real data.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import OutputWrapper
from django.db import transaction
from django.utils import timezone

from core.apps.accounts.models import Profession
from core.apps.accounts.selectors import lesson_year_current
from core.apps.students.models import Payer, Student
from core.apps.students.selectors import payer_list, student_list
from core.utils.months import month_add, month_start

from .models import ExpectedPayment, Payment, PaymentMethod
from .selectors import expected_payment_list, payment_list
from .services import (
    AllocationInput,
    expected_payment_cancel,
    expected_payments_sync_for_profession,
    one_off_income_create,
    payment_create,
)

TEST_PREFIX = "[TEST] "
SCENARIO_COUNT = 5
SCENARIO_ON_TIME = 0
SCENARIO_PAID_LATE = 1
SCENARIO_PARTIAL = 2
SCENARIO_CANCELLED_AND_CREDIT = 3
SCENARIO_ARREARS = 4
PAID_IN_ADVANCE_DAY = 28
PAID_LATE_DAY = 20
CREDIT_AMOUNT = Decimal("20.00")
GIFT_VOUCHER_AMOUNT = Decimal("450.00")


def _paid_in_advance_on(month: date) -> date:
    """The 28th of the month before: lessons are paid in advance."""
    return month_add(month, -1).replace(day=PAID_IN_ADVANCE_DAY)


def _pay_month(
    *,
    expected_payment: ExpectedPayment,
    received_on: date,
    share: Decimal,
    amount: Decimal,
    method: PaymentMethod = PaymentMethod.BANK_TRANSFER,
) -> None:
    payment_create(
        profession=expected_payment.profession,
        received_on=received_on,
        amount=amount,
        method=method,
        notes="",
        allocations=[AllocationInput(expected_payment=expected_payment, amount=share)],
        student=expected_payment.student,
        payer=expected_payment.payer,
    )


def _seed_student_payments(
    *, student: Student, scenario: int, today: date, current_year_start: date
) -> None:
    """Pay the student's months up to today according to one scenario."""
    current_month = month_start(today)
    past_months: list[ExpectedPayment] = []
    for expected_payment in expected_payment_list(student=student):
        if expected_payment.month <= current_month:
            past_months.append(expected_payment)
    first_of_current_year: date | None = None
    latest_of_current_year: date | None = None
    last_of_previous_year: date | None = None
    for expected_payment in past_months:
        month = expected_payment.month
        if month < current_year_start:
            last_of_previous_year = month
            continue
        if first_of_current_year is None:
            first_of_current_year = month
        latest_of_current_year = month

    for expected_payment in past_months:
        month = expected_payment.month
        price = expected_payment.amount
        is_current_year = month >= current_year_start
        is_first = month == first_of_current_year
        is_latest = month == latest_of_current_year
        received_on = _paid_in_advance_on(month)
        share = price
        amount = price
        method = PaymentMethod.BANK_TRANSFER
        if scenario == SCENARIO_ARREARS:
            # Nothing paid this year, and the last month of the previous year owed.
            if is_current_year or month == last_of_previous_year:
                continue
        elif scenario == SCENARIO_PAID_LATE and is_latest:
            received_on = min(month.replace(day=PAID_LATE_DAY), today)
            method = PaymentMethod.TWINT
        elif scenario == SCENARIO_PARTIAL and is_latest:
            share = (price / 2).quantize(Decimal("0.01"))
            amount = share
            method = PaymentMethod.CASH
        elif scenario == SCENARIO_CANCELLED_AND_CREDIT and is_latest:
            amount = price + CREDIT_AMOUNT
        elif scenario == SCENARIO_CANCELLED_AND_CREDIT and is_first:
            expected_payment_cancel(
                expected_payment=expected_payment, reason=TEST_PREFIX + "Absence forcée"
            )
            continue
        _pay_month(
            expected_payment=expected_payment,
            received_on=received_on,
            share=share,
            amount=amount,
            method=method,
        )


def _seed_family_payments(*, payer: Payer, today: date) -> None:
    """A family plan settled in two transfers a month, one per child."""
    current_month = month_start(today)
    for expected_payment in expected_payment_list(payer=payer):
        if expected_payment.month > current_month:
            continue
        half = (expected_payment.amount / 2).quantize(Decimal("0.01"))
        for share in (half, expected_payment.amount - half):
            _pay_month(
                expected_payment=expected_payment,
                received_on=_paid_in_advance_on(expected_payment.month),
                share=share,
                amount=share,
            )


@transaction.atomic
def seed_profession_payments(*, profession: Profession, stdout: OutputWrapper) -> None:
    """Create expected payments, payments and one-off income for a profession.

    Idempotent: expected payments are always brought up to date, but a
    profession that already has payments gets no new ones.
    """
    expected_payments_sync_for_profession(profession=profession)
    if payment_list(profession=profession).exists():
        stdout.write(f"Payments of '{profession.name}' already seeded")
        return
    today = timezone.localdate()
    lesson_year = lesson_year_current(profession=profession, today=today)
    if lesson_year is None:
        stdout.write(f"No lesson year for '{profession.name}': no payments seeded")
        return
    students = list(student_list(profession=profession).order_by("pk"))
    for index, student in enumerate(students):
        _seed_student_payments(
            student=student,
            scenario=index % SCENARIO_COUNT,
            today=today,
            current_year_start=lesson_year.first_month,
        )
    for payer in payer_list(profession=profession):
        _seed_family_payments(payer=payer, today=today)
    one_off_income_create(
        profession=profession,
        received_on=today.replace(day=1),
        amount=GIFT_VOUCHER_AMOUNT,
        method=PaymentMethod.BANK_TRANSFER,
        label=TEST_PREFIX + "Bon cadeau 5 cours",
        notes=TEST_PREFIX + "Acheté par un proche, bénéficiaire sans fiche.",
        student=None,
    )
    for student in students:
        single_lesson_price: Decimal | None = None
        for assignment in student.plan_assignments.all():
            if not assignment.plan.is_monthly:
                single_lesson_price = assignment.plan.price
        if single_lesson_price is not None:
            one_off_income_create(
                profession=profession,
                received_on=today.replace(day=1),
                amount=single_lesson_price,
                method=PaymentMethod.CASH,
                label=TEST_PREFIX + "Cours à la carte",
                notes="",
                student=student,
            )
    payment_total = Payment.objects.filter(profession=profession).count()
    stdout.write(f"Seeded '{profession.name}': {payment_total} payments")

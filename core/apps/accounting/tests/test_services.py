import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from core.apps.accounting.models import ExpectedPayment, Payment, PaymentMethod
from core.apps.accounting.selectors import (
    MonthStatus,
    expected_payment_list,
    expected_payments_for_lesson_year,
    month_line_build,
    payment_allocation_propose,
    unallocated_credit_list,
)
from core.apps.accounting.services import (
    AllocationInput,
    expected_payment_amount_update,
    expected_payment_cancel,
    expected_payment_restore,
    expected_payments_sync,
    one_off_income_create,
    payment_create,
    payment_delete,
    payment_update,
)
from core.apps.accounts.services import lesson_year_create, lesson_year_update
from core.apps.accounts.tests.factories import LessonYearFactory, ProfessionFactory
from core.apps.students.services import (
    plan_assign,
    plan_assignment_end,
    plan_assignment_remove_latest,
    student_pause_create,
    student_pause_delete,
    student_pause_update,
    student_update,
)
from core.apps.students.tests.factories import (
    PayerFactory,
    PlanFactory,
    StudentFactory,
)

pytestmark = pytest.mark.django_db

SEPTEMBER = datetime.date(2026, 9, 1)
OCTOBER = datetime.date(2026, 10, 1)
NOVEMBER = datetime.date(2026, 11, 1)
DECEMBER = datetime.date(2026, 12, 1)
JANUARY = datetime.date(2027, 1, 1)
FEBRUARY = datetime.date(2027, 2, 1)
MARCH = datetime.date(2027, 3, 1)
APRIL = datetime.date(2027, 4, 1)
JULY = datetime.date(2027, 7, 1)
PRICE = Decimal("280.00")


def make_student(profession=None, start_date=SEPTEMBER, price=PRICE, **fields):
    """A student with a monthly plan from their start month, in a 2026-2027 year."""
    if profession is None:
        profession = ProfessionFactory.create()
    if not profession.lessonyear_set.exists():
        LessonYearFactory.create(profession=profession)
    student = StudentFactory.create(
        profession=profession, start_date=start_date, **fields
    )
    plan = PlanFactory.create(profession=profession, price=price)
    plan_assign(
        plan=plan,
        starts_on=start_date.replace(day=1),
        student=student,
    )
    return student


def months_of(student=None, payer=None):
    expected_payments = expected_payment_list(student=student, payer=payer)
    return [expected_payment.month for expected_payment in expected_payments]


def expected_for(month, student=None, payer=None):
    return expected_payment_list(student=student, payer=payer).get(month=month)


def student_fields(student, **overrides):
    fields = {
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "phone": student.phone,
        "notes": student.notes,
        "start_date": student.start_date,
        "end_date": student.end_date,
        "status": student.status,
        "payment_reference_name": student.payment_reference_name,
        "payer": student.payer,
    }
    fields.update(overrides)
    return fields


def pay(student=None, payer=None, *, amount, received_on, months=None):
    """Record a payment allocated as proposed, or to the months given."""
    target = student if student is not None else payer
    if months is None:
        proposal = payment_allocation_propose(
            amount=amount, received_on=received_on, student=student, payer=payer
        )
        allocations = [
            AllocationInput(
                expected_payment=share.expected_payment, amount=share.amount
            )
            for share in proposal.shares
        ]
    else:
        allocations = [
            AllocationInput(
                expected_payment=expected_for(month, student=student, payer=payer),
                amount=share,
            )
            for month, share in months.items()
        ]
    return payment_create(
        profession=target.profession,
        received_on=received_on,
        amount=amount,
        method=PaymentMethod.BANK_TRANSFER,
        notes="",
        allocations=allocations,
        student=student,
        payer=payer,
    )


def line_for(month, today, student=None, payer=None):
    return month_line_build(
        expected_payment=expected_for(month, student=student, payer=payer), today=today
    )


# --- Creation of expected payments ------------------------------------------


def test_assigning_a_plan_creates_every_billed_month_from_the_start_date():
    student = make_student(start_date=datetime.date(2026, 10, 15))

    months = months_of(student)

    assert months[0] == OCTOBER
    assert months[-1] == JULY
    assert len(months) == 10
    assert expected_for(OCTOBER, student).amount == PRICE


def test_no_expected_payment_without_a_plan_or_with_a_single_lesson_plan():
    profession = ProfessionFactory.create()
    LessonYearFactory.create(profession=profession)
    without_plan = StudentFactory.create(profession=profession)
    single_lesson = StudentFactory.create(profession=profession)
    plan = PlanFactory.create(profession=profession, kind="single_lesson")
    plan_assign(plan=plan, starts_on=SEPTEMBER, student=single_lesson)
    expected_payments_sync(student=without_plan)

    assert months_of(without_plan) == []
    assert months_of(single_lesson) == []


def test_new_lesson_year_creates_months_for_students_who_carry_on():
    student = make_student()
    stopped = make_student(
        profession=student.profession, end_date=datetime.date(2027, 6, 30)
    )

    lesson_year_create(
        profession=student.profession,
        first_month=datetime.date(2027, 9, 1),
        last_month=datetime.date(2028, 7, 1),
    )

    assert months_of(student)[-1] == datetime.date(2028, 7, 1)
    assert len(months_of(student)) == 22
    assert months_of(stopped)[-1] == datetime.date(2027, 6, 1)


def test_august_is_not_billed_between_two_lesson_years():
    student = make_student()
    lesson_year_create(
        profession=student.profession,
        first_month=datetime.date(2027, 9, 1),
        last_month=datetime.date(2028, 7, 1),
    )

    assert datetime.date(2027, 8, 1) not in months_of(student)


def test_plan_change_updates_only_untouched_months_from_its_start():
    student = make_student()
    pay(student, amount=PRICE, received_on=datetime.date(2026, 8, 28))
    expected_payment_amount_update(
        expected_payment=expected_for(FEBRUARY, student), amount=Decimal("140.00")
    )
    cheaper = PlanFactory.create(profession=student.profession, price=Decimal("160.00"))

    plan_assign(plan=cheaper, starts_on=JANUARY, student=student)

    assert expected_for(SEPTEMBER, student).amount == PRICE
    assert expected_for(DECEMBER, student).amount == PRICE
    assert expected_for(JANUARY, student).amount == Decimal("160.00")
    assert expected_for(FEBRUARY, student).amount == Decimal("140.00")
    assert expected_for(MARCH, student).amount == Decimal("160.00")


def test_changing_a_plan_price_never_rewrites_expected_payments():
    student = make_student()
    plan = expected_for(SEPTEMBER, student).plan
    plan.price = Decimal("300.00")
    plan.save()

    expected_payments_sync(student=student)

    assert expected_for(SEPTEMBER, student).amount == PRICE


def test_family_plan_follows_its_assignment_not_the_students_dates():
    profession = ProfessionFactory.create()
    LessonYearFactory.create(profession=profession)
    payer = PayerFactory.create(profession=profession)
    StudentFactory.create(
        profession=profession, payer=payer, start_date=datetime.date(2026, 11, 1)
    )
    family_plan = PlanFactory.create(profession=profession, price=Decimal("420.00"))

    assignment = plan_assign(plan=family_plan, starts_on=OCTOBER, payer=payer)
    assert months_of(payer=payer)[0] == OCTOBER
    assert len(months_of(payer=payer)) == 10

    plan_assignment_end(assignment=assignment, last_month=DECEMBER)
    assert months_of(payer=payer) == [OCTOBER, NOVEMBER, DECEMBER]


def test_family_plan_and_individual_plans_add_up():
    student = make_student()
    payer = PayerFactory.create(profession=student.profession)
    student.payer = payer
    student.save()
    family_plan = PlanFactory.create(
        profession=student.profession, price=Decimal("420.00")
    )

    plan_assign(plan=family_plan, starts_on=SEPTEMBER, payer=payer)

    assert len(months_of(student)) == 11
    assert len(months_of(payer=payer)) == 11


# --- Shrinking periods ------------------------------------------------------


def test_end_date_deletes_untouched_months_and_keeps_paid_ones_flagged():
    student = make_student()
    pay(
        student,
        amount=PRICE,
        received_on=datetime.date(2026, 9, 1),
        months={APRIL: PRICE},
    )

    student_update(
        student=student,
        **student_fields(student, end_date=datetime.date(2027, 3, 31)),
    )

    assert months_of(student)[-2:] == [MARCH, APRIL]
    assert expected_for(MARCH, student).is_due
    assert not expected_for(APRIL, student).is_due


def test_cancelled_and_hand_edited_months_survive_a_shrinking_period():
    student = make_student()
    expected_payment_cancel(expected_payment=expected_for(APRIL, student), reason="")
    expected_payment_amount_update(
        expected_payment=expected_for(JULY, student), amount=Decimal("100.00")
    )

    student_update(
        student=student,
        **student_fields(student, end_date=datetime.date(2027, 3, 31)),
    )

    kept = [
        expected_payment.month
        for expected_payment in expected_payment_list(student=student)
        if not expected_payment.is_due
    ]
    assert kept == [APRIL, JULY]


def test_removing_the_assignment_deletes_untouched_months():
    student = make_student()

    plan_assignment_remove_latest(student=student)

    assert months_of(student) == []


def test_shortening_the_lesson_year_deletes_untouched_months():
    student = make_student()
    lesson_year = student.profession.lessonyear_set.get()

    lesson_year_update(
        lesson_year=lesson_year,
        first_month=SEPTEMBER,
        last_month=datetime.date(2027, 6, 1),
    )

    assert months_of(student)[-1] == datetime.date(2027, 6, 1)


def test_a_flagged_month_is_due_again_when_the_period_grows_back():
    student = make_student()
    pay(
        student,
        amount=PRICE,
        received_on=datetime.date(2026, 9, 1),
        months={APRIL: PRICE},
    )
    student_update(
        student=student,
        **student_fields(student, end_date=datetime.date(2027, 3, 31)),
    )

    student_update(student=student, **student_fields(student, end_date=None))

    assert expected_for(APRIL, student).is_due
    assert months_of(student)[-1] == JULY


# --- Pauses -----------------------------------------------------------------


def test_pause_removes_only_the_months_lying_entirely_within_it():
    student = make_student()

    student_pause_create(
        student=student,
        starts_on=datetime.date(2027, 1, 15),
        ends_on=datetime.date(2027, 3, 10),
    )

    months = months_of(student)
    assert JANUARY in months
    assert FEBRUARY not in months
    assert MARCH in months


def test_ending_or_deleting_a_pause_recreates_the_months_due_again():
    student = make_student()
    pause = student_pause_create(
        student=student, starts_on=datetime.date(2027, 1, 1), ends_on=None
    )
    assert months_of(student)[-1] == DECEMBER

    student_pause_update(
        pause=pause,
        starts_on=datetime.date(2027, 1, 1),
        ends_on=datetime.date(2027, 2, 28),
    )
    assert JANUARY not in months_of(student)
    assert MARCH in months_of(student)

    student_pause_delete(pause=pause)
    assert len(months_of(student)) == 11


def test_a_paid_month_within_a_pause_is_kept_and_flagged():
    student = make_student()
    pay(
        student,
        amount=PRICE,
        received_on=datetime.date(2026, 9, 1),
        months={FEBRUARY: PRICE},
    )

    student_pause_create(
        student=student,
        starts_on=datetime.date(2027, 1, 1),
        ends_on=datetime.date(2027, 2, 28),
    )

    assert JANUARY not in months_of(student)
    assert not expected_for(FEBRUARY, student).is_due


def test_pauses_of_a_student_cannot_overlap():
    student = make_student()
    student_pause_create(
        student=student,
        starts_on=datetime.date(2027, 1, 15),
        ends_on=datetime.date(2027, 3, 10),
    )

    with pytest.raises(ValidationError) as excinfo:
        student_pause_create(
            student=student, starts_on=datetime.date(2027, 3, 10), ends_on=None
        )

    assert excinfo.value.code == "overlap"


def test_a_students_pause_leaves_the_family_plan_untouched():
    student = make_student()
    payer = PayerFactory.create(profession=student.profession)
    student.payer = payer
    student.save()
    family_plan = PlanFactory.create(profession=student.profession)
    plan_assign(plan=family_plan, starts_on=SEPTEMBER, payer=payer)

    student_pause_create(
        student=student, starts_on=datetime.date(2027, 1, 1), ends_on=None
    )

    assert len(months_of(payer=payer)) == 11


# --- Allocation of payments to months ---------------------------------------


def test_roger_example_from_the_specification():
    """SPECS « Attribution des paiements aux mois »: Roger M., 280 CHF a month."""
    roger = make_student()

    pay(roger, amount=PRICE, received_on=datetime.date(2026, 8, 28))
    pay(roger, amount=PRICE, received_on=datetime.date(2026, 9, 25))
    mid_november = datetime.date(2026, 11, 15)
    assert line_for(NOVEMBER, mid_november, roger).status == MonthStatus.LATE
    pay(roger, amount=PRICE, received_on=datetime.date(2026, 11, 24))
    pay(roger, amount=PRICE, received_on=datetime.date(2026, 11, 28))

    today = datetime.date(2026, 11, 30)
    september = line_for(SEPTEMBER, today, roger)
    october = line_for(OCTOBER, today, roger)
    november = line_for(NOVEMBER, today, roger)
    december = line_for(DECEMBER, today, roger)
    assert september.status == MonthStatus.PAID and not september.is_paid_late
    assert october.status == MonthStatus.PAID and not october.is_paid_late
    assert november.status == MonthStatus.PAID and november.is_paid_late
    assert november.allocations[0].payment.received_on == datetime.date(2026, 11, 24)
    assert december.status == MonthStatus.PAID and not december.is_paid_late
    assert line_for(JANUARY, today, roger).status == MonthStatus.UNPAID


def test_a_payment_of_several_instalments_is_spread_oldest_month_first():
    student = make_student()

    proposal = payment_allocation_propose(
        amount=Decimal("560.00"),
        received_on=datetime.date(2026, 9, 2),
        student=student,
    )

    assert [share.expected_payment.month for share in proposal.shares] == [
        SEPTEMBER,
        OCTOBER,
    ]
    assert proposal.unallocated == Decimal("0.00")
    assert proposal.warnings == []


def test_cancelled_month_is_skipped_by_the_proposal():
    student = make_student()
    expected_payment_cancel(
        expected_payment=expected_for(SEPTEMBER, student), reason="Accident"
    )

    proposal = payment_allocation_propose(
        amount=PRICE, received_on=datetime.date(2026, 9, 2), student=student
    )

    assert proposal.shares[0].expected_payment.month == OCTOBER


def test_mid_month_start_partial_payment_then_adjusted_amount_is_paid():
    """SPECS « Début et fin en cours de mois »: no prorata, the user adjusts."""
    student = make_student(start_date=datetime.date(2026, 10, 15))
    today = datetime.date(2026, 10, 20)
    assert expected_for(OCTOBER, student).amount == PRICE

    proposal = payment_allocation_propose(
        amount=Decimal("140.00"), received_on=today, student=student
    )
    assert "partial_payment" in proposal.warnings
    pay(student, amount=Decimal("140.00"), received_on=today)
    assert line_for(OCTOBER, today, student).status == MonthStatus.PARTIALLY_PAID

    expected_payment_amount_update(
        expected_payment=expected_for(OCTOBER, student), amount=Decimal("140.00")
    )

    october = line_for(OCTOBER, today, student)
    assert october.status == MonthStatus.PAID
    assert october.expected_payment.is_amount_manual


def test_leftover_below_an_instalment_stays_an_unallocated_credit():
    student = make_student()

    proposal = payment_allocation_propose(
        amount=Decimal("300.00"),
        received_on=datetime.date(2026, 9, 2),
        student=student,
    )
    pay(student, amount=Decimal("300.00"), received_on=datetime.date(2026, 9, 2))

    assert [share.amount for share in proposal.shares] == [PRICE]
    assert proposal.unallocated == Decimal("20.00")
    assert "unallocated_credit" in proposal.warnings
    credits = unallocated_credit_list(student=student)
    assert [credit.amount for credit in credits] == [Decimal("20.00")]
    today = datetime.date(2026, 9, 2)
    assert line_for(OCTOBER, today, student).status == MonthStatus.UNPAID


def test_payment_received_on_28_december_pays_january_but_is_2026_income():
    """SPECS « Année de cours et année fiscale »."""
    from core.apps.accounting.selectors import income_for_fiscal_year

    student = make_student()
    for day in (
        datetime.date(2026, 8, 28),
        datetime.date(2026, 9, 28),
        datetime.date(2026, 10, 28),
        datetime.date(2026, 11, 28),
    ):
        pay(student, amount=PRICE, received_on=day)

    payment = pay(student, amount=PRICE, received_on=datetime.date(2026, 12, 28))

    assert payment.allocations.get().expected_payment.month == JANUARY
    assert payment.fiscal_year == 2026
    profession = student.profession
    assert income_for_fiscal_year(profession=profession, fiscal_year=2026) == Decimal(
        "1400.00"
    )
    assert income_for_fiscal_year(profession=profession, fiscal_year=2027) == Decimal(
        "0.00"
    )


def test_august_payment_goes_to_the_new_year_and_never_settles_arrears():
    """SPECS « Cas non évidents »: arrears are settled by hand only."""
    profession = ProfessionFactory.create()
    LessonYearFactory.create(
        profession=profession,
        first_month=datetime.date(2025, 9, 1),
        last_month=datetime.date(2026, 7, 1),
    )
    LessonYearFactory.create(profession=profession)
    student = make_student(profession=profession, start_date=datetime.date(2026, 7, 1))
    assert months_of(student)[0] == datetime.date(2026, 7, 1)

    proposal = payment_allocation_propose(
        amount=PRICE, received_on=datetime.date(2026, 8, 20), student=student
    )

    assert [share.expected_payment.month for share in proposal.shares] == [SEPTEMBER]
    assert "arrears_exist" in proposal.warnings

    pay(
        student,
        amount=PRICE,
        received_on=datetime.date(2026, 8, 20),
        months={datetime.date(2026, 7, 1): PRICE},
    )
    today = datetime.date(2026, 8, 20)
    july = line_for(datetime.date(2026, 7, 1), today, student)
    assert july.status == MonthStatus.PAID


def test_payment_without_any_lesson_year_ahead_stays_unallocated():
    student = make_student()

    proposal = payment_allocation_propose(
        amount=PRICE, received_on=datetime.date(2027, 8, 20), student=student
    )

    assert proposal.shares == []
    assert proposal.unallocated == PRICE
    assert "no_lesson_year" in proposal.warnings


def test_family_plan_is_settled_in_several_transfers_without_warning():
    profession = ProfessionFactory.create()
    LessonYearFactory.create(profession=profession)
    payer = PayerFactory.create(profession=profession)
    family_plan = PlanFactory.create(profession=profession, price=Decimal("420.00"))
    plan_assign(plan=family_plan, starts_on=SEPTEMBER, payer=payer)
    today = datetime.date(2026, 9, 5)

    first = payment_allocation_propose(
        amount=Decimal("210.00"), received_on=today, payer=payer
    )
    assert first.warnings == []
    pay(payer=payer, amount=Decimal("210.00"), received_on=today)
    assert line_for(SEPTEMBER, today, payer=payer).status == MonthStatus.PARTIALLY_PAID

    pay(payer=payer, amount=Decimal("210.00"), received_on=today)

    assert line_for(SEPTEMBER, today, payer=payer).status == MonthStatus.PAID
    assert line_for(OCTOBER, today, payer=payer).status == MonthStatus.UNPAID


def test_one_transfer_for_two_students_is_recorded_as_two_payments():
    first = make_student()
    second = make_student(profession=first.profession)
    received_on = datetime.date(2026, 9, 2)

    with pytest.raises(ValidationError) as excinfo:
        payment_create(
            profession=first.profession,
            received_on=received_on,
            amount=Decimal("560.00"),
            method=PaymentMethod.BANK_TRANSFER,
            notes="",
            allocations=[
                AllocationInput(expected_for(SEPTEMBER, first), PRICE),
                AllocationInput(expected_for(SEPTEMBER, second), PRICE),
            ],
            student=first,
        )
    assert excinfo.value.code == "foreign_expected_payment"
    assert Payment.objects.count() == 0

    pay(first, amount=PRICE, received_on=received_on)
    pay(second, amount=PRICE, received_on=received_on)

    assert line_for(SEPTEMBER, received_on, first).status == MonthStatus.PAID
    assert line_for(SEPTEMBER, received_on, second).status == MonthStatus.PAID


def test_allocations_cannot_exceed_the_payment_or_what_a_month_still_owes():
    student = make_student()
    received_on = datetime.date(2026, 9, 2)

    with pytest.raises(ValidationError) as above_payment:
        pay(
            student,
            amount=PRICE,
            received_on=received_on,
            months={SEPTEMBER: PRICE, OCTOBER: PRICE},
        )
    with pytest.raises(ValidationError) as above_remaining:
        pay(
            student,
            amount=Decimal("600.00"),
            received_on=received_on,
            months={SEPTEMBER: Decimal("300.00")},
        )

    assert above_payment.value.code == "above_payment"
    assert above_remaining.value.code == "above_remaining"
    assert Payment.objects.count() == 0


# --- Late months, due day ---------------------------------------------------


def test_unpaid_month_turns_late_after_the_due_day_which_can_be_changed():
    student = make_student()

    on_the_due_day = line_for(SEPTEMBER, datetime.date(2026, 9, 10), student)
    the_day_after = line_for(SEPTEMBER, datetime.date(2026, 9, 11), student)
    assert on_the_due_day.status == MonthStatus.UNPAID
    assert the_day_after.status == MonthStatus.LATE

    student.profession.payment_due_day = 20
    student.profession.save()

    recomputed = line_for(SEPTEMBER, datetime.date(2026, 9, 11), student)
    assert recomputed.status == MonthStatus.UNPAID


# --- Cancelling months ------------------------------------------------------


def test_cancelled_month_is_not_owed_and_can_be_restored():
    student = make_student()
    september = expected_for(SEPTEMBER, student)
    today = datetime.date(2026, 9, 20)

    expected_payment_cancel(expected_payment=september, reason="Accident")
    cancelled = line_for(SEPTEMBER, today, student)
    assert cancelled.status == MonthStatus.CANCELLED
    assert cancelled.remaining == Decimal("0.00")

    expected_payment_restore(expected_payment=expected_for(SEPTEMBER, student))
    assert line_for(SEPTEMBER, today, student).status == MonthStatus.LATE


def test_a_month_with_a_payment_cannot_be_cancelled():
    student = make_student()
    pay(student, amount=PRICE, received_on=datetime.date(2026, 8, 28))

    with pytest.raises(ValidationError) as excinfo:
        expected_payment_cancel(
            expected_payment=expected_for(SEPTEMBER, student), reason=""
        )

    assert excinfo.value.code == "has_allocations"


def test_expected_amount_cannot_go_below_what_was_paid():
    student = make_student()
    pay(student, amount=PRICE, received_on=datetime.date(2026, 8, 28))

    with pytest.raises(ValidationError) as excinfo:
        expected_payment_amount_update(
            expected_payment=expected_for(SEPTEMBER, student), amount=Decimal("100.00")
        )

    assert excinfo.value.code == "below_allocated"


# --- Editing and deleting payments ------------------------------------------


def test_deleting_a_payment_frees_its_months():
    student = make_student()
    payment = pay(student, amount=PRICE, received_on=datetime.date(2026, 8, 28))
    today = datetime.date(2026, 9, 1)

    payment_delete(payment=payment)

    assert line_for(SEPTEMBER, today, student).status == MonthStatus.UNPAID
    assert Payment.objects.count() == 0


def test_deleting_the_payment_of_a_month_no_longer_due_removes_that_month():
    student = make_student()
    payment = pay(
        student,
        amount=PRICE,
        received_on=datetime.date(2026, 9, 1),
        months={APRIL: PRICE},
    )
    student_update(
        student=student,
        **student_fields(student, end_date=datetime.date(2027, 3, 31)),
    )

    payment_delete(payment=payment)

    assert months_of(student)[-1] == MARCH


def test_updating_a_payment_replaces_its_allocations():
    student = make_student()
    payment = pay(student, amount=PRICE, received_on=datetime.date(2026, 8, 28))
    today = datetime.date(2026, 9, 1)

    payment_update(
        payment=payment,
        received_on=datetime.date(2026, 8, 28),
        amount=Decimal("560.00"),
        method=PaymentMethod.TWINT,
        notes="",
        allocations=[
            AllocationInput(expected_for(OCTOBER, student), PRICE),
            AllocationInput(expected_for(NOVEMBER, student), PRICE),
        ],
        student=student,
    )

    assert line_for(SEPTEMBER, today, student).status == MonthStatus.UNPAID
    assert line_for(OCTOBER, today, student).status == MonthStatus.PAID
    assert line_for(NOVEMBER, today, student).status == MonthStatus.PAID


# --- One-off income ---------------------------------------------------------


def test_one_off_income_is_never_allocated_and_needs_no_student():
    student = make_student()
    profession = student.profession

    gift_voucher = one_off_income_create(
        profession=profession,
        received_on=datetime.date(2026, 9, 3),
        amount=Decimal("450.00"),
        method=PaymentMethod.BANK_TRANSFER,
        label="[TEST] Bon cadeau 5 cours",
        notes="",
        student=None,
    )
    single_lesson = one_off_income_create(
        profession=profession,
        received_on=datetime.date(2026, 9, 3),
        amount=Decimal("90.00"),
        method=PaymentMethod.CASH,
        label="[TEST] Cours à la carte",
        notes="",
        student=student,
    )

    assert gift_voucher.student is None
    assert gift_voucher.allocations.count() == 0
    assert single_lesson.allocations.count() == 0
    today = datetime.date(2026, 9, 3)
    assert line_for(SEPTEMBER, today, student).status == MonthStatus.UNPAID
    assert unallocated_credit_list(student=student) == []


def test_lesson_year_overview_lists_only_the_months_of_that_year():
    student = make_student()
    lesson_year = student.profession.lessonyear_set.get()
    lesson_year_create(
        profession=student.profession,
        first_month=datetime.date(2027, 9, 1),
        last_month=datetime.date(2028, 7, 1),
    )

    lines = expected_payments_for_lesson_year(
        lesson_year=lesson_year, today=datetime.date(2026, 9, 1), student=student
    )

    assert len(lines) == 11
    assert ExpectedPayment.objects.filter(student=student).count() == 22

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import models
from django.db.models import QuerySet, Sum
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.models import LessonYear, Profession
from core.apps.accounts.selectors import (
    lesson_year_current,
    lesson_year_for_month,
    lesson_year_list,
)
from core.apps.students.models import Payer, Plan, Student, StudentPause
from core.apps.students.selectors import (
    plan_assignment_current,
    plan_assignment_list,
    student_pause_list,
)
from core.utils.months import month_start

from .models import ExpectedPayment, Payment, PaymentAllocation

ZERO = Decimal("0.00")


def payment_target(*, student: Student | None, payer: Payer | None) -> Student | Payer:
    """The single student or payer a payment or an expected payment is about."""
    if student is not None and payer is None:
        return student
    if payer is not None and student is None:
        return payer
    raise ValueError("Exactly one of student or payer is required.")


# --- Expected payments ------------------------------------------------------


def expected_months_due(
    *, student: Student | None = None, payer: Payer | None = None
) -> dict[date, Plan]:
    """Every billed month the target owes, with the monthly plan in effect.

    Business rules (SPECS « Création des paiements attendus », « Pauses »): only
    months of a configured lesson year are due; a student owes from the month
    of the start date to the month of the end date, except months lying
    entirely within a pause; a family plan follows its assignment alone.
    Single-lesson plans never create expected payments.
    """
    target = payment_target(student=student, payer=payer)
    assignments = list(plan_assignment_list(student=student, payer=payer))
    pauses: list[StudentPause] = []
    first_month: date | None = None
    last_month: date | None = None
    if student is not None:
        # Queried afresh: the caller's instance may carry a stale prefetch.
        pauses = list(student_pause_list(student=student))
        first_month = month_start(student.start_date)
        if student.end_date is not None:
            last_month = month_start(student.end_date)

    months_due: dict[date, Plan] = {}
    for lesson_year in lesson_year_list(profession=target.profession):
        for month in lesson_year.months:
            if first_month is not None and month < first_month:
                continue
            if last_month is not None and month > last_month:
                continue
            assignment = plan_assignment_current(assignments=assignments, month=month)
            if assignment is None or not assignment.plan.is_monthly:
                continue
            is_paused = False
            for pause in pauses:
                if pause.covers_whole_month(month):
                    is_paused = True
                    break
            if is_paused:
                continue
            months_due[month] = assignment.plan
    return months_due


def expected_payment_list(
    *, student: Student | None = None, payer: Payer | None = None
) -> QuerySet[ExpectedPayment]:
    """Expected payments of one student or payer, oldest month first."""
    payment_target(student=student, payer=payer)
    expected_payments = ExpectedPayment.objects.select_related(
        "profession", "plan"
    ).prefetch_related("allocations__payment")
    if student is not None:
        return expected_payments.filter(student=student)
    return expected_payments.filter(payer=payer)


def expected_payment_get(
    *, profession: Profession, expected_payment_id: int
) -> ExpectedPayment:
    expected_payments = ExpectedPayment.objects.filter(
        profession=profession
    ).select_related("profession", "plan", "student", "payer")
    return get_object_or_404(expected_payments, pk=expected_payment_id)


def expected_payment_allocated_total(
    *, expected_payment: ExpectedPayment, exclude_payment: Payment | None = None
) -> Decimal:
    """Sum allocated to the month, optionally ignoring one payment being edited."""
    total = ZERO
    for allocation in expected_payment.allocations.all():
        if exclude_payment is not None and allocation.payment_id == exclude_payment.pk:
            continue
        total += allocation.amount
    return total


class MonthStatus(models.TextChoices):
    PAID = "paid", _("Payé")
    PARTIALLY_PAID = "partially_paid", _("Partiellement payé")
    UNPAID = "unpaid", _("Impayé")
    LATE = "late", _("En retard")
    CANCELLED = "cancelled", _("Annulé")


@dataclass(frozen=True)
class MonthLine:
    """One expected month with what was allocated to it and its computed status."""

    expected_payment: ExpectedPayment
    allocations: list[PaymentAllocation]
    allocated_total: Decimal
    remaining: Decimal
    status: MonthStatus
    is_paid_late: bool
    is_overdue: bool

    @property
    def status_label(self) -> str:
        return str(self.status.label)


def month_line_build(*, expected_payment: ExpectedPayment, today: date) -> MonthLine:
    """Compute the status of a month; nothing but the cancellation is stored.

    Business rule (SPECS « Attribution des paiements aux mois »): before the
    payment due day an unsettled month is unpaid, after it it is late; once
    fully settled it is paid, « paid late » when the settling payment was
    received after the due day.
    """
    allocations = list(expected_payment.allocations.all())
    allocated_total = ZERO
    last_received_on: date | None = None
    for allocation in allocations:
        allocated_total += allocation.amount
        received_on = allocation.payment.received_on
        if last_received_on is None or received_on > last_received_on:
            last_received_on = received_on
    remaining = max(expected_payment.amount - allocated_total, ZERO)
    due_date = expected_payment.due_date
    is_paid_late = False
    is_overdue = False
    if expected_payment.is_cancelled:
        status = MonthStatus.CANCELLED
        remaining = ZERO
    elif remaining == ZERO:
        status = MonthStatus.PAID
        is_paid_late = last_received_on is not None and last_received_on > due_date
    else:
        is_overdue = today > due_date
        if allocated_total > ZERO:
            status = MonthStatus.PARTIALLY_PAID
        elif is_overdue:
            status = MonthStatus.LATE
        else:
            status = MonthStatus.UNPAID
    return MonthLine(
        expected_payment=expected_payment,
        allocations=allocations,
        allocated_total=allocated_total,
        remaining=remaining,
        status=status,
        is_paid_late=is_paid_late,
        is_overdue=is_overdue,
    )


def expected_payments_for_lesson_year(
    *,
    lesson_year: LessonYear,
    today: date,
    student: Student | None = None,
    payer: Payer | None = None,
) -> list[MonthLine]:
    """Month-by-month situation of a student or payer for one lesson year."""
    expected_payments = expected_payment_list(student=student, payer=payer).filter(
        month__gte=lesson_year.first_month, month__lte=lesson_year.last_month
    )
    lines: list[MonthLine] = []
    for expected_payment in expected_payments:
        lines.append(month_line_build(expected_payment=expected_payment, today=today))
    return lines


def arrears_for_lesson_year(
    *,
    lesson_year: LessonYear,
    today: date,
    student: Student | None = None,
    payer: Payer | None = None,
) -> list[MonthLine]:
    """Unsettled months of the lesson years before `lesson_year` (« arriérés »)."""
    expected_payments = expected_payment_list(student=student, payer=payer).filter(
        month__lt=lesson_year.first_month, is_due=True, is_cancelled=False
    )
    lines: list[MonthLine] = []
    for expected_payment in expected_payments:
        line = month_line_build(expected_payment=expected_payment, today=today)
        if line.remaining > ZERO:
            lines.append(line)
    return lines


def expected_payments_no_longer_due(
    *, today: date, student: Student | None = None, payer: Payer | None = None
) -> list[MonthLine]:
    """Months kept although no longer due, for the user to sort out."""
    expected_payments = expected_payment_list(student=student, payer=payer).filter(
        is_due=False
    )
    lines: list[MonthLine] = []
    for expected_payment in expected_payments:
        lines.append(month_line_build(expected_payment=expected_payment, today=today))
    return lines


# --- Payments ---------------------------------------------------------------


def payment_list(*, profession: Profession) -> QuerySet[Payment]:
    return (
        Payment.objects.filter(profession=profession)
        .select_related("student", "payer")
        .prefetch_related("allocations__expected_payment")
    )


def payment_get(*, profession: Profession, payment_id: int) -> Payment:
    return get_object_or_404(payment_list(profession=profession), pk=payment_id)


def payment_allocated_total(*, payment: Payment) -> Decimal:
    total = ZERO
    for allocation in payment.allocations.all():
        total += allocation.amount
    return total


@dataclass(frozen=True)
class UnallocatedCredit:
    """Part of a monthly payment not allocated to any month (« avoir »)."""

    payment: Payment
    amount: Decimal


def unallocated_credit_list(
    *, student: Student | None = None, payer: Payer | None = None
) -> list[UnallocatedCredit]:
    target = payment_target(student=student, payer=payer)
    payments = payment_list(profession=target.profession).filter(
        kind=Payment.Kind.MONTHLY
    )
    if student is not None:
        payments = payments.filter(student=student)
    else:
        payments = payments.filter(payer=payer)
    credits: list[UnallocatedCredit] = []
    for payment in payments:
        unallocated = payment.amount - payment_allocated_total(payment=payment)
        if unallocated > ZERO:
            credits.append(UnallocatedCredit(payment=payment, amount=unallocated))
    return credits


def one_off_income_list(*, student: Student) -> QuerySet[Payment]:
    """One-off income linked to the student (single lessons, gift vouchers)."""
    return payment_list(profession=student.profession).filter(
        kind=Payment.Kind.ONE_OFF, student=student
    )


@dataclass(frozen=True)
class PaymentOverview:
    """What a student or payer page shows about payments for one lesson year."""

    lesson_years: list[LessonYear]
    lesson_year: LessonYear | None
    lines: list[MonthLine]
    arrears: list[MonthLine]
    credits: list[UnallocatedCredit]
    no_longer_due: list[MonthLine]
    expected_total: Decimal
    allocated_total: Decimal
    remaining_total: Decimal

    @property
    def has_content(self) -> bool:
        return bool(self.lines or self.arrears or self.credits or self.no_longer_due)


def lesson_year_for_overview(
    *, profession: Profession, lesson_year_id: str | None, today: date
) -> LessonYear | None:
    """The lesson year picked in the period selector, else the current one."""
    if lesson_year_id is not None and lesson_year_id.isdigit():
        lesson_year = (
            lesson_year_list(profession=profession)
            .filter(pk=int(lesson_year_id))
            .first()
        )
        if lesson_year is not None:
            return lesson_year
    return lesson_year_current(profession=profession, today=today)


def payment_overview(
    *,
    today: date,
    lesson_year: LessonYear | None,
    student: Student | None = None,
    payer: Payer | None = None,
) -> PaymentOverview:
    """Month-by-month situation, arrears, credits and months to sort out."""
    target = payment_target(student=student, payer=payer)
    lines: list[MonthLine] = []
    arrears: list[MonthLine] = []
    if lesson_year is not None:
        lines = expected_payments_for_lesson_year(
            lesson_year=lesson_year, today=today, student=student, payer=payer
        )
        arrears = arrears_for_lesson_year(
            lesson_year=lesson_year, today=today, student=student, payer=payer
        )
    expected_total = ZERO
    allocated_total = ZERO
    remaining_total = ZERO
    for line in lines:
        if line.status == MonthStatus.CANCELLED or not line.expected_payment.is_due:
            continue
        expected_total += line.expected_payment.amount
        allocated_total += line.allocated_total
        remaining_total += line.remaining
    return PaymentOverview(
        lesson_years=list(lesson_year_list(profession=target.profession)),
        lesson_year=lesson_year,
        lines=lines,
        arrears=arrears,
        credits=unallocated_credit_list(student=student, payer=payer),
        no_longer_due=expected_payments_no_longer_due(
            today=today, student=student, payer=payer
        ),
        expected_total=expected_total,
        allocated_total=allocated_total,
        remaining_total=remaining_total,
    )


# --- Allocation of a payment to months --------------------------------------


@dataclass(frozen=True)
class AllocatableMonth:
    """A month a payment may be allocated to, with what is still owed on it."""

    expected_payment: ExpectedPayment
    remaining: Decimal


def allocatable_month_list(
    *,
    student: Student | None = None,
    payer: Payer | None = None,
    exclude_payment: Payment | None = None,
) -> list[AllocatableMonth]:
    """Every month of the target still owing something, arrears included.

    `exclude_payment` is the payment being edited: its own allocations are
    ignored so that the months it currently settles stay available.
    """
    expected_payments = expected_payment_list(student=student, payer=payer).filter(
        is_due=True, is_cancelled=False
    )
    months: list[AllocatableMonth] = []
    for expected_payment in expected_payments:
        allocated_total = expected_payment_allocated_total(
            expected_payment=expected_payment, exclude_payment=exclude_payment
        )
        remaining = expected_payment.amount - allocated_total
        if remaining > ZERO:
            months.append(
                AllocatableMonth(expected_payment=expected_payment, remaining=remaining)
            )
    return months


class AllocationWarning(models.TextChoices):
    """Why a proposed allocation needs the user's attention.

    The bank import reuses these to flag a payment « à vérifier ».
    """

    PARTIAL_PAYMENT = (
        "partial_payment",
        _("Le montant ne couvre pas une mensualité entière : paiement partiel."),
    )
    UNALLOCATED_CREDIT = (
        "unallocated_credit",
        _("Une partie du montant reste un avoir non attribué."),
    )
    ARREARS_EXIST = (
        "arrears_exist",
        _(
            "Un arriéré d'une année précédente existe : il n'est jamais soldé "
            "automatiquement."
        ),
    )
    NO_LESSON_YEAR = (
        "no_lesson_year",
        _("Aucune année de cours ne correspond à cette date : rien n'est attribué."),
    )


@dataclass(frozen=True)
class ProposedShare:
    expected_payment: ExpectedPayment
    amount: Decimal


@dataclass(frozen=True)
class AllocationProposal:
    shares: list[ProposedShare]
    unallocated: Decimal
    warnings: list[AllocationWarning]

    def amount_for(self, expected_payment: ExpectedPayment) -> Decimal | None:
        for share in self.shares:
            if share.expected_payment.pk == expected_payment.pk:
                return share.amount
        return None


def lesson_year_for_payment(
    *, profession: Profession, received_on: date
) -> LessonYear | None:
    """The lesson year a payment received on that day is about.

    Business rule: a payment received in the gap between two lesson years
    (e.g. in August) belongs to the next one.
    """
    month = month_start(received_on)
    lesson_year = lesson_year_for_month(profession=profession, month=month)
    if lesson_year is not None:
        return lesson_year
    return (
        lesson_year_list(profession=profession)
        .filter(first_month__gt=month)
        .order_by("first_month")
        .first()
    )


def payment_allocation_propose(
    *,
    amount: Decimal,
    received_on: date,
    student: Student | None = None,
    payer: Payer | None = None,
    exclude_payment: Payment | None = None,
) -> AllocationProposal:
    """Propose how a payment is split over the months still owed.

    Business rules (SPECS « Attribution des paiements aux mois »): the payment
    goes to the oldest unsettled month of the lesson year concerned, then to
    the following ones, by whole instalments. An amount below the first open
    month is proposed as a partial payment. What is left over stays an
    unallocated credit. Arrears of earlier lesson years are never proposed.
    A family plan may be settled in several transfers, so for a payer a partial
    share is normal and carries no warning.
    """
    target = payment_target(student=student, payer=payer)
    warnings: list[AllocationWarning] = []
    lesson_year = lesson_year_for_payment(
        profession=target.profession, received_on=received_on
    )
    if lesson_year is None:
        warnings.append(AllocationWarning.NO_LESSON_YEAR)
        return AllocationProposal(shares=[], unallocated=amount, warnings=warnings)

    open_months: list[AllocatableMonth] = []
    has_arrears = False
    for month in allocatable_month_list(
        student=student, payer=payer, exclude_payment=exclude_payment
    ):
        if month.expected_payment.month < lesson_year.first_month:
            has_arrears = True
        elif month.expected_payment.month <= lesson_year.last_month:
            open_months.append(month)
    is_received_between_years = not lesson_year.contains(month_start(received_on))
    if has_arrears and is_received_between_years:
        warnings.append(AllocationWarning.ARREARS_EXIST)

    shares: list[ProposedShare] = []
    left = amount
    for month in open_months:
        if left <= ZERO:
            break
        if left >= month.remaining:
            shares.append(
                ProposedShare(
                    expected_payment=month.expected_payment, amount=month.remaining
                )
            )
            left -= month.remaining
            continue
        if payer is not None:
            shares.append(
                ProposedShare(expected_payment=month.expected_payment, amount=left)
            )
            left = ZERO
        elif not shares:
            shares.append(
                ProposedShare(expected_payment=month.expected_payment, amount=left)
            )
            left = ZERO
            warnings.append(AllocationWarning.PARTIAL_PAYMENT)
        break
    if left > ZERO:
        warnings.append(AllocationWarning.UNALLOCATED_CREDIT)
    return AllocationProposal(shares=shares, unallocated=left, warnings=warnings)


# --- Ledger and fiscal year -------------------------------------------------


@dataclass(frozen=True)
class LedgerEntry:
    """A line of the ledger (« écriture comptable »): money actually received.

    There is no ledger table: entries are read from payments (and from
    expenses once they exist), so amounts are never duplicated.
    """

    entry_date: date
    amount: Decimal
    payment: Payment


def ledger_entry_list(*, profession: Profession, fiscal_year: int) -> list[LedgerEntry]:
    """Income of the fiscal (calendar) year, by date received, newest first."""
    payments = payment_list(profession=profession).filter(received_on__year=fiscal_year)
    entries: list[LedgerEntry] = []
    for payment in payments:
        entries.append(
            LedgerEntry(
                entry_date=payment.received_on, amount=payment.amount, payment=payment
            )
        )
    return entries


def income_for_fiscal_year(*, profession: Profession, fiscal_year: int) -> Decimal:
    """Total income received during the fiscal (calendar) year.

    Business rule: income belongs to the fiscal year of the date it was
    received, whatever lesson month it pays for.
    """
    total = Payment.objects.filter(
        profession=profession, received_on__year=fiscal_year
    ).aggregate(total=Sum("amount"))["total"]
    if total is None:
        return ZERO
    return Decimal(total)


def fiscal_year_list(*, profession: Profession, today: date) -> list[int]:
    """Fiscal years to offer in the period selector, newest first."""
    years = {today.year}
    for received_on in Payment.objects.filter(profession=profession).dates(
        "received_on", "year"
    ):
        years.add(received_on.year)
    return sorted(years, reverse=True)

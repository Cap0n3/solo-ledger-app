import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from core.apps.accounts.models import Profession
from core.apps.students.models import Payer, Student

from .models import ExpectedPayment, Payment, PaymentAllocation, PaymentMethod
from .selectors import (
    ZERO,
    expected_months_due,
    expected_payment_allocated_total,
    expected_payment_list,
    payment_allocated_total,
    payment_target,
)

logger = logging.getLogger(__name__)


# --- Expected payments ------------------------------------------------------


@dataclass(frozen=True)
class ExpectedPaymentSyncResult:
    created: int
    updated: int
    deleted: int
    kept_not_due: int


def _is_intact(expected_payment: ExpectedPayment) -> bool:
    """Whether nobody touched the month: it is then plain derived data."""
    if expected_payment.is_cancelled or expected_payment.is_amount_manual:
        return False
    return len(expected_payment.allocations.all()) == 0


@transaction.atomic
def expected_payments_sync(
    *, student: Student | None = None, payer: Payer | None = None
) -> ExpectedPaymentSyncResult:
    """Bring the expected payments of a student or payer in line with what is due.

    Business rules (SPECS « Création des paiements attendus »): missing months
    are created with a snapshot of the plan's price; an intact month follows a
    plan change; a month that is no longer due is deleted when intact, and
    otherwise kept and flagged (`is_due=False`). Paid, partially paid,
    cancelled or hand-edited months are never modified automatically.
    """
    target = payment_target(student=student, payer=payer)
    months_due = expected_months_due(student=student, payer=payer)
    created = 0
    updated = 0
    deleted = 0
    kept_not_due = 0
    existing_months: set[date] = set()
    for expected_payment in expected_payment_list(student=student, payer=payer):
        existing_months.add(expected_payment.month)
        is_intact = _is_intact(expected_payment)
        plan = months_due.get(expected_payment.month)
        if plan is None:
            if is_intact:
                expected_payment.delete()
                deleted += 1
            else:
                kept_not_due += 1
                if expected_payment.is_due:
                    expected_payment.is_due = False
                    expected_payment.save(update_fields=["is_due"])
            continue
        changed_fields: list[str] = []
        if not expected_payment.is_due:
            expected_payment.is_due = True
            changed_fields.append("is_due")
        if is_intact and expected_payment.plan_id != plan.pk:
            expected_payment.plan = plan
            expected_payment.amount = plan.price
            changed_fields.extend(["plan", "amount"])
        if changed_fields:
            expected_payment.save(update_fields=changed_fields)
            updated += 1
    for month, plan in months_due.items():
        if month in existing_months:
            continue
        expected_payment = ExpectedPayment(
            profession=target.profession,
            student=student,
            payer=payer,
            plan=plan,
            month=month,
            amount=plan.price,
        )
        expected_payment.full_clean()
        expected_payment.save()
        created += 1
    result = ExpectedPaymentSyncResult(
        created=created, updated=updated, deleted=deleted, kept_not_due=kept_not_due
    )
    if created or updated or deleted:
        logger.info(
            "Expected payments synced: student_id=%s payer_id=%s created=%s "
            "updated=%s deleted=%s kept_not_due=%s",
            student.pk if student is not None else None,
            payer.pk if payer is not None else None,
            created,
            updated,
            deleted,
            kept_not_due,
        )
    return result


@transaction.atomic
def expected_payments_sync_for_profession(*, profession: Profession) -> None:
    """Sync every student and payer, e.g. after a lesson year was set up."""
    for student in Student.objects.filter(profession=profession):
        expected_payments_sync(student=student)
    for payer in Payer.objects.filter(profession=profession):
        expected_payments_sync(payer=payer)


def _expected_payment_sync_target(expected_payment: ExpectedPayment) -> None:
    expected_payments_sync(
        student=expected_payment.student, payer=expected_payment.payer
    )


def expected_payment_cancel(
    *, expected_payment: ExpectedPayment, reason: str
) -> ExpectedPayment:
    """Mark a month as cancelled: it is no longer owed (SPECS « Annulation »)."""
    if expected_payment.allocations.exists():
        raise ValidationError(
            _(
                "Un paiement est attribué à ce mois : retirez d'abord cette "
                "attribution."
            ),
            code="has_allocations",
        )
    expected_payment.is_cancelled = True
    expected_payment.cancellation_reason = reason
    expected_payment.full_clean()
    expected_payment.save(update_fields=["is_cancelled", "cancellation_reason"])
    logger.info(
        "Expected payment cancelled: expected_payment_id=%s month=%s amount=%s",
        expected_payment.pk,
        expected_payment.month,
        expected_payment.amount,
    )
    return expected_payment


@transaction.atomic
def expected_payment_restore(*, expected_payment: ExpectedPayment) -> None:
    """Undo a cancellation. A month that is no longer due disappears again."""
    if not expected_payment.is_cancelled:
        raise ValidationError(_("Ce mois n'est pas annulé."), code="not_cancelled")
    expected_payment.is_cancelled = False
    expected_payment.cancellation_reason = ""
    expected_payment.save(update_fields=["is_cancelled", "cancellation_reason"])
    logger.info(
        "Expected payment restored: expected_payment_id=%s month=%s",
        expected_payment.pk,
        expected_payment.month,
    )
    _expected_payment_sync_target(expected_payment)


def expected_payment_amount_update(
    *, expected_payment: ExpectedPayment, amount: Decimal
) -> ExpectedPayment:
    """Correct the amount of a month by hand; it is then never recomputed."""
    if expected_payment.is_cancelled:
        raise ValidationError(
            _("Rétablissez d'abord ce mois annulé."), code="cancelled"
        )
    allocated_total = expected_payment_allocated_total(
        expected_payment=expected_payment
    )
    if amount < allocated_total:
        raise ValidationError(
            _("Le montant attendu ne peut pas être inférieur au montant déjà payé."),
            code="below_allocated",
        )
    previous_amount = expected_payment.amount
    expected_payment.amount = amount
    expected_payment.is_amount_manual = True
    expected_payment.full_clean()
    expected_payment.save(update_fields=["amount", "is_amount_manual"])
    logger.info(
        "Expected payment amount updated: expected_payment_id=%s month=%s "
        "previous=%s amount=%s",
        expected_payment.pk,
        expected_payment.month,
        previous_amount,
        amount,
    )
    return expected_payment


# --- Payments ---------------------------------------------------------------


@dataclass(frozen=True)
class AllocationInput:
    """The share of a payment the user gives to one expected month."""

    expected_payment: ExpectedPayment
    amount: Decimal


def _allocations_replace(
    *, payment: Payment, allocations: Sequence[AllocationInput]
) -> None:
    """Replace the allocations of a payment after checking each share.

    A share must go to a month of the same student or payer, still owed, and
    cannot exceed what remains due on it; the shares cannot exceed the payment.
    """
    payment.allocations.all().delete()
    total = ZERO
    seen_ids: set[int] = set()
    rows: list[PaymentAllocation] = []
    for allocation in allocations:
        expected_payment = allocation.expected_payment
        if allocation.amount <= ZERO:
            continue
        if expected_payment.pk in seen_ids:
            raise ValidationError(
                _("Un mois ne peut recevoir qu'une part du paiement."),
                code="duplicate_month",
            )
        seen_ids.add(expected_payment.pk)
        is_same_target = (
            expected_payment.profession_id == payment.profession_id
            and expected_payment.student_id == payment.student_id
            and expected_payment.payer_id == payment.payer_id
        )
        if not is_same_target:
            raise ValidationError(
                _("Un mois attribué ne concerne pas cet élève ou ce payeur."),
                code="foreign_expected_payment",
            )
        if expected_payment.is_cancelled:
            raise ValidationError(
                _("Un paiement ne peut pas être attribué à un mois annulé."),
                code="cancelled_month",
            )
        remaining = expected_payment.amount - expected_payment_allocated_total(
            expected_payment=expected_payment, exclude_payment=payment
        )
        if allocation.amount > remaining:
            raise ValidationError(
                _("La part attribuée à %(month)s dépasse le montant encore dû.")
                % {"month": f"{expected_payment.month:%m.%Y}"},
                code="above_remaining",
            )
        total += allocation.amount
        rows.append(
            PaymentAllocation(
                payment=payment,
                expected_payment=expected_payment,
                amount=allocation.amount,
            )
        )
    if total > payment.amount:
        raise ValidationError(
            _("Les parts attribuées dépassent le montant du paiement."),
            code="above_payment",
        )
    PaymentAllocation.objects.bulk_create(rows)


@transaction.atomic
def payment_create(
    *,
    profession: Profession,
    received_on: date,
    amount: Decimal,
    method: PaymentMethod,
    notes: str,
    allocations: Sequence[AllocationInput],
    student: Student | None = None,
    payer: Payer | None = None,
) -> Payment:
    """Record a monthly payment and allocate it to the months given.

    Business rule: a payment is about a single student, or a single payer
    settling a family plan. Whatever is not allocated stays a credit.
    """
    payment = Payment(
        profession=profession,
        kind=Payment.Kind.MONTHLY,
        student=student,
        payer=payer,
        received_on=received_on,
        amount=amount,
        method=method,
        notes=notes,
    )
    payment.full_clean()
    payment.save()
    _allocations_replace(payment=payment, allocations=allocations)
    logger.info(
        "Payment created: payment_id=%s student_id=%s payer_id=%s amount=%s "
        "received_on=%s allocated=%s",
        payment.pk,
        payment.student_id,
        payment.payer_id,
        amount,
        received_on,
        payment_allocated_total(payment=payment),
    )
    return payment


@transaction.atomic
def payment_update(
    *,
    payment: Payment,
    received_on: date,
    amount: Decimal,
    method: PaymentMethod,
    notes: str,
    allocations: Sequence[AllocationInput],
    student: Student | None = None,
    payer: Payer | None = None,
) -> Payment:
    """Correct a monthly payment; its allocations are replaced by those given."""
    if payment.is_one_off:
        raise ValueError("Use one_off_income_update for a one-off income.")
    previous_student = payment.student
    previous_payer = payment.payer
    payment.allocations.all().delete()
    payment.student = student
    payment.payer = payer
    payment.received_on = received_on
    payment.amount = amount
    payment.method = method
    payment.notes = notes
    payment.full_clean()
    payment.save()
    _allocations_replace(payment=payment, allocations=allocations)
    logger.info(
        "Payment updated: payment_id=%s student_id=%s payer_id=%s amount=%s "
        "received_on=%s",
        payment.pk,
        payment.student_id,
        payment.payer_id,
        amount,
        received_on,
    )
    # A month kept only because this payment settled it may now be removable.
    expected_payments_sync(student=student, payer=payer)
    has_target_changed = (
        getattr(previous_student, "pk", None) != payment.student_id
        or getattr(previous_payer, "pk", None) != payment.payer_id
    )
    if has_target_changed:
        expected_payments_sync(student=previous_student, payer=previous_payer)
    return payment


@transaction.atomic
def payment_delete(*, payment: Payment) -> None:
    """Delete a payment or a one-off income; the months it settled are freed."""
    payment_id = payment.pk
    amount = payment.amount
    student = payment.student
    payer = payment.payer
    is_one_off = payment.is_one_off
    payment.delete()
    logger.info("Payment deleted: payment_id=%s amount=%s", payment_id, amount)
    if not is_one_off:
        expected_payments_sync(student=student, payer=payer)


def one_off_income_create(
    *,
    profession: Profession,
    received_on: date,
    amount: Decimal,
    method: PaymentMethod,
    label: str,
    notes: str,
    student: Student | None,
) -> Payment:
    """Record a one-off income (single lesson, gift voucher).

    Business rule (SPECS « Recettes ponctuelles »): it is never allocated to a
    month and the link to a student is optional.
    """
    payment = Payment(
        profession=profession,
        kind=Payment.Kind.ONE_OFF,
        student=student,
        received_on=received_on,
        amount=amount,
        method=method,
        label=label,
        notes=notes,
    )
    payment.full_clean()
    payment.save()
    logger.info(
        "One-off income created: payment_id=%s student_id=%s amount=%s received_on=%s",
        payment.pk,
        payment.student_id,
        amount,
        received_on,
    )
    return payment


def one_off_income_update(
    *,
    payment: Payment,
    received_on: date,
    amount: Decimal,
    method: PaymentMethod,
    label: str,
    notes: str,
    student: Student | None,
) -> Payment:
    if not payment.is_one_off:
        raise ValueError("Use payment_update for a monthly payment.")
    payment.student = student
    payment.received_on = received_on
    payment.amount = amount
    payment.method = method
    payment.label = label
    payment.notes = notes
    payment.full_clean()
    payment.save()
    logger.info(
        "One-off income updated: payment_id=%s student_id=%s amount=%s received_on=%s",
        payment.pk,
        payment.student_id,
        amount,
        received_on,
    )
    return payment

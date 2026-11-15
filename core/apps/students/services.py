import logging
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from core.apps.accounting.services import expected_payments_sync
from core.apps.accounts.models import Profession
from core.utils.months import month_add, month_start, validate_month_start

from .models import Payer, Plan, PlanAssignment, Student, StudentPause
from .selectors import (
    payer_is_deletable,
    plan_assignment_latest,
    plan_assignment_list,
    plan_assignment_reopened_by_removal,
    student_pause_list,
)

logger = logging.getLogger(__name__)


# --- Plans ------------------------------------------------------------------


def plan_create(
    *,
    profession: Profession,
    name: str,
    description: str,
    price: Decimal,
    kind: Plan.Kind,
) -> Plan:
    plan = Plan(
        profession=profession,
        name=name,
        description=description,
        price=price,
        kind=kind,
    )
    plan.full_clean()
    plan.save()
    logger.info(
        "Plan created: plan_id=%s profession_id=%s kind=%s price=%s",
        plan.pk,
        profession.pk,
        kind,
        price,
    )
    return plan


def plan_update(
    *, plan: Plan, name: str, description: str, price: Decimal, kind: Plan.Kind
) -> Plan:
    plan.name = name
    plan.description = description
    plan.price = price
    plan.kind = kind
    plan.full_clean()
    plan.save()
    logger.info("Plan updated: plan_id=%s kind=%s price=%s", plan.pk, kind, price)
    return plan


def plan_archive(*, plan: Plan) -> Plan:
    plan.is_archived = True
    plan.save(update_fields=["is_archived"])
    logger.info("Plan archived: plan_id=%s", plan.pk)
    return plan


def plan_unarchive(*, plan: Plan) -> Plan:
    plan.is_archived = False
    plan.save(update_fields=["is_archived"])
    logger.info("Plan unarchived: plan_id=%s", plan.pk)
    return plan


@transaction.atomic
def plan_delete(*, plan: Plan) -> None:
    """Delete a plan that was never assigned; assigned plans are archived instead."""
    # A month kept after its assignment was removed still refers to the plan.
    if plan.assignments.exists() or plan.expected_payments.exists():
        raise ValidationError(
            _("Cette formule a déjà été attribuée : archivez-la plutôt."),
            code="plan_assigned",
        )
    plan_id = plan.pk
    plan.delete()
    logger.info("Plan deleted: plan_id=%s", plan_id)


# --- Payers -----------------------------------------------------------------


def payer_create(
    *,
    profession: Profession,
    name: str,
    payment_reference_name: str,
    email: str,
    phone: str,
    notes: str,
) -> Payer:
    payer = Payer(
        profession=profession,
        name=name,
        payment_reference_name=payment_reference_name,
        email=email,
        phone=phone,
        notes=notes,
    )
    payer.full_clean()
    payer.save()
    logger.info("Payer created: payer_id=%s profession_id=%s", payer.pk, profession.pk)
    return payer


def payer_update(
    *,
    payer: Payer,
    name: str,
    payment_reference_name: str,
    email: str,
    phone: str,
    notes: str,
) -> Payer:
    payer.name = name
    payer.payment_reference_name = payment_reference_name
    payer.email = email
    payer.phone = phone
    payer.notes = notes
    payer.full_clean()
    payer.save()
    logger.info("Payer updated: payer_id=%s", payer.pk)
    return payer


@transaction.atomic
def payer_delete(*, payer: Payer) -> None:
    if not payer_is_deletable(payer=payer):
        raise ValidationError(
            _(
                "Ce payeur a encore des élèves, des formules ou des paiements : "
                "il ne peut pas être supprimé."
            ),
            code="payer_in_use",
        )
    payer_id = payer.pk
    payer.delete()
    logger.info("Payer deleted: payer_id=%s", payer_id)


# --- Students ---------------------------------------------------------------


@transaction.atomic
def student_create(
    *,
    profession: Profession,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    notes: str,
    start_date: date,
    end_date: date | None,
    status: Student.Status,
    payment_reference_name: str,
    payer: Payer | None,
    plan: Plan | None,
) -> Student:
    """Create a student; with a plan, assign it from the start month."""
    student = Student(
        profession=profession,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        notes=notes,
        start_date=start_date,
        end_date=end_date,
        status=status,
        payment_reference_name=payment_reference_name,
        payer=payer,
    )
    student.full_clean()
    student.save()
    logger.info(
        "Student created: student_id=%s profession_id=%s status=%s start=%s end=%s",
        student.pk,
        profession.pk,
        status,
        start_date,
        end_date,
    )
    if plan is not None:
        plan_assign(plan=plan, starts_on=month_start(start_date), student=student)
    return student


@transaction.atomic
def student_update(
    *,
    student: Student,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    notes: str,
    start_date: date,
    end_date: date | None,
    status: Student.Status,
    payment_reference_name: str,
    payer: Payer | None,
) -> Student:
    """Update a student. Dates cannot move past existing plan assignments.

    Expected payments follow the new dates: see `expected_payments_sync`.
    """
    assignments = list(plan_assignment_list(student=student))
    if assignments:
        earliest_start = min(assignment.starts_on for assignment in assignments)
        latest_start = max(assignment.starts_on for assignment in assignments)
        if earliest_start < month_start(start_date):
            raise ValidationError(
                _(
                    "Une formule commence avant la nouvelle date de début : "
                    "corrigez d'abord les attributions."
                ),
                code="assignment_before_start",
            )
        if end_date is not None and latest_start > month_start(end_date):
            raise ValidationError(
                _(
                    "Une formule commence après la nouvelle date de fin : "
                    "corrigez d'abord les attributions."
                ),
                code="assignment_after_end",
            )
    student.first_name = first_name
    student.last_name = last_name
    student.email = email
    student.phone = phone
    student.notes = notes
    student.start_date = start_date
    student.end_date = end_date
    student.status = status
    student.payment_reference_name = payment_reference_name
    student.payer = payer
    student.full_clean()
    student.save()
    logger.info(
        "Student updated: student_id=%s status=%s start=%s end=%s",
        student.pk,
        status,
        start_date,
        end_date,
    )
    expected_payments_sync(student=student)
    return student


# --- Pauses -----------------------------------------------------------------


def _student_pause_validate(pause: StudentPause) -> None:
    """Model rules plus the cross-record rule: pauses of a student never overlap."""
    pause.full_clean()
    for other in student_pause_list(student=pause.student):
        if other.pk == pause.pk:
            continue
        starts_before_other_ends = (
            other.ends_on is None or pause.starts_on <= other.ends_on
        )
        ends_after_other_starts = (
            pause.ends_on is None or pause.ends_on >= other.starts_on
        )
        if starts_before_other_ends and ends_after_other_starts:
            raise ValidationError(
                _("Cette pause chevauche une autre pause de l'élève."),
                code="overlap",
            )


@transaction.atomic
def student_pause_create(
    *, student: Student, starts_on: date, ends_on: date | None
) -> StudentPause:
    """Record a pause; months lying entirely within it are no longer expected."""
    pause = StudentPause(
        profession=student.profession,
        student=student,
        starts_on=starts_on,
        ends_on=ends_on,
    )
    _student_pause_validate(pause)
    pause.save()
    logger.info(
        "Student pause created: pause_id=%s student_id=%s starts_on=%s ends_on=%s",
        pause.pk,
        student.pk,
        starts_on,
        ends_on,
    )
    expected_payments_sync(student=student)
    return pause


@transaction.atomic
def student_pause_update(
    *, pause: StudentPause, starts_on: date, ends_on: date | None
) -> StudentPause:
    """Correct or end a pause; months that are due again are created."""
    pause.starts_on = starts_on
    pause.ends_on = ends_on
    _student_pause_validate(pause)
    pause.save()
    logger.info(
        "Student pause updated: pause_id=%s starts_on=%s ends_on=%s",
        pause.pk,
        starts_on,
        ends_on,
    )
    expected_payments_sync(student=pause.student)
    return pause


@transaction.atomic
def student_pause_delete(*, pause: StudentPause) -> None:
    student = pause.student
    pause_id = pause.pk
    pause.delete()
    logger.info("Student pause deleted: pause_id=%s", pause_id)
    expected_payments_sync(student=student)


# --- Plan assignments -------------------------------------------------------


def _assignment_target(
    *, student: Student | None, payer: Payer | None
) -> Student | Payer:
    if student is not None and payer is None:
        return student
    if payer is not None and student is None:
        return payer
    raise ValueError("Exactly one of student or payer is required.")


@transaction.atomic
def plan_assign(
    *,
    plan: Plan,
    starts_on: date,
    student: Student | None = None,
    payer: Payer | None = None,
) -> PlanAssignment:
    """Assign a plan to a student or a payer from `starts_on` (a month).

    Business rule: a plan change takes effect at the start of a month. The
    previous open assignment ends the month before; an assignment starting the
    same month is corrected in place; a later assignment must be removed first.
    """
    target = _assignment_target(student=student, payer=payer)
    validate_month_start(starts_on)
    if plan.is_archived:
        raise ValidationError(
            _("Une formule archivée ne peut plus être attribuée."),
            code="plan_archived",
        )
    if student is not None:
        if starts_on < month_start(student.start_date):
            raise ValidationError(
                _("La formule ne peut pas commencer avant le début des cours."),
                code="before_student_start",
            )
        if student.end_date is not None and starts_on > month_start(student.end_date):
            raise ValidationError(
                _("La formule ne peut pas commencer après la fin des cours."),
                code="after_student_end",
            )
    latest = plan_assignment_latest(student=student, payer=payer)
    if latest is not None:
        if latest.starts_on == starts_on:
            latest.plan = plan
            latest.full_clean()
            latest.save()
            logger.info(
                "Plan assignment replaced: assignment_id=%s plan_id=%s starts_on=%s",
                latest.pk,
                plan.pk,
                starts_on,
            )
            expected_payments_sync(student=student, payer=payer)
            return latest
        if latest.starts_on > starts_on:
            raise ValidationError(
                _("Une attribution ultérieure existe déjà : supprimez-la d'abord."),
                code="later_assignment_exists",
            )
        if latest.ends_on is not None and latest.ends_on >= starts_on:
            raise ValidationError(
                _(
                    "La formule précédente couvre encore ce mois : "
                    "choisissez un mois postérieur."
                ),
                code="overlaps_previous",
            )
        if latest.ends_on is None:
            latest.ends_on = month_add(starts_on, -1)
            latest.save(update_fields=["ends_on"])
    assignment = PlanAssignment(
        profession=target.profession,
        plan=plan,
        student=student,
        payer=payer,
        starts_on=starts_on,
    )
    assignment.full_clean()
    assignment.save()
    logger.info(
        "Plan assigned: assignment_id=%s plan_id=%s student_id=%s payer_id=%s "
        "starts_on=%s",
        assignment.pk,
        plan.pk,
        assignment.student_id,
        assignment.payer_id,
        starts_on,
    )
    expected_payments_sync(student=student, payer=payer)
    return assignment


@transaction.atomic
def plan_assignment_end(
    *, assignment: PlanAssignment, last_month: date
) -> PlanAssignment:
    """Close the latest assignment of its target at `last_month` (inclusive)."""
    validate_month_start(last_month)
    latest = plan_assignment_latest(student=assignment.student, payer=assignment.payer)
    if latest is None or latest.pk != assignment.pk:
        raise ValidationError(
            _("Seule la dernière attribution peut être terminée."),
            code="not_latest_assignment",
        )
    if last_month < assignment.starts_on:
        raise ValidationError(
            _(
                "Le dernier mois doit être postérieur ou égal "
                "au premier mois de la formule."
            ),
            code="end_before_start",
        )
    assignment.ends_on = last_month
    assignment.full_clean()
    assignment.save(update_fields=["ends_on"])
    logger.info(
        "Plan assignment ended: assignment_id=%s ends_on=%s", assignment.pk, last_month
    )
    expected_payments_sync(student=assignment.student, payer=assignment.payer)
    return assignment


@transaction.atomic
def plan_assignment_remove_latest(
    *, student: Student | None = None, payer: Payer | None = None
) -> None:
    """Remove the most recent assignment (a correction).

    The previous assignment is reopened only when it had been closed by the
    removed one; see `plan_assignment_reopened_by_removal`.
    """
    assignments = list(plan_assignment_list(student=student, payer=payer)[:2])
    if not assignments:
        raise ValidationError(
            _("Aucune attribution à supprimer."), code="no_assignment"
        )
    latest = assignments[0]
    reopened = plan_assignment_reopened_by_removal(assignments=assignments)
    latest_id = latest.pk
    latest.delete()
    logger.info("Plan assignment removed: assignment_id=%s", latest_id)
    if reopened is not None:
        reopened.ends_on = None
        reopened.save(update_fields=["ends_on"])
        logger.info("Plan assignment reopened: assignment_id=%s", reopened.pk)
    expected_payments_sync(student=student, payer=payer)

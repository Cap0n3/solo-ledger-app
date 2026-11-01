from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404

from core.apps.accounts.models import Profession
from core.utils.months import month_add, month_start

from .models import Payer, Plan, PlanAssignment, Student


def plan_list(*, profession: Profession) -> QuerySet[Plan]:
    return Plan.objects.filter(profession=profession)


def plan_assignable_list(
    *, profession: Profession, monthly_only: bool = False
) -> QuerySet[Plan]:
    """Plans that can still be assigned: not archived, monthly only for payers."""
    plans = plan_list(profession=profession).filter(is_archived=False)
    if monthly_only:
        plans = plans.filter(kind=Plan.Kind.MONTHLY)
    return plans


def plan_get(*, profession: Profession, plan_id: int) -> Plan:
    return get_object_or_404(plan_list(profession=profession), pk=plan_id)


@dataclass(frozen=True)
class PlanListItem:
    plan: Plan
    assignment_count: int


def plan_list_items(*, profession: Profession) -> list[PlanListItem]:
    """Rows of the plan list with how many times each plan was assigned."""
    count_rows = (
        PlanAssignment.objects.filter(plan__profession=profession)
        .values("plan_id")
        .annotate(total=Count("pk"))
    )
    counts: dict[int, int] = {}
    for row in count_rows:
        counts[row["plan_id"]] = row["total"]
    items: list[PlanListItem] = []
    for plan in plan_list(profession=profession):
        items.append(PlanListItem(plan=plan, assignment_count=counts.get(plan.pk, 0)))
    return items


def payer_list(*, profession: Profession) -> QuerySet[Payer]:
    return Payer.objects.filter(profession=profession)


def payer_get(*, profession: Profession, payer_id: int) -> Payer:
    return get_object_or_404(payer_list(profession=profession), pk=payer_id)


def student_list(
    *,
    profession: Profession,
    query: str = "",
    statuses: Iterable[Student.Status] = (),
    payer: Payer | None = None,
) -> QuerySet[Student]:
    """Students of the profession, optionally searched and filtered.

    Every word of `query` must match one of the name, e-mail or reference fields.
    """
    students = (
        Student.objects.filter(profession=profession)
        .select_related("payer")
        .prefetch_related("plan_assignments__plan")
    )
    status_list = list(statuses)
    if status_list:
        students = students.filter(status__in=status_list)
    if payer is not None:
        students = students.filter(payer=payer)
    for term in query.split():
        students = students.filter(
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
            | Q(payment_reference_name__icontains=term)
            | Q(payer__name__icontains=term)
        )
    return students


def student_get(*, profession: Profession, student_id: int) -> Student:
    return get_object_or_404(student_list(profession=profession), pk=student_id)


def plan_assignment_list(
    *, student: Student | None = None, payer: Payer | None = None
) -> QuerySet[PlanAssignment]:
    """Plan history of one target, most recent first.

    The target must come from a profession-filtered selector.
    """
    if (student is None) == (payer is None):
        raise ValueError("Exactly one of student or payer is required.")
    assignments = PlanAssignment.objects.select_related("plan")
    if student is not None:
        return assignments.filter(student=student)
    return assignments.filter(payer=payer)


def plan_assignment_latest(
    *, student: Student | None = None, payer: Payer | None = None
) -> PlanAssignment | None:
    return plan_assignment_list(student=student, payer=payer).first()


def plan_assignment_reopened_by_removal(
    *, assignments: Sequence[PlanAssignment]
) -> PlanAssignment | None:
    """The assignment that comes back into force if the latest one is removed.

    `assignments` is one target's history, most recent first. The previous
    assignment is reopened only when the latest one had closed it, i.e. it
    ended the month before the latest one started. Shared by the removal
    service and by the confirmation dialog, so both tell the same story.
    """
    if len(assignments) < 2:
        return None
    latest = assignments[0]
    previous = assignments[1]
    if previous.ends_on == month_add(latest.starts_on, -1):
        return previous
    return None


def plan_assignment_current(
    *, assignments: Iterable[PlanAssignment], month: date
) -> PlanAssignment | None:
    """The assignment covering `month`: started on or before it, not ended before it."""
    current: PlanAssignment | None = None
    for assignment in assignments:
        if assignment.starts_on > month:
            continue
        if assignment.ends_on is not None and assignment.ends_on < month:
            continue
        if current is None or assignment.starts_on > current.starts_on:
            current = assignment
    return current


def student_current_plan(*, student: Student, month: date) -> Plan | None:
    """The student's plan for `month`, none once the lessons have ended."""
    if student.end_date is not None and month_start(student.end_date) < month:
        return None
    assignment = plan_assignment_current(
        assignments=student.plan_assignments.all(), month=month
    )
    if assignment is None:
        return None
    return assignment.plan


def payer_current_plan(*, payer: Payer, month: date) -> Plan | None:
    assignment = plan_assignment_current(
        assignments=payer.plan_assignments.all(), month=month
    )
    if assignment is None:
        return None
    return assignment.plan


@dataclass(frozen=True)
class StudentListItem:
    student: Student
    current_plan: Plan | None


def student_list_items(
    *, students: Iterable[Student], month: date
) -> list[StudentListItem]:
    """Rows of the student list, with the plan in force for `month`."""
    items: list[StudentListItem] = []
    for student in students:
        current_plan = student_current_plan(student=student, month=month)
        items.append(StudentListItem(student=student, current_plan=current_plan))
    return items


@dataclass(frozen=True)
class PayerListItem:
    payer: Payer
    student_count: int
    current_plan: Plan | None


def payer_list_items(*, profession: Profession, month: date) -> list[PayerListItem]:
    """Rows of the payer list with their students and family plan for `month`."""
    payers = (
        payer_list(profession=profession)
        .annotate(student_total=Count("students", distinct=True))
        .prefetch_related("plan_assignments__plan")
    )
    items: list[PayerListItem] = []
    for payer in payers:
        student_total = payer.__dict__.get("student_total", 0)
        current_plan = payer_current_plan(payer=payer, month=month)
        items.append(
            PayerListItem(
                payer=payer, student_count=int(student_total), current_plan=current_plan
            )
        )
    return items

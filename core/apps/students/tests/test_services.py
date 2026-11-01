import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.models import Plan, PlanAssignment, Student
from core.apps.students.services import (
    payer_delete,
    plan_assign,
    plan_assignment_end,
    plan_assignment_remove_latest,
    plan_delete,
    student_create,
    student_update,
)

from .factories import PayerFactory, PlanAssignmentFactory, PlanFactory, StudentFactory

pytestmark = pytest.mark.django_db

SEPTEMBER = datetime.date(2026, 9, 1)
OCTOBER = datetime.date(2026, 10, 1)
NOVEMBER = datetime.date(2026, 11, 1)
DECEMBER = datetime.date(2026, 12, 1)


def student_fields(**overrides):
    fields = {
        "first_name": "Alice",
        "last_name": "Dupont",
        "email": "",
        "phone": "",
        "notes": "",
        "start_date": datetime.date(2026, 9, 15),
        "end_date": None,
        "status": Student.Status.ACTIVE,
        "payment_reference_name": "",
        "payer": None,
    }
    fields.update(overrides)
    return fields


def test_student_create_with_plan_assigns_it_from_the_start_month():
    profession = ProfessionFactory.create()
    plan = PlanFactory.create(profession=profession)

    student = student_create(profession=profession, plan=plan, **student_fields())

    assignment = student.plan_assignments.get()
    assert assignment.plan == plan
    assert assignment.starts_on == SEPTEMBER
    assert assignment.ends_on is None
    assert assignment.profession == profession


def test_student_create_rejects_payer_of_another_profession():
    profession = ProfessionFactory.create()
    foreign_payer = PayerFactory.create()

    with pytest.raises(ValidationError):
        student_create(
            profession=profession, plan=None, **student_fields(payer=foreign_payer)
        )

    assert not Student.objects.exists()


def test_plan_assign_closes_the_previous_open_assignment():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER)
    new_plan = PlanFactory.create(profession=first.profession)

    second = plan_assign(plan=new_plan, starts_on=NOVEMBER, student=first.student)

    first.refresh_from_db()
    assert first.ends_on == OCTOBER
    assert second.starts_on == NOVEMBER
    assert second.ends_on is None


def test_plan_assign_replaces_the_plan_when_same_month():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER)
    new_plan = PlanFactory.create(profession=first.profession)

    replaced = plan_assign(plan=new_plan, starts_on=SEPTEMBER, student=first.student)

    assert replaced.pk == first.pk
    assert replaced.plan == new_plan
    assert PlanAssignment.objects.count() == 1


def test_plan_assign_rejects_month_before_student_start():
    student = StudentFactory.create(start_date=datetime.date(2026, 9, 15))
    plan = PlanFactory.create(profession=student.profession)

    with pytest.raises(ValidationError) as excinfo:
        plan_assign(plan=plan, starts_on=datetime.date(2026, 8, 1), student=student)

    assert excinfo.value.code == "before_student_start"


def test_plan_assign_rejects_month_after_student_end():
    student = StudentFactory.create(
        start_date=SEPTEMBER, end_date=datetime.date(2026, 10, 20)
    )
    plan = PlanFactory.create(profession=student.profession)

    with pytest.raises(ValidationError) as excinfo:
        plan_assign(plan=plan, starts_on=NOVEMBER, student=student)

    assert excinfo.value.code == "after_student_end"


def test_plan_assign_rejects_when_a_later_assignment_exists():
    later = PlanAssignmentFactory.create(starts_on=NOVEMBER)
    plan = PlanFactory.create(profession=later.profession)

    with pytest.raises(ValidationError) as excinfo:
        plan_assign(plan=plan, starts_on=OCTOBER, student=later.student)

    assert excinfo.value.code == "later_assignment_exists"


def test_plan_assign_rejects_month_covered_by_an_ended_assignment():
    ended = PlanAssignmentFactory.create(starts_on=SEPTEMBER, ends_on=NOVEMBER)
    plan = PlanFactory.create(profession=ended.profession)

    with pytest.raises(ValidationError) as excinfo:
        plan_assign(plan=plan, starts_on=OCTOBER, student=ended.student)

    assert excinfo.value.code == "overlaps_previous"


def test_plan_assign_after_an_ended_assignment_leaves_a_gap():
    ended = PlanAssignmentFactory.create(starts_on=SEPTEMBER, ends_on=OCTOBER)
    plan = PlanFactory.create(profession=ended.profession)

    resumed = plan_assign(plan=plan, starts_on=DECEMBER, student=ended.student)

    ended.refresh_from_db()
    assert ended.ends_on == OCTOBER
    assert resumed.starts_on == DECEMBER


def test_plan_assign_rejects_archived_plan():
    student = StudentFactory.create()
    plan = PlanFactory.create(profession=student.profession, is_archived=True)

    with pytest.raises(ValidationError) as excinfo:
        plan_assign(plan=plan, starts_on=SEPTEMBER, student=student)

    assert excinfo.value.code == "plan_archived"


def test_plan_assign_rejects_plan_of_another_profession():
    student = StudentFactory.create()
    foreign_plan = PlanFactory.create()

    with pytest.raises(ValidationError):
        plan_assign(plan=foreign_plan, starts_on=SEPTEMBER, student=student)

    assert not PlanAssignment.objects.exists()


def test_plan_assign_rejects_single_lesson_plan_on_payer():
    payer = PayerFactory.create()
    plan = PlanFactory.create(profession=payer.profession, kind=Plan.Kind.SINGLE_LESSON)

    with pytest.raises(ValidationError):
        plan_assign(plan=plan, starts_on=SEPTEMBER, payer=payer)


def test_plan_assign_family_plan_on_payer():
    payer = PayerFactory.create()
    plan = PlanFactory.create(profession=payer.profession, price=Decimal("420.00"))

    assignment = plan_assign(plan=plan, starts_on=SEPTEMBER, payer=payer)

    assert assignment.payer == payer
    assert assignment.student is None
    assert assignment.profession == payer.profession


def test_plan_assignment_end_sets_the_last_month():
    assignment = PlanAssignmentFactory.create(starts_on=SEPTEMBER)

    plan_assignment_end(assignment=assignment, last_month=DECEMBER)

    assignment.refresh_from_db()
    assert assignment.ends_on == DECEMBER


def test_plan_assignment_end_rejects_month_before_start():
    assignment = PlanAssignmentFactory.create(starts_on=OCTOBER)

    with pytest.raises(ValidationError) as excinfo:
        plan_assignment_end(assignment=assignment, last_month=SEPTEMBER)

    assert excinfo.value.code == "end_before_start"


def test_plan_assignment_end_rejects_non_latest_assignment():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER)
    new_plan = PlanFactory.create(profession=first.profession)
    plan_assign(plan=new_plan, starts_on=NOVEMBER, student=first.student)

    with pytest.raises(ValidationError) as excinfo:
        plan_assignment_end(assignment=first, last_month=SEPTEMBER)

    assert excinfo.value.code == "not_latest_assignment"


def test_plan_assignment_remove_latest_reopens_the_previous_one_it_closed():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER)
    new_plan = PlanFactory.create(profession=first.profession)
    plan_assign(plan=new_plan, starts_on=NOVEMBER, student=first.student)

    plan_assignment_remove_latest(student=first.student)

    first.refresh_from_db()
    assert first.ends_on is None
    assert PlanAssignment.objects.count() == 1


def test_plan_assignment_remove_latest_keeps_a_previous_one_ended_by_hand():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER, ends_on=OCTOBER)
    new_plan = PlanFactory.create(profession=first.profession)
    plan_assign(plan=new_plan, starts_on=DECEMBER, student=first.student)

    plan_assignment_remove_latest(student=first.student)

    first.refresh_from_db()
    assert first.ends_on == OCTOBER


def test_plan_assignment_remove_latest_without_assignment_is_refused():
    student = StudentFactory.create()

    with pytest.raises(ValidationError):
        plan_assignment_remove_latest(student=student)


def test_student_update_rejects_start_date_after_first_assignment():
    student = StudentFactory.create(start_date=SEPTEMBER)
    PlanAssignmentFactory.create(
        profession=student.profession, student=student, starts_on=SEPTEMBER
    )

    with pytest.raises(ValidationError) as excinfo:
        student_update(
            student=student, **student_fields(start_date=datetime.date(2026, 10, 5))
        )

    assert excinfo.value.code == "assignment_before_start"


def test_student_update_rejects_end_date_before_latest_assignment():
    student = StudentFactory.create(start_date=SEPTEMBER)
    PlanAssignmentFactory.create(
        profession=student.profession, student=student, starts_on=NOVEMBER
    )

    with pytest.raises(ValidationError) as excinfo:
        student_update(
            student=student,
            **student_fields(
                start_date=SEPTEMBER, end_date=datetime.date(2026, 10, 15)
            ),
        )

    assert excinfo.value.code == "assignment_after_end"


def test_student_update_changes_fields_and_keeps_assignments():
    existing = StudentFactory.create(start_date=SEPTEMBER)
    PlanAssignmentFactory.create(
        profession=existing.profession, student=existing, starts_on=SEPTEMBER
    )
    payer = PayerFactory.create(profession=existing.profession)

    student = student_update(
        student=existing,
        **student_fields(
            start_date=SEPTEMBER,
            end_date=datetime.date(2027, 6, 30),
            status=Student.Status.ENDED,
            payer=payer,
        ),
    )

    assert student.status == Student.Status.ENDED
    assert student.payer == payer
    assert student.plan_assignments.count() == 1


def test_plan_delete_refuses_an_assigned_plan():
    assignment = PlanAssignmentFactory.create()

    with pytest.raises(ValidationError) as excinfo:
        plan_delete(plan=assignment.plan)

    assert excinfo.value.code == "plan_assigned"
    assert Plan.objects.filter(pk=assignment.plan.pk).exists()


def test_plan_delete_removes_an_unused_plan():
    plan = PlanFactory.create()

    plan_delete(plan=plan)

    assert not Plan.objects.filter(pk=plan.pk).exists()


def test_payer_delete_refuses_a_payer_with_students():
    payer = PayerFactory.create()
    StudentFactory.create(profession=payer.profession, payer=payer)

    with pytest.raises(ValidationError) as excinfo:
        payer_delete(payer=payer)

    assert excinfo.value.code == "payer_in_use"

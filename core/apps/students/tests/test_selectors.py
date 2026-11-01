import datetime

import pytest

from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.models import Plan, Student
from core.apps.students.selectors import (
    payer_current_plan,
    plan_assignable_list,
    plan_assignment_current,
    plan_assignment_reopened_by_removal,
    student_current_plan,
    student_list,
    student_list_items,
)

from .factories import PayerFactory, PlanAssignmentFactory, PlanFactory, StudentFactory

pytestmark = pytest.mark.django_db

SEPTEMBER = datetime.date(2026, 9, 1)
OCTOBER = datetime.date(2026, 10, 1)
NOVEMBER = datetime.date(2026, 11, 1)


def test_student_list_only_returns_students_of_the_profession():
    profession = ProfessionFactory.create()
    own = StudentFactory.create(profession=profession)
    StudentFactory.create()

    assert list(student_list(profession=profession)) == [own]


def test_student_list_search_matches_every_term_across_fields():
    profession = ProfessionFactory.create()
    alice = StudentFactory.create(
        profession=profession, first_name="Alice", last_name="Dupont"
    )
    StudentFactory.create(profession=profession, first_name="Bob", last_name="Dupont")
    payer = PayerFactory.create(profession=profession, name="Famille Martin")
    carla = StudentFactory.create(
        profession=profession, first_name="Carla", last_name="Rossi", payer=payer
    )

    assert list(student_list(profession=profession, query="alice dup")) == [alice]
    assert list(student_list(profession=profession, query="martin")) == [carla]
    assert student_list(profession=profession, query="dupont").count() == 2


def test_student_list_filters_by_statuses_and_payer():
    profession = ProfessionFactory.create()
    payer = PayerFactory.create(profession=profession)
    active = StudentFactory.create(profession=profession, payer=payer)
    paused = StudentFactory.create(profession=profession, status=Student.Status.PAUSED)
    StudentFactory.create(
        profession=profession,
        status=Student.Status.ENDED,
        end_date=datetime.date(2026, 12, 31),
    )

    current = student_list(
        profession=profession,
        statuses=(Student.Status.ACTIVE, Student.Status.PAUSED),
    )
    assert set(current) == {active, paused}
    assert list(student_list(profession=profession, payer=payer)) == [active]


def test_plan_assignment_current_picks_the_assignment_covering_the_month():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER, ends_on=OCTOBER)
    second = PlanAssignmentFactory.create(
        profession=first.profession, student=first.student, starts_on=NOVEMBER
    )
    assignments = [first, second]

    assert plan_assignment_current(assignments=assignments, month=OCTOBER) == first
    assert plan_assignment_current(assignments=assignments, month=NOVEMBER) == second
    assert (
        plan_assignment_current(
            assignments=assignments, month=datetime.date(2026, 8, 1)
        )
        is None
    )


def test_plan_assignment_reopened_by_removal_is_the_one_the_latest_closed():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER, ends_on=OCTOBER)
    second = PlanAssignmentFactory.create(
        profession=first.profession, student=first.student, starts_on=NOVEMBER
    )

    assert plan_assignment_reopened_by_removal(assignments=[second, first]) == first


def test_plan_assignment_reopened_by_removal_ignores_one_ended_by_hand():
    first = PlanAssignmentFactory.create(starts_on=SEPTEMBER, ends_on=SEPTEMBER)
    second = PlanAssignmentFactory.create(
        profession=first.profession, student=first.student, starts_on=NOVEMBER
    )

    assert plan_assignment_reopened_by_removal(assignments=[second, first]) is None
    assert plan_assignment_reopened_by_removal(assignments=[second]) is None


def test_student_current_plan_is_none_after_the_end_date():
    student = StudentFactory.create(
        start_date=SEPTEMBER, end_date=datetime.date(2026, 10, 15)
    )
    assignment = PlanAssignmentFactory.create(
        profession=student.profession, student=student, starts_on=SEPTEMBER
    )

    assert student_current_plan(student=student, month=OCTOBER) == assignment.plan
    assert student_current_plan(student=student, month=NOVEMBER) is None


def test_payer_current_plan():
    payer = PayerFactory.create()
    assignment = PlanAssignmentFactory.create(
        profession=payer.profession, student=None, payer=payer, starts_on=SEPTEMBER
    )

    assert payer_current_plan(payer=payer, month=OCTOBER) == assignment.plan
    assert payer_current_plan(payer=payer, month=datetime.date(2026, 8, 1)) is None


def test_plan_assignable_list_excludes_archived_and_optionally_single_lesson():
    profession = ProfessionFactory.create()
    monthly = PlanFactory.create(profession=profession)
    single = PlanFactory.create(profession=profession, kind=Plan.Kind.SINGLE_LESSON)
    PlanFactory.create(profession=profession, is_archived=True)
    PlanFactory.create()

    assert set(plan_assignable_list(profession=profession)) == {monthly, single}
    assert list(plan_assignable_list(profession=profession, monthly_only=True)) == [
        monthly
    ]


def test_student_list_items_carry_the_plan_in_force():
    with_plan = StudentFactory.create()
    assignment = PlanAssignmentFactory.create(
        profession=with_plan.profession, student=with_plan, starts_on=SEPTEMBER
    )
    without_plan = StudentFactory.create(profession=with_plan.profession)

    items = student_list_items(
        students=student_list(profession=with_plan.profession), month=OCTOBER
    )

    by_student = {item.student: item.current_plan for item in items}
    assert by_student[with_plan] == assignment.plan
    assert by_student[without_plan] is None

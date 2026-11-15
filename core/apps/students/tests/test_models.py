import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.models import Plan, PlanAssignment, Student

from .factories import (
    PayerFactory,
    PlanAssignmentFactory,
    PlanFactory,
    StudentFactory,
    StudentPauseFactory,
)

pytestmark = pytest.mark.django_db


def test_student_end_date_cannot_precede_start_date():
    student = StudentFactory.create(start_date=datetime.date(2026, 9, 1))
    student.end_date = datetime.date(2026, 8, 1)

    with pytest.raises(ValidationError) as excinfo:
        student.full_clean()

    assert "end_date" in excinfo.value.error_dict


def test_ended_student_requires_end_date():
    student = StudentFactory.create()
    student.status = Student.Status.ENDED

    with pytest.raises(ValidationError) as excinfo:
        student.full_clean()

    assert "end_date" in excinfo.value.error_dict


def test_student_payer_must_belong_to_same_profession():
    student = StudentFactory.create()
    student.payer = PayerFactory.create()

    with pytest.raises(ValidationError) as excinfo:
        student.full_clean()

    assert "payer" in excinfo.value.error_dict


def test_student_reference_name_prefers_payer_then_own_then_full_name():
    profession = ProfessionFactory.create()
    student = StudentFactory.create(
        profession=profession, first_name="Alice", last_name="Dupont"
    )
    assert student.reference_name == "Alice Dupont"

    student.payment_reference_name = "DUPONT MARC"
    assert student.reference_name == "DUPONT MARC"

    student.payer = PayerFactory.create(
        profession=profession, name="Famille Dupont", payment_reference_name="DUPONT M."
    )
    assert student.reference_name == "DUPONT M."


def test_plan_assignment_requires_exactly_one_target():
    profession = ProfessionFactory.create()
    plan = PlanFactory.create(profession=profession)

    with pytest.raises(IntegrityError), transaction.atomic():
        PlanAssignment.objects.create(
            profession=profession, plan=plan, starts_on=datetime.date(2026, 9, 1)
        )


def test_plan_assignment_is_unique_per_student_and_month():
    assignment = PlanAssignmentFactory.create()

    with pytest.raises(IntegrityError), transaction.atomic():
        PlanAssignment.objects.create(
            profession=assignment.profession,
            plan=assignment.plan,
            student=assignment.student,
            starts_on=assignment.starts_on,
        )


def test_plan_assignment_rejects_single_lesson_plan_on_payer():
    profession = ProfessionFactory.create()
    plan = PlanFactory.create(profession=profession, kind=Plan.Kind.SINGLE_LESSON)
    assignment = PlanAssignmentFactory.build(
        profession=profession, plan=plan, for_payer=True
    )
    assignment.payer = PayerFactory.create(profession=profession)

    with pytest.raises(ValidationError) as excinfo:
        assignment.full_clean()

    assert "plan" in excinfo.value.error_dict


def test_plan_assignment_rejects_plan_of_another_profession():
    assignment = PlanAssignmentFactory.create()
    assignment.plan = PlanFactory.create()

    with pytest.raises(ValidationError) as excinfo:
        assignment.full_clean()

    assert "plan" in excinfo.value.error_dict


def test_plan_assignment_rejects_target_of_another_profession():
    assignment = PlanAssignmentFactory.create()
    assignment.student = StudentFactory.create()

    with pytest.raises(ValidationError) as excinfo:
        assignment.full_clean()

    assert "student" in excinfo.value.error_dict


def test_plan_assignment_months_must_be_first_of_month():
    assignment = PlanAssignmentFactory.create()
    assignment.starts_on = datetime.date(2026, 9, 15)

    with pytest.raises(ValidationError) as excinfo:
        assignment.full_clean()

    assert "starts_on" in excinfo.value.error_dict


def test_plan_assignment_target_is_the_student_or_the_payer():
    student_assignment = PlanAssignmentFactory.create()
    payer_assignment = PlanAssignmentFactory.create(for_payer=True)

    assert student_assignment.target == student_assignment.student
    assert payer_assignment.target == payer_assignment.payer
    assert payer_assignment.profession == payer_assignment.payer.profession


def test_paused_status_cannot_be_stored():
    student = StudentFactory.create()
    student.status = Student.Status.PAUSED

    with pytest.raises(ValidationError) as excinfo:
        student.full_clean()

    assert "status" in excinfo.value.error_dict


def test_pause_covers_only_months_lying_entirely_within_it():
    pause = StudentPauseFactory.build(
        starts_on=datetime.date(2027, 1, 15), ends_on=datetime.date(2027, 3, 10)
    )

    assert not pause.covers_whole_month(datetime.date(2027, 1, 1))
    assert pause.covers_whole_month(datetime.date(2027, 2, 1))
    assert not pause.covers_whole_month(datetime.date(2027, 3, 1))


def test_open_pause_covers_every_later_month():
    pause = StudentPauseFactory.build(starts_on=datetime.date(2027, 1, 1), ends_on=None)

    assert pause.covers_whole_month(datetime.date(2027, 1, 1))
    assert pause.covers_whole_month(datetime.date(2028, 6, 1))
    assert pause.covers_day(datetime.date(2030, 1, 1))


def test_pause_end_cannot_precede_its_start():
    pause = StudentPauseFactory.create()
    pause.ends_on = datetime.date(2027, 1, 1)

    with pytest.raises(ValidationError) as excinfo:
        pause.full_clean()

    assert "ends_on" in excinfo.value.error_dict

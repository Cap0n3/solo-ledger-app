"""Factories rooted on `profession`: pass `profession=` together with any
related instance (`student=`, `plan=`, `payer=`) so every record shares it."""

import datetime
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.models import (
    Payer,
    Plan,
    PlanAssignment,
    Student,
    StudentPause,
)
from core.utils.months import month_start


class PlanFactory(DjangoModelFactory[Plan]):
    class Meta:
        model = Plan

    profession = factory.SubFactory(ProfessionFactory)
    name = factory.Sequence(lambda n: f"Plan {n}")
    price = Decimal("280.00")
    kind = Plan.Kind.MONTHLY


class PayerFactory(DjangoModelFactory[Payer]):
    class Meta:
        model = Payer

    profession = factory.SubFactory(ProfessionFactory)
    name = factory.Sequence(lambda n: f"[TEST] Payer {n}")


class StudentFactory(DjangoModelFactory[Student]):
    class Meta:
        model = Student

    profession = factory.SubFactory(ProfessionFactory)
    first_name = factory.Sequence(lambda n: f"[TEST] Student {n}")
    last_name = "Example"
    start_date = datetime.date(2026, 9, 1)


class PlanAssignmentFactory(DjangoModelFactory[PlanAssignment]):
    class Meta:
        model = PlanAssignment

    profession = factory.SubFactory(ProfessionFactory)
    plan = factory.SubFactory(
        PlanFactory, profession=factory.SelfAttribute("..profession")
    )
    student = factory.SubFactory(
        StudentFactory, profession=factory.SelfAttribute("..profession")
    )
    payer = None
    starts_on = factory.LazyAttribute(
        lambda assignment: (
            month_start(assignment.student.start_date)
            if assignment.student is not None
            else datetime.date(2026, 9, 1)
        )
    )

    class Params:
        for_payer = factory.Trait(
            student=None,
            payer=factory.SubFactory(
                PayerFactory, profession=factory.SelfAttribute("..profession")
            ),
        )


class StudentPauseFactory(DjangoModelFactory[StudentPause]):
    class Meta:
        model = StudentPause

    profession = factory.SubFactory(ProfessionFactory)
    student = factory.SubFactory(
        StudentFactory, profession=factory.SelfAttribute("..profession")
    )
    starts_on = datetime.date(2027, 1, 15)
    ends_on = datetime.date(2027, 3, 10)

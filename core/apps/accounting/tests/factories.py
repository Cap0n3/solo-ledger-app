"""Factories rooted on `profession`: pass `profession=` together with any
related instance (`student=`, `payer=`, `plan=`) so every record shares it."""

import datetime
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from core.apps.accounting.models import (
    ExpectedPayment,
    Payment,
    PaymentAllocation,
    PaymentMethod,
)
from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.tests.factories import (
    PayerFactory,
    PlanFactory,
    StudentFactory,
)


class ExpectedPaymentFactory(DjangoModelFactory[ExpectedPayment]):
    class Meta:
        model = ExpectedPayment

    profession = factory.SubFactory(ProfessionFactory)
    student = factory.SubFactory(
        StudentFactory, profession=factory.SelfAttribute("..profession")
    )
    payer = None
    plan = factory.SubFactory(
        PlanFactory, profession=factory.SelfAttribute("..profession")
    )
    month = datetime.date(2026, 9, 1)
    amount = Decimal("280.00")

    class Params:
        for_payer = factory.Trait(
            student=None,
            payer=factory.SubFactory(
                PayerFactory, profession=factory.SelfAttribute("..profession")
            ),
        )


class PaymentFactory(DjangoModelFactory[Payment]):
    class Meta:
        model = Payment

    profession = factory.SubFactory(ProfessionFactory)
    kind = Payment.Kind.MONTHLY
    student = factory.SubFactory(
        StudentFactory, profession=factory.SelfAttribute("..profession")
    )
    payer = None
    received_on = datetime.date(2026, 8, 28)
    amount = Decimal("280.00")
    method = PaymentMethod.BANK_TRANSFER

    class Params:
        one_off = factory.Trait(
            kind=Payment.Kind.ONE_OFF,
            student=None,
            label="[TEST] Gift voucher",
        )


class PaymentAllocationFactory(DjangoModelFactory[PaymentAllocation]):
    class Meta:
        model = PaymentAllocation

    payment = factory.SubFactory(PaymentFactory)
    expected_payment = factory.SubFactory(ExpectedPaymentFactory)
    amount = Decimal("280.00")

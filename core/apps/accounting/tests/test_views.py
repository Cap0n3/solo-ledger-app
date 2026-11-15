import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from core.apps.accounting.models import Payment, PaymentMethod
from core.apps.accounting.selectors import expected_payment_list
from core.apps.accounting.services import one_off_income_create, payment_create
from core.apps.accounts.tests.factories import LessonYearFactory, ProfessionFactory
from core.apps.students.services import plan_assign
from core.apps.students.tests.factories import (
    PayerFactory,
    PlanFactory,
    StudentFactory,
)

pytestmark = pytest.mark.django_db

URL_NAMES = (
    "accounting:ledger_entry_list",
    "accounting:expense_list",
    "accounting:payment_create",
    "accounting:one_off_income_create",
)
SEPTEMBER = datetime.date(2026, 9, 1)
OCTOBER = datetime.date(2026, 10, 1)
PRICE = Decimal("280.00")


def make_student(profession=None, **fields):
    """A student with a 280 CHF monthly plan in a 2026-2027 lesson year."""
    if profession is None:
        profession = ProfessionFactory.create()
    if not profession.lessonyear_set.exists():
        LessonYearFactory.create(profession=profession)
    student = StudentFactory.create(profession=profession, **fields)
    plan = PlanFactory.create(profession=profession, price=PRICE)
    plan_assign(plan=plan, starts_on=SEPTEMBER, student=student)
    return student


def expected_for(student, month):
    return expected_payment_list(student=student).get(month=month)


def make_payment(student, received_on=datetime.date(2026, 8, 28)):
    return payment_create(
        profession=student.profession,
        received_on=received_on,
        amount=PRICE,
        method=PaymentMethod.BANK_TRANSFER,
        notes="",
        allocations=[],
        student=student,
    )


def payment_data(target, /, **overrides):
    data = {
        "student": str(target.pk),
        "payer": "",
        "received_on": "2026-08-28",
        "amount": "280.00",
        "method": "bank_transfer",
        "notes": "",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("url_name", URL_NAMES)
def test_pages_redirect_anonymous_user_to_login(client, url_name):
    response = client.get(reverse(url_name))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.parametrize("url_name", URL_NAMES)
def test_pages_render_with_the_users_own_profession(client, url_name):
    profession = ProfessionFactory.create(name="Cours de guitare")
    client.force_login(profession.user)

    response = client.get(reverse(url_name))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()


# --- Payment form -----------------------------------------------------------


def test_payment_form_first_proposes_the_allocation_then_saves_it(client):
    student = make_student()
    client.force_login(student.profession.user)
    url = reverse("accounting:payment_create")

    proposed = client.post(url, payment_data(student, action="propose"))

    assert proposed.status_code == 200
    assert Payment.objects.count() == 0
    september = expected_for(student, SEPTEMBER)
    rows = proposed.context["allocation_rows"]
    assert rows[0].month.expected_payment == september
    assert rows[0].field.initial == PRICE
    assert rows[1].field.initial is None

    saved = client.post(
        url,
        payment_data(
            student,
            action="save",
            proposed_for=proposed.context["proposed_for"],
            **{f"month_{september.pk}": "280.00"},
        ),
    )

    assert saved.status_code == 302
    assert saved.url == reverse("students:student_detail", args=[student.pk])
    payment = Payment.objects.get()
    assert payment.allocations.get().expected_payment == september


def test_payment_is_not_saved_when_it_changed_since_the_proposal(client):
    student = make_student()
    client.force_login(student.profession.user)
    url = reverse("accounting:payment_create")
    proposed = client.post(url, payment_data(student, action="propose"))
    september = expected_for(student, SEPTEMBER)

    response = client.post(
        url,
        payment_data(
            student,
            amount="560.00",
            action="save",
            proposed_for=proposed.context["proposed_for"],
            **{f"month_{september.pk}": "280.00"},
        ),
    )

    assert response.status_code == 200
    assert Payment.objects.count() == 0
    assert response.context["is_proposal_refreshed"]
    proposed_amounts = [
        row.field.initial for row in response.context["allocation_rows"]
    ]
    assert proposed_amounts[:3] == [PRICE, PRICE, None]


def test_payment_form_shows_the_warnings_of_the_proposal(client):
    student = make_student()
    client.force_login(student.profession.user)

    response = client.post(
        reverse("accounting:payment_create"),
        payment_data(student, amount="300.00", action="propose"),
    )

    assert "avoir non attribué" in response.content.decode()


def test_payment_needs_a_student_or_a_payer_but_not_both(client):
    student = make_student()
    payer = PayerFactory.create(profession=student.profession)
    client.force_login(student.profession.user)
    url = reverse("accounting:payment_create")

    neither = client.post(url, payment_data(student, student="", action="propose"))
    both = client.post(
        url, payment_data(student, payer=str(payer.pk), action="propose")
    )

    assert neither.context["form"].non_field_errors()
    assert both.context["form"].non_field_errors()


def test_payment_form_is_prefilled_from_the_student_page(client):
    student = make_student()
    client.force_login(student.profession.user)

    response = client.get(reverse("accounting:payment_create"), {"student": student.pk})

    assert response.context["form"].initial["student"] == student


def test_payment_update_shows_and_replaces_the_current_allocation(client):
    student = make_student()
    payment = make_payment(student)
    client.force_login(student.profession.user)
    url = reverse("accounting:payment_update", args=[payment.pk])
    october = expected_for(student, OCTOBER)

    shown = client.get(url)
    saved = client.post(
        url,
        payment_data(
            student,
            action="save",
            proposed_for=shown.context["proposed_for"],
            **{f"month_{october.pk}": "280.00"},
        ),
    )

    assert saved.status_code == 302
    assert payment.allocations.get().expected_payment == october


def test_payment_delete_asks_for_confirmation_then_deletes(client):
    student = make_student()
    payment = make_payment(student)
    client.force_login(student.profession.user)
    url = reverse("accounting:payment_delete", args=[payment.pk])

    confirmation = client.get(url)
    assert confirmation.status_code == 200
    assert Payment.objects.count() == 1

    response = client.post(url)

    assert response.status_code == 302
    assert Payment.objects.count() == 0


# --- One-off income ---------------------------------------------------------


def test_one_off_income_is_created_without_a_student(client):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.post(
        reverse("accounting:one_off_income_create"),
        {
            "label": "[TEST] Bon cadeau 5 cours",
            "received_on": "2026-09-03",
            "amount": "450.00",
            "method": "bank_transfer",
            "student": "",
            "notes": "",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounting:ledger_entry_list")
    income = Payment.objects.get()
    assert income.is_one_off
    assert income.student is None
    assert income.profession == profession


# --- Expected payments ------------------------------------------------------


def test_month_can_be_cancelled_restored_and_its_amount_corrected(client):
    student = make_student()
    client.force_login(student.profession.user)
    september = expected_for(student, SEPTEMBER)

    client.post(
        reverse("accounting:expected_payment_cancel", args=[september.pk]),
        {"reason": "Accident"},
    )
    september.refresh_from_db()
    assert september.is_cancelled
    assert september.cancellation_reason == "Accident"

    client.post(reverse("accounting:expected_payment_restore", args=[september.pk]))
    september.refresh_from_db()
    assert not september.is_cancelled

    client.post(
        reverse("accounting:expected_payment_amount_update", args=[september.pk]),
        {"amount": "140.00"},
    )
    september.refresh_from_db()
    assert september.amount == Decimal("140.00")
    assert september.is_amount_manual


def test_cancelling_a_paid_month_shows_the_refusal(client):
    student = make_student()
    september = expected_for(student, SEPTEMBER)
    payment = make_payment(student)
    payment.allocations.create(expected_payment=september, amount=PRICE)
    client.force_login(student.profession.user)

    response = client.post(
        reverse("accounting:expected_payment_cancel", args=[september.pk]),
        {"reason": ""},
    )

    assert response.status_code == 200
    assert response.context["form"].non_field_errors()


# --- Ledger -----------------------------------------------------------------


def test_ledger_lists_income_of_the_fiscal_year_it_was_received(client):
    student = make_student()
    make_payment(student, received_on=datetime.date(2026, 12, 28))
    make_payment(student, received_on=datetime.date(2027, 1, 5))
    one_off_income_create(
        profession=student.profession,
        received_on=datetime.date(2026, 9, 3),
        amount=Decimal("90.00"),
        method=PaymentMethod.CASH,
        label="[TEST] Cours à la carte",
        notes="",
        student=None,
    )
    client.force_login(student.profession.user)

    response = client.get(reverse("accounting:ledger_entry_list"), {"year": "2026"})

    assert response.context["fiscal_year"] == 2026
    assert response.context["income_total"] == Decimal("370.00")
    assert len(response.context["entries"]) == 2
    assert "[TEST] Cours à la carte" in response.content.decode()


# --- Data separation --------------------------------------------------------


def test_ledger_never_shows_another_professions_income(client):
    own = make_student()
    foreign = make_student()
    make_payment(own)
    one_off_income_create(
        profession=foreign.profession,
        received_on=datetime.date(2026, 8, 28),
        amount=Decimal("450.00"),
        method=PaymentMethod.CASH,
        label="[TEST] Foreign voucher",
        notes="",
        student=None,
    )
    client.force_login(own.profession.user)

    response = client.get(reverse("accounting:ledger_entry_list"), {"year": "2026"})

    assert response.context["income_total"] == PRICE
    assert "[TEST] Foreign voucher" not in response.content.decode()


def test_payment_and_month_pages_return_404_for_another_profession(client):
    profession = ProfessionFactory.create()
    foreign = make_student()
    foreign_payment = make_payment(foreign)
    foreign_income = one_off_income_create(
        profession=foreign.profession,
        received_on=datetime.date(2026, 8, 28),
        amount=Decimal("90.00"),
        method=PaymentMethod.CASH,
        label="[TEST] Foreign",
        notes="",
        student=None,
    )
    foreign_month = expected_for(foreign, SEPTEMBER)
    client.force_login(profession.user)

    get_urls = (
        reverse("accounting:payment_update", args=[foreign_payment.pk]),
        reverse("accounting:payment_delete", args=[foreign_payment.pk]),
        reverse("accounting:one_off_income_update", args=[foreign_income.pk]),
        reverse("accounting:expected_payment_cancel", args=[foreign_month.pk]),
        reverse("accounting:expected_payment_amount_update", args=[foreign_month.pk]),
        reverse("accounting:payment_create") + f"?student={foreign.pk}",
        reverse("accounting:one_off_income_create") + f"?student={foreign.pk}",
    )
    for url in get_urls:
        assert client.get(url).status_code == 404, url
    post_urls = (
        reverse("accounting:payment_delete", args=[foreign_payment.pk]),
        reverse("accounting:expected_payment_restore", args=[foreign_month.pk]),
        reverse("accounting:expected_payment_cancel", args=[foreign_month.pk]),
    )
    for url in post_urls:
        assert client.post(url).status_code == 404, url
    assert Payment.objects.filter(pk=foreign_payment.pk).exists()
    foreign_month.refresh_from_db()
    assert not foreign_month.is_cancelled


def test_another_professions_student_or_payer_is_a_field_error(client):
    profession = ProfessionFactory.create()
    foreign = make_student()
    foreign_payer = PayerFactory.create(profession=foreign.profession)
    client.force_login(profession.user)

    as_student = client.post(
        reverse("accounting:payment_create"), payment_data(foreign, action="propose")
    )
    as_payer = client.post(
        reverse("accounting:payment_create"),
        payment_data(foreign, student="", payer=str(foreign_payer.pk), action="save"),
    )
    as_income = client.post(
        reverse("accounting:one_off_income_create"),
        {
            "label": "[TEST] Voucher",
            "received_on": "2026-09-03",
            "amount": "90.00",
            "method": "cash",
            "student": str(foreign.pk),
            "notes": "",
        },
    )

    assert "student" in as_student.context["form"].errors
    assert "payer" in as_payer.context["form"].errors
    assert "student" in as_income.context["form"].errors
    assert Payment.objects.count() == 0


def test_a_posted_month_of_another_student_is_ignored(client):
    """Allocation inputs exist only for the months of the chosen student."""
    own = make_student()
    foreign = make_student()
    foreign_month = expected_for(foreign, SEPTEMBER)
    client.force_login(own.profession.user)
    url = reverse("accounting:payment_create")
    proposed = client.post(url, payment_data(own, action="propose"))

    client.post(
        url,
        payment_data(
            own,
            action="save",
            proposed_for=proposed.context["proposed_for"],
            **{f"month_{foreign_month.pk}": "280.00"},
        ),
    )

    assert foreign_month.allocations.count() == 0
    assert Payment.objects.get().allocations.count() == 0

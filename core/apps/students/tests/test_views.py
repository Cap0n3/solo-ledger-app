from decimal import Decimal

import pytest
from django.urls import reverse

from core.apps.accounts.tests.factories import ProfessionFactory
from core.apps.students.models import Plan

from .factories import PlanAssignmentFactory, PlanFactory

pytestmark = pytest.mark.django_db

PUBLIC_PAGES = ("students:student_list", "students:plan_list", "students:plan_create")


@pytest.mark.parametrize("url_name", PUBLIC_PAGES)
def test_pages_redirect_anonymous_user_to_login(client, url_name):
    response = client.get(reverse(url_name))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.parametrize("url_name", PUBLIC_PAGES)
def test_pages_render_with_the_users_own_profession(client, url_name):
    profession = ProfessionFactory.create(name="Cours de guitare")
    client.force_login(profession.user)

    response = client.get(reverse(url_name))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()


# --- Plans ------------------------------------------------------------------


def test_plan_list_shows_only_the_professions_plans(client):
    profession = ProfessionFactory.create()
    PlanFactory.create(
        profession=profession, name="Hebdomadaire", price=Decimal("1280.5")
    )
    PlanFactory.create(name="Formule étrangère")
    client.force_login(profession.user)

    response = client.get(reverse("students:plan_list"))

    content = response.content.decode()
    assert "Hebdomadaire" in content
    assert "1’280.50 CHF" in content
    assert "Formule étrangère" not in content
    assert response.context["nav_section"] == "plans"


def test_plan_create_adds_a_plan_to_the_current_profession(client):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.post(
        reverse("students:plan_create"),
        {
            "name": "Bimensuelle",
            "description": "Un cours toutes les deux semaines",
            "price": "160.00",
            "kind": Plan.Kind.MONTHLY,
        },
    )

    assert response.status_code == 302
    plan = Plan.objects.get(name="Bimensuelle")
    assert plan.profession == profession
    assert plan.price == Decimal("160.00")


def test_plan_create_rejects_a_duplicate_name_with_a_form_error(client):
    plan = PlanFactory.create(name="Hebdomadaire")
    client.force_login(plan.profession.user)

    response = client.post(
        reverse("students:plan_create"),
        {"name": "Hebdomadaire", "description": "", "price": "280", "kind": "monthly"},
    )

    assert response.status_code == 200
    assert response.context["form"].errors
    assert Plan.objects.count() == 1


def test_plan_update_changes_the_price(client):
    plan = PlanFactory.create(price=Decimal("260.00"))
    client.force_login(plan.profession.user)

    response = client.post(
        reverse("students:plan_update", args=[plan.pk]),
        {"name": plan.name, "description": "", "price": "280.00", "kind": "monthly"},
    )

    assert response.status_code == 302
    plan.refresh_from_db()
    assert plan.price == Decimal("280.00")


def test_plan_pages_return_404_for_another_professions_plan(client):
    foreign_plan = PlanFactory.create()
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    assert (
        client.get(reverse("students:plan_update", args=[foreign_plan.pk])).status_code
        == 404
    )
    assert (
        client.post(reverse("students:plan_delete", args=[foreign_plan.pk])).status_code
        == 404
    )
    assert Plan.objects.filter(pk=foreign_plan.pk).exists()


def test_plan_archive_toggle_flips_the_flag(client):
    plan = PlanFactory.create()
    client.force_login(plan.profession.user)

    client.post(reverse("students:plan_archive_toggle", args=[plan.pk]))
    plan.refresh_from_db()
    assert plan.is_archived

    client.post(reverse("students:plan_archive_toggle", args=[plan.pk]))
    plan.refresh_from_db()
    assert not plan.is_archived


def test_plan_delete_is_refused_for_an_assigned_plan(client):
    assignment = PlanAssignmentFactory.create()
    client.force_login(assignment.profession.user)

    response = client.post(
        reverse("students:plan_delete", args=[assignment.plan.pk]), follow=True
    )

    assert Plan.objects.filter(pk=assignment.plan.pk).exists()
    assert "archivez-la" in response.content.decode()


def test_plan_delete_removes_an_unused_plan(client):
    plan = PlanFactory.create()
    client.force_login(plan.profession.user)

    response = client.post(reverse("students:plan_delete", args=[plan.pk]))

    assert response.status_code == 302
    assert not Plan.objects.filter(pk=plan.pk).exists()


# --- Students ---------------------------------------------------------------


def test_student_list_hides_ended_students_by_default_and_filters(client):
    import datetime

    from core.apps.students.models import Student

    from .factories import StudentFactory

    profession = ProfessionFactory.create()
    StudentFactory.create(profession=profession, first_name="Alice", last_name="Active")
    StudentFactory.create(
        profession=profession,
        first_name="Paul",
        last_name="Pause",
        status=Student.Status.PAUSED,
    )
    StudentFactory.create(
        profession=profession,
        first_name="Tom",
        last_name="Terminé",
        status=Student.Status.ENDED,
        end_date=datetime.date(2026, 6, 30),
    )
    StudentFactory.create(first_name="Zoé", last_name="Étrangère")
    client.force_login(profession.user)

    default_page = client.get(reverse("students:student_list")).content.decode()
    assert "Alice Active" in default_page
    assert "Paul Pause" in default_page
    assert "Tom Terminé" not in default_page
    assert "Zoé Étrangère" not in default_page

    ended_page = client.get(
        reverse("students:student_list"), {"status": "ended"}
    ).content.decode()
    assert "Tom Terminé" in ended_page
    assert "Alice Active" not in ended_page

    searched = client.get(
        reverse("students:student_list"), {"q": "pau", "status": "all"}
    ).content.decode()
    assert "Paul Pause" in searched
    assert "Alice Active" not in searched


def test_student_list_returns_only_the_table_for_htmx_requests(client):
    from .factories import StudentFactory

    student = StudentFactory.create(first_name="Alice", last_name="Dupont")
    client.force_login(student.profession.user)

    partial = client.get(
        reverse("students:student_list"), headers={"HX-Request": "true"}
    )
    restored = client.get(
        reverse("students:student_list"),
        headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )

    assert "<html" not in partial.content.decode()
    assert "Alice Dupont" in partial.content.decode()
    assert "HX-Request" in partial.headers["Vary"]
    assert "<html" in restored.content.decode()


def test_student_list_paginates(client):
    from .factories import StudentFactory

    profession = ProfessionFactory.create()
    StudentFactory.create_batch(26, profession=profession)
    client.force_login(profession.user)

    first_page = client.get(reverse("students:student_list"))
    second_page = client.get(reverse("students:student_list"), {"page": 2})

    assert len(first_page.context["items"]) == 25
    assert len(second_page.context["items"]) == 1
    assert "page=2" in first_page.content.decode()


def test_student_create_with_plan_assigns_it_and_redirects_to_the_detail(client):
    from core.apps.students.models import Student

    profession = ProfessionFactory.create()
    plan = PlanFactory.create(profession=profession)
    client.force_login(profession.user)

    response = client.post(
        reverse("students:student_create"),
        {
            "first_name": "Alice",
            "last_name": "Dupont",
            "email": "alice@example.com",
            "phone": "",
            "start_date": "2026-09-15",
            "end_date": "",
            "status": "active",
            "payer": "",
            "payment_reference_name": "",
            "plan": plan.pk,
            "notes": "",
        },
    )

    student = Student.objects.get(last_name="Dupont")
    assert response.status_code == 302
    assert response.url == reverse("students:student_detail", args=[student.pk])
    assert student.profession == profession
    assert student.plan_assignments.get().plan == plan


def test_student_create_rejects_a_foreign_payer_and_plan_with_field_errors(client):
    from core.apps.students.models import Student

    from .factories import PayerFactory

    profession = ProfessionFactory.create()
    foreign_payer = PayerFactory.create()
    foreign_plan = PlanFactory.create()
    client.force_login(profession.user)

    response = client.post(
        reverse("students:student_create"),
        {
            "first_name": "Alice",
            "last_name": "Dupont",
            "start_date": "2026-09-15",
            "status": "active",
            "payer": foreign_payer.pk,
            "plan": foreign_plan.pk,
        },
    )

    assert response.status_code == 200
    assert "payer" in response.context["form"].errors
    assert "plan" in response.context["form"].errors
    assert not Student.objects.exists()


def test_student_detail_shows_plan_history_payer_and_siblings(client):
    import datetime

    from .factories import PayerFactory, StudentFactory

    profession = ProfessionFactory.create()
    payer = PayerFactory.create(profession=profession, name="Famille Dupont")
    student = StudentFactory.create(
        profession=profession, first_name="Alice", last_name="Dupont", payer=payer
    )
    sibling = StudentFactory.create(
        profession=profession, first_name="Bob", last_name="Dupont", payer=payer
    )
    PlanAssignmentFactory.create(
        profession=profession,
        student=student,
        plan=PlanFactory.create(profession=profession, name="Ancienne"),
        starts_on=datetime.date(2025, 9, 1),
        ends_on=datetime.date(2026, 8, 1),
    )
    PlanAssignmentFactory.create(
        profession=profession,
        student=student,
        plan=PlanFactory.create(profession=profession, name="Hebdomadaire"),
        starts_on=datetime.date(2026, 9, 1),
    )
    client.force_login(profession.user)

    response = client.get(reverse("students:student_detail", args=[student.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Hebdomadaire" in content
    assert "Ancienne" in content
    assert "Famille Dupont" in content
    assert sibling.full_name in content
    assert response.context["nav_section"] == "students"


def test_student_pages_return_404_for_another_professions_student(client):
    from .factories import StudentFactory

    foreign = StudentFactory.create()
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    for url_name in (
        "students:student_detail",
        "students:student_update",
        "students:student_plan_assign",
    ):
        assert client.get(reverse(url_name, args=[foreign.pk])).status_code == 404
    assert (
        client.post(
            reverse("students:student_plan_remove_latest", args=[foreign.pk])
        ).status_code
        == 404
    )


def test_student_update_changes_the_status_and_end_date(client):
    from core.apps.students.models import Student

    from .factories import StudentFactory

    student = StudentFactory.create(start_date=__import__("datetime").date(2026, 9, 1))
    client.force_login(student.profession.user)

    response = client.post(
        reverse("students:student_update", args=[student.pk]),
        {
            "first_name": student.first_name,
            "last_name": student.last_name,
            "start_date": "2026-09-01",
            "end_date": "2027-06-30",
            "status": "ended",
            "payer": "",
            "payment_reference_name": "DUPONT",
        },
    )

    assert response.status_code == 302
    student.refresh_from_db()
    assert student.status == Student.Status.ENDED
    assert student.end_date == __import__("datetime").date(2027, 6, 30)
    assert student.payment_reference_name == "DUPONT"


def test_student_plan_assign_end_and_remove_latest(client):
    import datetime

    from core.apps.students.models import PlanAssignment

    from .factories import StudentFactory

    student = StudentFactory.create(start_date=datetime.date(2026, 9, 1))
    first_plan = PlanFactory.create(profession=student.profession)
    second_plan = PlanFactory.create(profession=student.profession)
    client.force_login(student.profession.user)
    assign_url = reverse("students:student_plan_assign", args=[student.pk])

    first = client.post(
        assign_url, {"plan": first_plan.pk, "starts_on_0": "9", "starts_on_1": "2026"}
    )
    second = client.post(
        assign_url, {"plan": second_plan.pk, "starts_on_0": "11", "starts_on_1": "2026"}
    )
    assert first.status_code == 302
    assert second.status_code == 302
    assignments = list(
        PlanAssignment.objects.filter(student=student).order_by("starts_on")
    )
    assert [assignment.plan for assignment in assignments] == [first_plan, second_plan]
    assert assignments[0].ends_on == datetime.date(2026, 10, 1)

    ended = client.post(
        reverse("students:student_plan_end", args=[student.pk]),
        {"last_month_0": "12", "last_month_1": "2026"},
    )
    assert ended.status_code == 302
    assignments[1].refresh_from_db()
    assert assignments[1].ends_on == datetime.date(2026, 12, 1)

    removed = client.post(
        reverse("students:student_plan_remove_latest", args=[student.pk])
    )
    assert removed.status_code == 302
    assignments[0].refresh_from_db()
    assert assignments[0].ends_on is None
    assert PlanAssignment.objects.filter(student=student).count() == 1


def test_student_plan_assign_rejects_a_foreign_plan_with_a_field_error(client):
    from core.apps.students.models import PlanAssignment

    from .factories import StudentFactory

    student = StudentFactory.create()
    foreign_plan = PlanFactory.create()
    client.force_login(student.profession.user)

    response = client.post(
        reverse("students:student_plan_assign", args=[student.pk]),
        {"plan": foreign_plan.pk, "starts_on_0": "9", "starts_on_1": "2026"},
    )

    assert response.status_code == 200
    assert "plan" in response.context["form"].errors
    assert not PlanAssignment.objects.exists()


def test_student_plan_assign_shows_business_refusals_on_the_form(client):
    import datetime

    from .factories import StudentFactory

    student = StudentFactory.create(start_date=datetime.date(2026, 9, 1))
    plan = PlanFactory.create(profession=student.profession)
    client.force_login(student.profession.user)

    response = client.post(
        reverse("students:student_plan_assign", args=[student.pk]),
        {"plan": plan.pk, "starts_on_0": "6", "starts_on_1": "2026"},
    )

    assert response.status_code == 200
    assert "avant le début des cours" in response.content.decode()


# --- Payers -----------------------------------------------------------------


def test_payer_list_and_detail_show_students_and_family_plan(client):
    import datetime

    from core.apps.students.models import Plan

    from .factories import PayerFactory, StudentFactory

    profession = ProfessionFactory.create()
    payer = PayerFactory.create(
        profession=profession, name="Famille Martin", payment_reference_name="MARTIN J."
    )
    StudentFactory.create(
        profession=profession, first_name="Léa", last_name="Martin", payer=payer
    )
    family_plan = PlanFactory.create(profession=profession, name="Formule famille")
    PlanAssignmentFactory.create(
        profession=profession,
        student=None,
        payer=payer,
        plan=family_plan,
        starts_on=datetime.date(2026, 9, 1),
    )
    PayerFactory.create(name="Payeur étranger")
    client.force_login(profession.user)

    listing = client.get(reverse("students:payer_list")).content.decode()
    detail = client.get(
        reverse("students:payer_detail", args=[payer.pk])
    ).content.decode()

    assert "Famille Martin" in listing
    assert "MARTIN J." in listing
    assert "Payeur étranger" not in listing
    assert "Léa Martin" in detail
    assert "Formule famille" in detail
    assert Plan.objects.filter(pk=family_plan.pk).exists()


def test_payer_create_update_and_delete(client):
    from core.apps.students.models import Payer

    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    created = client.post(
        reverse("students:payer_create"),
        {
            "name": "Famille Rossi",
            "payment_reference_name": "",
            "email": "",
            "phone": "",
            "notes": "",
        },
    )
    payer = Payer.objects.get(name="Famille Rossi")
    assert created.status_code == 302
    assert payer.profession == profession

    updated = client.post(
        reverse("students:payer_update", args=[payer.pk]),
        {
            "name": "Famille Rossi",
            "payment_reference_name": "ROSSI M",
            "email": "",
            "phone": "",
            "notes": "",
        },
    )
    payer.refresh_from_db()
    assert updated.status_code == 302
    assert payer.reference_name == "ROSSI M"

    deleted = client.post(reverse("students:payer_delete", args=[payer.pk]))
    assert deleted.status_code == 302
    assert not Payer.objects.filter(pk=payer.pk).exists()


def test_payer_delete_is_refused_with_students(client):
    from core.apps.students.models import Payer

    from .factories import PayerFactory, StudentFactory

    payer = PayerFactory.create()
    StudentFactory.create(profession=payer.profession, payer=payer)
    client.force_login(payer.profession.user)

    response = client.post(
        reverse("students:payer_delete", args=[payer.pk]), follow=True
    )

    assert Payer.objects.filter(pk=payer.pk).exists()
    assert "détachez-les" in response.content.decode()


def test_payer_plan_assign_offers_only_monthly_plans(client):
    from core.apps.students.models import Plan, PlanAssignment

    from .factories import PayerFactory

    payer = PayerFactory.create()
    single = PlanFactory.create(
        profession=payer.profession, kind=Plan.Kind.SINGLE_LESSON
    )
    monthly = PlanFactory.create(profession=payer.profession)
    client.force_login(payer.profession.user)
    assign_url = reverse("students:payer_plan_assign", args=[payer.pk])

    refused = client.post(
        assign_url, {"plan": single.pk, "starts_on_0": "9", "starts_on_1": "2026"}
    )
    accepted = client.post(
        assign_url, {"plan": monthly.pk, "starts_on_0": "9", "starts_on_1": "2026"}
    )

    assert refused.status_code == 200
    assert "plan" in refused.context["form"].errors
    assert accepted.status_code == 302
    assert PlanAssignment.objects.get(payer=payer).plan == monthly


def test_payer_pages_return_404_for_another_professions_payer(client):
    from .factories import PayerFactory

    foreign = PayerFactory.create()
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    assert (
        client.get(reverse("students:payer_detail", args=[foreign.pk])).status_code
        == 404
    )
    assert (
        client.post(reverse("students:payer_delete", args=[foreign.pk])).status_code
        == 404
    )

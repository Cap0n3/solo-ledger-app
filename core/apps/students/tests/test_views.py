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

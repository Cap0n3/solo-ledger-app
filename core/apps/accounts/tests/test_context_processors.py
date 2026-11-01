import pytest
from django.urls import reverse

from .factories import ProfessionFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("url_name", "section"),
    [
        ("reports:dashboard", "dashboard"),
        ("students:student_list", "students"),
        ("students:plan_list", "plans"),
        ("accounting:expense_list", "expenses"),
        ("accounting:ledger_entry_list", "accounting"),
        ("accounts:settings", "settings"),
    ],
)
def test_nav_section_follows_the_current_page(client, url_name, section):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.get(reverse(url_name))

    assert response.context["nav_section"] == section


def test_nav_section_is_empty_on_error_pages(client):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.get("/does-not-exist/")

    assert response.status_code == 404
    assert response.context["nav_section"] is None

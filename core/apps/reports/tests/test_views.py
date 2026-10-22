import pytest
from django.urls import reverse

from core.apps.accounts.tests.factories import ProfessionFactory

pytestmark = pytest.mark.django_db

URL_NAMES = (
    "reports:dashboard",
    "reports:statistics",
    "reports:income_statement",
)


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

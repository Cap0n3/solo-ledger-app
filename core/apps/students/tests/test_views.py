import pytest
from django.urls import reverse

from core.apps.accounts.tests.factories import ActivityFactory

pytestmark = pytest.mark.django_db

URL_NAMES = (
    "students:student_list",
    "students:plan_list",
)


@pytest.mark.parametrize("url_name", URL_NAMES)
def test_pages_redirect_anonymous_user_to_login(client, url_name):
    response = client.get(reverse(url_name))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.parametrize("url_name", URL_NAMES)
def test_pages_render_with_the_users_own_activity(client, url_name):
    activity = ActivityFactory.create(name="Cours de guitare")
    client.force_login(activity.user)

    response = client.get(reverse(url_name))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()

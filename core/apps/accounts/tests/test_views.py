import pytest
from django.urls import reverse

from core.apps.accounts.types import CURRENT_ACTIVITY_SESSION_KEY

from .factories import ActivityFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_dashboard_redirects_anonymous_user_to_login(client):
    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_dashboard_never_shows_another_users_activity(client):
    own = ActivityFactory.create(name="Cours de guitare")
    foreign = ActivityFactory.create(name="Cours de chant")
    client.force_login(own.user)
    session = client.session
    session[CURRENT_ACTIVITY_SESSION_KEY] = foreign.pk
    session.save()

    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 200
    assert response.context["current_activity"] == own
    content = response.content.decode()
    assert "Cours de guitare" in content
    assert "Cours de chant" not in content


def test_dashboard_returns_403_for_user_without_activity(client):
    client.force_login(UserFactory.create())

    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 403


def test_login_page_is_public(client):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200


def test_login_redirects_to_dashboard(client):
    activity = ActivityFactory.create()
    activity.user.set_password("secret-pass-123")
    activity.user.save()

    response = client.post(
        reverse("accounts:login"),
        {"username": activity.user.username, "password": "secret-pass-123"},
    )

    assert response.status_code == 302
    assert response.url == reverse("reports:dashboard")


def test_logout_requires_post(client):
    client.force_login(ActivityFactory.create().user)

    assert client.get(reverse("accounts:logout")).status_code == 405

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


def test_password_change_updates_password(client):
    activity = ActivityFactory.create()
    user = activity.user
    user.set_password("old-password-123")
    user.save()
    client.force_login(user)

    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "old-password-123",
            "new_password1": "new-password-456",
            "new_password2": "new-password-456",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("new-password-456")


def test_password_change_page_still_shows_current_activity(client):
    activity = ActivityFactory.create(name="Cours de guitare")
    client.force_login(activity.user)

    response = client.get(reverse("accounts:password_change"))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()


def test_settings_page_shows_current_activity(client):
    activity = ActivityFactory.create(name="Cours de guitare")
    client.force_login(activity.user)

    response = client.get(reverse("accounts:settings"))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()

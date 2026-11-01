import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.apps.accounts import forms as accounts_forms
from core.apps.accounts.services import user_avatar_update, user_profile_update
from core.apps.accounts.types import CURRENT_PROFESSION_SESSION_KEY

from .factories import ProfessionFactory, UserFactory, avatar_upload

pytestmark = pytest.mark.django_db


def test_dashboard_redirects_anonymous_user_to_login(client):
    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


def test_dashboard_never_shows_another_users_profession(client):
    own = ProfessionFactory.create(name="Cours de guitare")
    foreign = ProfessionFactory.create(name="Cours de chant")
    client.force_login(own.user)
    session = client.session
    session[CURRENT_PROFESSION_SESSION_KEY] = foreign.pk
    session.save()

    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 200
    assert response.context["current_profession"] == own
    content = response.content.decode()
    assert "Cours de guitare" in content
    assert "Cours de chant" not in content


def test_dashboard_returns_403_for_user_without_profession(client):
    client.force_login(UserFactory.create())

    response = client.get(reverse("reports:dashboard"))

    assert response.status_code == 403


def test_login_page_is_public(client):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200


def test_login_redirects_to_dashboard(client):
    profession = ProfessionFactory.create()
    profession.user.set_password("secret-pass-123")
    profession.user.save()

    response = client.post(
        reverse("accounts:login"),
        {"username": profession.user.username, "password": "secret-pass-123"},
    )

    assert response.status_code == 302
    assert response.url == reverse("reports:dashboard")


def test_logout_requires_post(client):
    client.force_login(ProfessionFactory.create().user)

    assert client.get(reverse("accounts:logout")).status_code == 405

    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


def test_password_change_updates_password(client):
    profession = ProfessionFactory.create()
    user = profession.user
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


def test_password_change_page_still_shows_current_profession(client):
    profession = ProfessionFactory.create(name="Cours de guitare")
    client.force_login(profession.user)

    response = client.get(reverse("accounts:password_change"))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()


def test_settings_page_shows_current_profession(client):
    profession = ProfessionFactory.create(name="Cours de guitare")
    client.force_login(profession.user)

    response = client.get(reverse("accounts:settings"))

    assert response.status_code == 200
    assert "Cours de guitare" in response.content.decode()


def test_settings_upload_sets_avatar(client):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.post(
        reverse("accounts:avatar_update"), {"avatar": avatar_upload()}
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:settings")
    profession.user.refresh_from_db()
    assert str(profession.user.avatar).startswith(f"avatars/{profession.user.pk}/")


def test_settings_rejects_file_that_is_not_an_image(client):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)
    upload = SimpleUploadedFile("notes.png", b"not an image", content_type="image/png")

    response = client.post(reverse("accounts:avatar_update"), {"avatar": upload})

    assert response.status_code == 200
    assert "avatar" in response.context["avatar_form"].errors
    profession.user.refresh_from_db()
    assert not profession.user.avatar


def test_settings_rejects_image_above_size_limit(client, monkeypatch):
    monkeypatch.setattr(accounts_forms, "AVATAR_MAX_BYTES", 10)
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.post(
        reverse("accounts:avatar_update"), {"avatar": avatar_upload()}
    )

    assert response.status_code == 200
    assert "avatar" in response.context["avatar_form"].errors
    profession.user.refresh_from_db()
    assert not profession.user.avatar


def test_avatar_remove_requires_post_and_clears_avatar(client):
    profession = ProfessionFactory.create()
    user_avatar_update(user=profession.user, avatar=avatar_upload())
    client.force_login(profession.user)

    assert client.get(reverse("accounts:avatar_remove")).status_code == 405

    response = client.post(reverse("accounts:avatar_remove"))

    assert response.status_code == 302
    profession.user.refresh_from_db()
    assert not profession.user.avatar


def test_avatar_upload_never_touches_another_user(client):
    own = ProfessionFactory.create()
    other = ProfessionFactory.create()
    client.force_login(own.user)

    client.post(reverse("accounts:avatar_update"), {"avatar": avatar_upload()})

    own.user.refresh_from_db()
    other.user.refresh_from_db()
    assert own.user.avatar
    assert not other.user.avatar


def test_topbar_shows_initial_without_avatar_and_image_with_one(client):
    profession = ProfessionFactory.create()
    profession.user.first_name = "[TEST] Guitare"
    profession.user.save()
    client.force_login(profession.user)

    content = client.get(reverse("reports:dashboard")).content.decode()
    assert "app-avatar--initial" in content
    assert reverse("accounts:settings") in content

    user_avatar_update(user=profession.user, avatar=avatar_upload())
    content = client.get(reverse("reports:dashboard")).content.decode()
    assert "app-avatar--initial" not in content
    assert profession.user.avatar.url in content


def test_settings_form_shows_current_names(client):
    profession = ProfessionFactory.create()
    user_profile_update(user=profession.user, first_name="Alice", last_name="Martin")
    client.force_login(profession.user)

    response = client.get(reverse("accounts:settings"))

    assert response.status_code == 200
    assert response.context["profile_form"].initial == {
        "first_name": "Alice",
        "last_name": "Martin",
    }


def test_profile_update_sets_first_and_last_name(client):
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    assert client.get(reverse("accounts:profile_update")).status_code == 405

    response = client.post(
        reverse("accounts:profile_update"),
        {"first_name": "  Alice ", "last_name": "Martin"},
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:settings")
    profession.user.refresh_from_db()
    assert profession.user.first_name == "Alice"
    assert profession.user.last_name == "Martin"


def test_profile_update_rejects_name_longer_than_the_model_allows(client):
    profession = ProfessionFactory.create()
    original_first_name = profession.user.first_name
    client.force_login(profession.user)

    response = client.post(
        reverse("accounts:profile_update"),
        {"first_name": "a" * 151, "last_name": "Martin"},
    )

    assert response.status_code == 200
    assert "first_name" in response.context["profile_form"].errors
    profession.user.refresh_from_db()
    assert profession.user.first_name == original_first_name


def test_profile_update_never_touches_another_user(client):
    own = ProfessionFactory.create()
    other = ProfessionFactory.create()
    other_first_name = other.user.first_name
    client.force_login(own.user)

    client.post(
        reverse("accounts:profile_update"),
        {"first_name": "Alice", "last_name": "Martin"},
    )

    own.user.refresh_from_db()
    other.user.refresh_from_db()
    assert own.user.first_name == "Alice"
    assert other.user.first_name == other_first_name


# --- Lesson years in settings -----------------------------------------------


def test_settings_page_lists_the_professions_lesson_years(client):
    import datetime

    from .factories import LessonYearFactory

    profession = ProfessionFactory.create()
    LessonYearFactory.create(
        profession=profession,
        first_month=datetime.date(2026, 9, 1),
        last_month=datetime.date(2027, 7, 1),
    )
    LessonYearFactory.create(
        first_month=datetime.date(2024, 9, 1), last_month=datetime.date(2025, 7, 1)
    )
    client.force_login(profession.user)

    response = client.get(reverse("accounts:settings"))

    content = response.content.decode()
    assert "2026-2027" in content
    assert "2024-2025" not in content


def test_lesson_year_create_and_overlap_refusal(client):
    import datetime

    from core.apps.accounts.models import LessonYear

    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    created = client.post(
        reverse("accounts:lesson_year_create"),
        {
            "first_month_0": "9",
            "first_month_1": "2026",
            "last_month_0": "7",
            "last_month_1": "2027",
        },
    )
    assert created.status_code == 302
    lesson_year = LessonYear.objects.get(profession=profession)
    assert lesson_year.first_month == datetime.date(2026, 9, 1)
    assert lesson_year.last_month == datetime.date(2027, 7, 1)

    overlapping = client.post(
        reverse("accounts:lesson_year_create"),
        {
            "first_month_0": "7",
            "first_month_1": "2027",
            "last_month_0": "6",
            "last_month_1": "2028",
        },
    )
    assert overlapping.status_code == 200
    assert "chevauche" in overlapping.content.decode()
    assert LessonYear.objects.filter(profession=profession).count() == 1
    assert overlapping.context["nav_section"] == "settings"


def test_lesson_year_update_changes_the_months(client):
    import datetime

    from .factories import LessonYearFactory

    lesson_year = LessonYearFactory.create()
    client.force_login(lesson_year.profession.user)

    response = client.post(
        reverse("accounts:lesson_year_update", args=[lesson_year.pk]),
        {
            "first_month_0": "8",
            "first_month_1": "2026",
            "last_month_0": "6",
            "last_month_1": "2027",
        },
    )

    assert response.status_code == 302
    lesson_year.refresh_from_db()
    assert lesson_year.first_month == datetime.date(2026, 8, 1)
    assert lesson_year.last_month == datetime.date(2027, 6, 1)


def test_lesson_year_update_returns_404_for_another_professions_year(client):
    from .factories import LessonYearFactory

    foreign = LessonYearFactory.create()
    profession = ProfessionFactory.create()
    client.force_login(profession.user)

    response = client.get(reverse("accounts:lesson_year_update", args=[foreign.pk]))

    assert response.status_code == 404

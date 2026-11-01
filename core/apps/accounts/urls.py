from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password-change/", views.PasswordChangeView.as_view(), name="password_change"
    ),
    path(
        "password-change/done/",
        views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path("settings/", views.settings_view, name="settings"),
    path("settings/profile/", views.profile_update_view, name="profile_update"),
    path("settings/avatar/", views.avatar_update_view, name="avatar_update"),
    path("settings/avatar/remove/", views.avatar_remove_view, name="avatar_remove"),
    path(
        "settings/lesson-years/new/",
        views.lesson_year_create_view,
        name="lesson_year_create",
    ),
    path(
        "settings/lesson-years/<int:lesson_year_id>/edit/",
        views.lesson_year_update_view,
        name="lesson_year_update",
    ),
]

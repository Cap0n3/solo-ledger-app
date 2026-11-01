from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.student_list, name="student_list"),
    path("plans/", views.plan_list, name="plan_list"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:plan_id>/edit/", views.plan_update, name="plan_update"),
    path(
        "plans/<int:plan_id>/archive/",
        views.plan_archive_toggle,
        name="plan_archive_toggle",
    ),
    path("plans/<int:plan_id>/delete/", views.plan_delete, name="plan_delete"),
]

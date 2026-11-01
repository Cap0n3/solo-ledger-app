from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.student_list, name="student_list"),
    path("new/", views.student_create, name="student_create"),
    path("<int:student_id>/", views.student_detail, name="student_detail"),
    path("<int:student_id>/edit/", views.student_update, name="student_update"),
    path(
        "<int:student_id>/plan/", views.student_plan_assign, name="student_plan_assign"
    ),
    path("<int:student_id>/plan/end/", views.student_plan_end, name="student_plan_end"),
    path(
        "<int:student_id>/plan/remove-latest/",
        views.student_plan_remove_latest,
        name="student_plan_remove_latest",
    ),
    path("payers/", views.payer_list, name="payer_list"),
    path("payers/new/", views.payer_create, name="payer_create"),
    path("payers/<int:payer_id>/", views.payer_detail, name="payer_detail"),
    path("payers/<int:payer_id>/edit/", views.payer_update, name="payer_update"),
    path(
        "payers/<int:payer_id>/plan/", views.payer_plan_assign, name="payer_plan_assign"
    ),
    path(
        "payers/<int:payer_id>/plan/end/", views.payer_plan_end, name="payer_plan_end"
    ),
    path(
        "payers/<int:payer_id>/plan/remove-latest/",
        views.payer_plan_remove_latest,
        name="payer_plan_remove_latest",
    ),
    path("payers/<int:payer_id>/delete/", views.payer_delete, name="payer_delete"),
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

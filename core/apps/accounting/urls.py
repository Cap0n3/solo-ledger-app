from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.ledger_entry_list, name="ledger_entry_list"),
    path("payments/new/", views.payment_create, name="payment_create"),
    path(
        "payments/<int:payment_id>/edit/", views.payment_update, name="payment_update"
    ),
    path(
        "payments/<int:payment_id>/delete/",
        views.payment_delete,
        name="payment_delete",
    ),
    path("income/new/", views.one_off_income_create, name="one_off_income_create"),
    path(
        "income/<int:payment_id>/edit/",
        views.one_off_income_update,
        name="one_off_income_update",
    ),
    path(
        "expected-payments/<int:expected_payment_id>/cancel/",
        views.expected_payment_cancel,
        name="expected_payment_cancel",
    ),
    path(
        "expected-payments/<int:expected_payment_id>/restore/",
        views.expected_payment_restore,
        name="expected_payment_restore",
    ),
    path(
        "expected-payments/<int:expected_payment_id>/amount/",
        views.expected_payment_amount_update,
        name="expected_payment_amount_update",
    ),
    path("expenses/", views.expense_list, name="expense_list"),
]

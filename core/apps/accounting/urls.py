from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.ledger_entry_list, name="ledger_entry_list"),
    path("expenses/", views.expense_list, name="expense_list"),
]

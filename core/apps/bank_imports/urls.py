from django.urls import path

from . import views

app_name = "bank_imports"

urlpatterns = [
    path("", views.bank_statement_list, name="bank_statement_list"),
]

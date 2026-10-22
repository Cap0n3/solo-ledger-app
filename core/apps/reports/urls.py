from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("statistics/", views.statistics, name="statistics"),
    path("income-statement/", views.income_statement, name="income_statement"),
]

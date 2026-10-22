from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("core.apps.accounts.urls")),
    path("students/", include("core.apps.students.urls")),
    path("accounting/", include("core.apps.accounting.urls")),
    path("bank-imports/", include("core.apps.bank_imports.urls")),
    path("", include("core.apps.reports.urls")),
]

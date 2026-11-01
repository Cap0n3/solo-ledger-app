from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    path("accounts/", include("core.apps.accounts.urls")),
    path("students/", include("core.apps.students.urls")),
    path("accounting/", include("core.apps.accounting.urls")),
    path("bank-imports/", include("core.apps.bank_imports.urls")),
    path("", include("core.apps.reports.urls")),
]

if settings.DEBUG:
    # Uploaded files are served by Django in development only; production
    # serving belongs to the production milestone.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

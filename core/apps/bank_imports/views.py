from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.decorators import activity_required
from core.apps.accounts.types import ActivityHttpRequest

# Placeholder page: the real views arrive with the bank import milestone.


@activity_required
def bank_statement_list(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Import bancaire"),
        "page_subtitle": _("Import des relevés CSV et vérification des transactions"),
    }
    return render(request, "placeholder.html", context)

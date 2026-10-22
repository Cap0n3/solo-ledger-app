from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.decorators import profession_required
from core.apps.accounts.types import ProfessionHttpRequest

# Placeholder page: the real views arrive with the bank import milestone.


@profession_required
def bank_statement_list(request: ProfessionHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Import bancaire"),
        "page_subtitle": _("Import des relevés CSV et vérification des transactions"),
    }
    return render(request, "placeholder.html", context)

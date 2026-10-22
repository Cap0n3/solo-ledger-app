from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.decorators import activity_required
from core.apps.accounts.types import ActivityHttpRequest

# Placeholder pages: the real views arrive with the accounting and expenses milestones.


@activity_required
def ledger_entry_list(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Comptabilité"),
        "page_subtitle": _("Recettes et dépenses de l'activité"),
    }
    return render(request, "placeholder.html", context)


@activity_required
def expense_list(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Dépenses"),
        "page_subtitle": _("Saisie et consultation des dépenses par label"),
    }
    return render(request, "placeholder.html", context)

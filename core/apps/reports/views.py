from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.decorators import profession_required
from core.apps.accounts.types import ProfessionHttpRequest


@profession_required
def dashboard(request: ProfessionHttpRequest) -> HttpResponse:
    """Home page after login. Figures arrive with the dashboard milestone."""
    context = {
        "page_title": _("Tableau de bord"),
        "page_subtitle": _("Suivi des paiements et de la comptabilité"),
    }
    return render(request, "reports/dashboard.html", context)


@profession_required
def statistics(request: ProfessionHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Statistiques"),
        "page_subtitle": _("Indicateurs de suivi de l'activité"),
    }
    return render(request, "placeholder.html", context)


@profession_required
def income_statement(request: ProfessionHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Compte d'exploitation"),
        "page_subtitle": _("Recettes et dépenses de la période, par label"),
    }
    return render(request, "placeholder.html", context)

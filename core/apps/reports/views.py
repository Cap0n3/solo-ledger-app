from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.decorators import activity_required
from core.apps.accounts.types import ActivityHttpRequest


@activity_required
def dashboard(request: ActivityHttpRequest) -> HttpResponse:
    """Home page after login. Figures arrive with the dashboard milestone."""
    context = {
        "page_title": _("Tableau de bord"),
        "page_subtitle": _("Suivi des paiements et de la comptabilité"),
    }
    return render(request, "reports/dashboard.html", context)


@activity_required
def statistics(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Statistiques"),
        "page_subtitle": _("Indicateurs de suivi de l'activité"),
    }
    return render(request, "placeholder.html", context)


@activity_required
def income_statement(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Compte d'exploitation"),
        "page_subtitle": _("Recettes et dépenses de la période, par label"),
    }
    return render(request, "placeholder.html", context)

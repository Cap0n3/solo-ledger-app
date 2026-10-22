from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.decorators import activity_required
from core.apps.accounts.types import ActivityHttpRequest

# Placeholder pages: the real views arrive with the "students and plans" milestone.


@activity_required
def student_list(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Élèves"),
        "page_subtitle": _("Base de données des élèves et de leurs formules"),
    }
    return render(request, "placeholder.html", context)


@activity_required
def plan_list(request: ActivityHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Formules"),
        "page_subtitle": _("Gestion des formules de cours et de leurs tarifs"),
    }
    return render(request, "placeholder.html", context)

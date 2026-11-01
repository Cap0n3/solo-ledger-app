from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.apps.accounts.decorators import profession_required
from core.apps.accounts.types import ProfessionHttpRequest
from core.utils.forms import add_service_errors

from . import selectors, services
from .forms import PlanForm

# --- Students (placeholder until the student pages land) --------------------


@profession_required
def student_list(request: ProfessionHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Élèves"),
        "page_subtitle": _("Base de données des élèves et de leurs formules"),
    }
    return render(request, "placeholder.html", context)


# --- Plans ------------------------------------------------------------------


@profession_required
def plan_list(request: ProfessionHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Formules"),
        "page_subtitle": _("Gestion des formules de cours et de leurs tarifs"),
        "items": selectors.plan_list_items(profession=request.profession),
    }
    return render(request, "students/plan_list.html", context)


@profession_required
def plan_create(request: ProfessionHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            try:
                services.plan_create(
                    profession=request.profession,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data["description"],
                    price=form.cleaned_data["price"],
                    kind=form.cleaned_data["kind"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Formule créée."))
                return redirect("students:plan_list")
    else:
        form = PlanForm()
    context = {
        "page_title": _("Nouvelle formule"),
        "page_subtitle": _("Formules"),
        "form": form,
    }
    return render(request, "students/plan_form.html", context)


@profession_required
def plan_update(request: ProfessionHttpRequest, plan_id: int) -> HttpResponse:
    plan = selectors.plan_get(profession=request.profession, plan_id=plan_id)
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            try:
                services.plan_update(
                    plan=plan,
                    name=form.cleaned_data["name"],
                    description=form.cleaned_data["description"],
                    price=form.cleaned_data["price"],
                    kind=form.cleaned_data["kind"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Formule mise à jour."))
                return redirect("students:plan_list")
    else:
        form = PlanForm.for_plan(plan)
    context = {
        "page_title": plan.name,
        "page_subtitle": _("Modifier la formule"),
        "form": form,
        "plan": plan,
    }
    return render(request, "students/plan_form.html", context)


@profession_required
@require_POST
def plan_archive_toggle(request: ProfessionHttpRequest, plan_id: int) -> HttpResponse:
    plan = selectors.plan_get(profession=request.profession, plan_id=plan_id)
    if plan.is_archived:
        services.plan_unarchive(plan=plan)
        messages.success(request, _("Formule réactivée."))
    else:
        services.plan_archive(plan=plan)
        messages.success(request, _("Formule archivée."))
    return redirect("students:plan_list")


@profession_required
@require_POST
def plan_delete(request: ProfessionHttpRequest, plan_id: int) -> HttpResponse:
    plan = selectors.plan_get(profession=request.profession, plan_id=plan_id)
    try:
        services.plan_delete(plan=plan)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, _("Formule supprimée."))
    return redirect("students:plan_list")

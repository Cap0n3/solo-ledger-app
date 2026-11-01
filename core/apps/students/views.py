from collections.abc import Callable
from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.apps.accounts.decorators import profession_required
from core.apps.accounts.types import ProfessionHttpRequest
from core.utils.forms import add_service_errors
from core.utils.months import month_start

from . import selectors, services
from .forms import (
    PayerForm,
    PlanAssignForm,
    PlanAssignmentEndForm,
    PlanForm,
    StudentForm,
)
from .models import Payer, PlanAssignment, Student

PAGE_SIZE = 25
STATUS_FILTER_ALL = "all"
STATUS_FILTER_DEFAULT = (Student.Status.ACTIVE, Student.Status.PAUSED)


def _current_month() -> date:
    return month_start(timezone.localdate())


# --- Students ---------------------------------------------------------------


def _status_filter(value: str) -> tuple[str, tuple[Student.Status, ...]]:
    """Map the `status` query parameter to the statuses to list.

    By default the list shows active and paused students, as on the wireframe.
    """
    if value == STATUS_FILTER_ALL:
        return value, ()
    if value in Student.Status.values:
        return value, (Student.Status(value),)
    return "", STATUS_FILTER_DEFAULT


@profession_required
def student_list(request: ProfessionHttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()
    status_value, statuses = _status_filter(request.GET.get("status", ""))
    students = selectors.student_list(
        profession=request.profession, query=query, statuses=statuses
    )
    page = Paginator(students, PAGE_SIZE).get_page(request.GET.get("page"))
    items = selectors.student_list_items(
        students=page.object_list, month=_current_month()
    )
    filter_parameters: dict[str, str] = {}
    if query:
        filter_parameters["q"] = query
    if status_value:
        filter_parameters["status"] = status_value
    context = {
        "page_title": _("Élèves"),
        "page_subtitle": _("Base de données des élèves et de leurs formules"),
        "items": items,
        "page": page,
        "query": query,
        "status_value": status_value,
        "status_choices": Student.Status.choices,
        "status_filter_all": STATUS_FILTER_ALL,
        "filter_query": urlencode(filter_parameters),
    }
    # HTMX asks for the table alone, except when restoring history (back button).
    is_partial = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )
    template_name = (
        "students/includes/student_table.html"
        if is_partial
        else "students/student_list.html"
    )
    response = render(request, template_name, context)
    patch_vary_headers(response, ("HX-Request",))
    return response


@profession_required
def student_create(request: ProfessionHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = StudentForm.for_profession(request.profession, data=request.POST)
        if form.is_valid():
            try:
                student = services.student_create(
                    profession=request.profession,
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    notes=form.cleaned_data["notes"],
                    start_date=form.cleaned_data["start_date"],
                    end_date=form.cleaned_data["end_date"],
                    status=form.cleaned_data["status"],
                    payment_reference_name=form.cleaned_data["payment_reference_name"],
                    payer=form.cleaned_data["payer"],
                    plan=form.cleaned_data["plan"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Élève créé."))
                return redirect("students:student_detail", student_id=student.pk)
    else:
        initial = {"start_date": timezone.localdate(), "status": Student.Status.ACTIVE}
        form = StudentForm.for_profession(request.profession, initial=initial)
    context = {
        "page_title": _("Nouvel élève"),
        "page_subtitle": _("Élèves"),
        "form": form,
        "cancel_url": reverse("students:student_list"),
    }
    return render(request, "students/student_form.html", context)


@profession_required
def student_detail(request: ProfessionHttpRequest, student_id: int) -> HttpResponse:
    student = selectors.student_get(
        profession=request.profession, student_id=student_id
    )
    today = timezone.localdate()
    month = month_start(today)
    assignments = list(selectors.plan_assignment_list(student=student))
    latest_assignment = assignments[0] if assignments else None
    siblings: list[Student] = []
    payer_plan = None
    if student.payer is not None:
        siblings = list(
            selectors.student_list(
                profession=request.profession, payer=student.payer
            ).exclude(pk=student.pk)
        )
        payer_plan = selectors.payer_current_plan(payer=student.payer, month=month)
    has_past_end_date = (
        student.end_date is not None
        and student.end_date < today
        and student.status != Student.Status.ENDED
    )
    context = {
        "page_title": student.full_name,
        "page_subtitle": _("Fiche de l'élève"),
        "student": student,
        "current_plan": selectors.student_current_plan(student=student, month=month),
        "assignments": assignments,
        "latest_assignment": latest_assignment,
        "reopened_assignment": selectors.plan_assignment_reopened_by_removal(
            assignments=assignments
        ),
        "siblings": siblings,
        "payer_plan": payer_plan,
        "has_past_end_date": has_past_end_date,
    }
    return render(request, "students/student_detail.html", context)


@profession_required
def student_update(request: ProfessionHttpRequest, student_id: int) -> HttpResponse:
    student = selectors.student_get(
        profession=request.profession, student_id=student_id
    )
    if request.method == "POST":
        form = StudentForm.for_profession(
            request.profession, data=request.POST, include_plan=False
        )
        if form.is_valid():
            try:
                services.student_update(
                    student=student,
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    notes=form.cleaned_data["notes"],
                    start_date=form.cleaned_data["start_date"],
                    end_date=form.cleaned_data["end_date"],
                    status=form.cleaned_data["status"],
                    payment_reference_name=form.cleaned_data["payment_reference_name"],
                    payer=form.cleaned_data["payer"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Élève mis à jour."))
                return redirect("students:student_detail", student_id=student.pk)
    else:
        form = StudentForm.for_student(student)
    context = {
        "page_title": student.full_name,
        "page_subtitle": _("Modifier l'élève"),
        "form": form,
        "cancel_url": reverse("students:student_detail", args=[student.pk]),
    }
    return render(request, "students/student_form.html", context)


# --- Plan assignments, shared by students and payers ------------------------


def _plan_assign_response(
    request: ProfessionHttpRequest,
    *,
    target: Student | Payer,
    assign: Callable[[PlanAssignForm], None],
    back_url: str,
    monthly_only: bool,
) -> HttpResponse:
    if request.method == "POST":
        form = PlanAssignForm.for_profession(
            request.profession, data=request.POST, monthly_only=monthly_only
        )
        if form.is_valid():
            try:
                assign(form)
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Formule attribuée."))
                return redirect(back_url)
    else:
        form = PlanAssignForm.for_profession(
            request.profession,
            initial={"starts_on": _current_month()},
            monthly_only=monthly_only,
        )
    context = {
        "page_title": str(target),
        "page_subtitle": _("Changer de formule"),
        "form": form,
        "cancel_url": back_url,
        "submit_label": _("Attribuer la formule"),
    }
    return render(request, "students/plan_assign_form.html", context)


def _plan_end_response(
    request: ProfessionHttpRequest,
    *,
    target: Student | Payer,
    latest_assignment: PlanAssignment | None,
    back_url: str,
) -> HttpResponse:
    if latest_assignment is None or not latest_assignment.is_open:
        messages.error(request, _("Aucune formule en cours à terminer."))
        return redirect(back_url)
    if request.method == "POST":
        form = PlanAssignmentEndForm(request.POST)
        if form.is_valid():
            try:
                services.plan_assignment_end(
                    assignment=latest_assignment,
                    last_month=form.cleaned_data["last_month"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Formule terminée."))
                return redirect(back_url)
    else:
        form = PlanAssignmentEndForm(initial={"last_month": _current_month()})
    context = {
        "page_title": str(target),
        "page_subtitle": _("Terminer la formule"),
        "form": form,
        "cancel_url": back_url,
        "submit_label": _("Terminer la formule"),
        "assignment": latest_assignment,
    }
    return render(request, "students/plan_assign_form.html", context)


@profession_required
def student_plan_assign(
    request: ProfessionHttpRequest, student_id: int
) -> HttpResponse:
    student = selectors.student_get(
        profession=request.profession, student_id=student_id
    )

    def assign(form: PlanAssignForm) -> None:
        services.plan_assign(
            plan=form.cleaned_data["plan"],
            starts_on=form.cleaned_data["starts_on"],
            student=student,
        )

    return _plan_assign_response(
        request,
        target=student,
        assign=assign,
        back_url=reverse("students:student_detail", args=[student.pk]),
        monthly_only=False,
    )


@profession_required
def student_plan_end(request: ProfessionHttpRequest, student_id: int) -> HttpResponse:
    student = selectors.student_get(
        profession=request.profession, student_id=student_id
    )
    return _plan_end_response(
        request,
        target=student,
        latest_assignment=selectors.plan_assignment_latest(student=student),
        back_url=reverse("students:student_detail", args=[student.pk]),
    )


@profession_required
@require_POST
def student_plan_remove_latest(
    request: ProfessionHttpRequest, student_id: int
) -> HttpResponse:
    student = selectors.student_get(
        profession=request.profession, student_id=student_id
    )
    try:
        services.plan_assignment_remove_latest(student=student)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, _("Dernière attribution supprimée."))
    return redirect("students:student_detail", student_id=student.pk)


# --- Payers -----------------------------------------------------------------


@profession_required
def payer_list(request: ProfessionHttpRequest) -> HttpResponse:
    context = {
        "page_title": _("Payeurs"),
        "page_subtitle": _("Personnes qui règlent les cours d'un ou plusieurs élèves"),
        "items": selectors.payer_list_items(
            profession=request.profession, month=_current_month()
        ),
    }
    return render(request, "students/payer_list.html", context)


@profession_required
def payer_create(request: ProfessionHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = PayerForm(request.POST)
        if form.is_valid():
            try:
                payer = services.payer_create(
                    profession=request.profession,
                    name=form.cleaned_data["name"],
                    payment_reference_name=form.cleaned_data["payment_reference_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    notes=form.cleaned_data["notes"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Payeur créé."))
                return redirect("students:payer_detail", payer_id=payer.pk)
    else:
        form = PayerForm()
    context = {
        "page_title": _("Nouveau payeur"),
        "page_subtitle": _("Payeurs"),
        "form": form,
        "cancel_url": reverse("students:payer_list"),
    }
    return render(request, "students/payer_form.html", context)


@profession_required
def payer_detail(request: ProfessionHttpRequest, payer_id: int) -> HttpResponse:
    payer = selectors.payer_get(profession=request.profession, payer_id=payer_id)
    month = _current_month()
    assignments = list(selectors.plan_assignment_list(payer=payer))
    context = {
        "page_title": payer.name,
        "page_subtitle": _("Fiche du payeur"),
        "payer": payer,
        "students": selectors.student_list(profession=request.profession, payer=payer),
        "current_plan": selectors.payer_current_plan(payer=payer, month=month),
        "assignments": assignments,
        "latest_assignment": assignments[0] if assignments else None,
        "reopened_assignment": selectors.plan_assignment_reopened_by_removal(
            assignments=assignments
        ),
    }
    return render(request, "students/payer_detail.html", context)


@profession_required
def payer_update(request: ProfessionHttpRequest, payer_id: int) -> HttpResponse:
    payer = selectors.payer_get(profession=request.profession, payer_id=payer_id)
    if request.method == "POST":
        form = PayerForm(request.POST)
        if form.is_valid():
            try:
                services.payer_update(
                    payer=payer,
                    name=form.cleaned_data["name"],
                    payment_reference_name=form.cleaned_data["payment_reference_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    notes=form.cleaned_data["notes"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Payeur mis à jour."))
                return redirect("students:payer_detail", payer_id=payer.pk)
    else:
        form = PayerForm.for_payer(payer)
    context = {
        "page_title": payer.name,
        "page_subtitle": _("Modifier le payeur"),
        "form": form,
        "cancel_url": reverse("students:payer_detail", args=[payer.pk]),
    }
    return render(request, "students/payer_form.html", context)


@profession_required
def payer_plan_assign(request: ProfessionHttpRequest, payer_id: int) -> HttpResponse:
    payer = selectors.payer_get(profession=request.profession, payer_id=payer_id)

    def assign(form: PlanAssignForm) -> None:
        services.plan_assign(
            plan=form.cleaned_data["plan"],
            starts_on=form.cleaned_data["starts_on"],
            payer=payer,
        )

    return _plan_assign_response(
        request,
        target=payer,
        assign=assign,
        back_url=reverse("students:payer_detail", args=[payer.pk]),
        monthly_only=True,
    )


@profession_required
def payer_plan_end(request: ProfessionHttpRequest, payer_id: int) -> HttpResponse:
    payer = selectors.payer_get(profession=request.profession, payer_id=payer_id)
    return _plan_end_response(
        request,
        target=payer,
        latest_assignment=selectors.plan_assignment_latest(payer=payer),
        back_url=reverse("students:payer_detail", args=[payer.pk]),
    )


@profession_required
@require_POST
def payer_plan_remove_latest(
    request: ProfessionHttpRequest, payer_id: int
) -> HttpResponse:
    payer = selectors.payer_get(profession=request.profession, payer_id=payer_id)
    try:
        services.plan_assignment_remove_latest(payer=payer)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, _("Dernière attribution supprimée."))
    return redirect("students:payer_detail", payer_id=payer.pk)


@profession_required
@require_POST
def payer_delete(request: ProfessionHttpRequest, payer_id: int) -> HttpResponse:
    payer = selectors.payer_get(profession=request.profession, payer_id=payer_id)
    try:
        services.payer_delete(payer=payer)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
        return redirect("students:payer_detail", payer_id=payer.pk)
    messages.success(request, _("Payeur supprimé."))
    return redirect("students:payer_list")


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

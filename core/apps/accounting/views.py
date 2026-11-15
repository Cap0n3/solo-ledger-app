from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.apps.accounts.decorators import profession_required
from core.apps.accounts.types import ProfessionHttpRequest
from core.apps.students.models import Payer, Student
from core.apps.students.selectors import payer_get, student_get
from core.utils.forms import add_service_errors

from . import selectors, services
from .forms import (
    AllocationForm,
    ExpectedPaymentAmountForm,
    ExpectedPaymentCancelForm,
    OneOffIncomeForm,
    PaymentForm,
)
from .models import ExpectedPayment, Payment, PaymentMethod
from .selectors import AllocatableMonth, AllocationProposal

ACTION_SAVE = "save"


def _target_url(*, student: Student | None, payer: Payer | None) -> str:
    """Where to go back to after working on a payment or a month."""
    if student is not None:
        return reverse("students:student_detail", args=[student.pk])
    if payer is not None:
        return reverse("students:payer_detail", args=[payer.pk])
    return reverse("accounting:ledger_entry_list")


# --- Ledger -----------------------------------------------------------------


def _fiscal_year_selected(*, value: str | None, years: list[int], today: date) -> int:
    if value is not None and value.isdigit() and int(value) in years:
        return int(value)
    return today.year


@profession_required
def ledger_entry_list(request: ProfessionHttpRequest) -> HttpResponse:
    """Income actually received during a fiscal (calendar) year."""
    today = timezone.localdate()
    fiscal_years = selectors.fiscal_year_list(
        profession=request.profession, today=today
    )
    fiscal_year = _fiscal_year_selected(
        value=request.GET.get("year"), years=fiscal_years, today=today
    )
    context = {
        "page_title": _("Comptabilité"),
        "page_subtitle": _("Recettes reçues, par année fiscale"),
        "fiscal_years": fiscal_years,
        "fiscal_year": fiscal_year,
        "entries": selectors.ledger_entry_list(
            profession=request.profession, fiscal_year=fiscal_year
        ),
        "income_total": selectors.income_for_fiscal_year(
            profession=request.profession, fiscal_year=fiscal_year
        ),
    }
    return render(request, "accounting/ledger_entry_list.html", context)


@profession_required
def expense_list(request: ProfessionHttpRequest) -> HttpResponse:
    # Placeholder page: the real view arrives with the expenses milestone.
    context = {
        "page_title": _("Dépenses"),
        "page_subtitle": _("Saisie et consultation des dépenses par label"),
    }
    return render(request, "placeholder.html", context)


# --- Monthly payments -------------------------------------------------------


@dataclass(frozen=True)
class AllocationRow:
    """A line of the allocation table: a month owed and its amount input."""

    month: AllocatableMonth
    field: forms.BoundField
    is_arrear: bool


def _proposal_token(
    *, student: Student | None, payer: Payer | None, amount: Decimal, received_on: date
) -> str:
    """Identifies what an allocation was proposed for.

    Posted back with the allocation: when the payer, the amount or the date
    changed in the meantime, the shares on screen are stale and a new proposal
    is shown instead of saving.
    """
    student_id = student.pk if student is not None else ""
    payer_id = payer.pk if payer is not None else ""
    return f"{student_id}|{payer_id}|{amount}|{received_on.isoformat()}"


def _allocation_rows(
    *,
    months: list[AllocatableMonth],
    allocation_form: AllocationForm,
    student: Student | None,
    payer: Payer | None,
    received_on: date,
) -> list[AllocationRow]:
    target = selectors.payment_target(student=student, payer=payer)
    lesson_year = selectors.lesson_year_for_payment(
        profession=target.profession, received_on=received_on
    )
    rows: list[AllocationRow] = []
    for month in months:
        is_arrear = (
            lesson_year is not None
            and month.expected_payment.month < lesson_year.first_month
        )
        field = allocation_form[AllocationForm.field_name(month.expected_payment)]
        rows.append(AllocationRow(month=month, field=field, is_arrear=is_arrear))
    return rows


def _proposal_initial(proposal: AllocationProposal) -> dict[str, object]:
    initial: dict[str, object] = {}
    for share in proposal.shares:
        initial[AllocationForm.field_name(share.expected_payment)] = share.amount
    return initial


def _payment_form_response(
    request: ProfessionHttpRequest, *, payment: Payment | None
) -> HttpResponse:
    """Create or correct a monthly payment, in two steps on a single page.

    The payment is entered first; the months still owed are then shown with
    the proposed allocation, which the user confirms or corrects by saving.
    """
    profession = request.profession
    allocation_form: AllocationForm | None = None
    proposal: AllocationProposal | None = None
    rows: list[AllocationRow] = []
    token = ""
    is_proposal_refreshed = False
    cancel_url = reverse("accounting:ledger_entry_list")
    if payment is not None:
        cancel_url = _target_url(student=payment.student, payer=payment.payer)

    if request.method == "POST":
        form = PaymentForm.for_profession(profession, data=request.POST)
        if form.is_valid():
            student: Student | None = form.cleaned_data["student"]
            payer: Payer | None = form.cleaned_data["payer"]
            amount: Decimal = form.cleaned_data["amount"]
            received_on: date = form.cleaned_data["received_on"]
            months = selectors.allocatable_month_list(
                student=student, payer=payer, exclude_payment=payment
            )
            token = _proposal_token(
                student=student, payer=payer, amount=amount, received_on=received_on
            )
            wants_save = request.POST.get("action") == ACTION_SAVE
            is_token_current = request.POST.get("proposed_for") == token
            if wants_save and is_token_current:
                allocation_form = AllocationForm.for_months(months, data=request.POST)
                if allocation_form.is_valid():
                    allocations = allocation_form.allocation_inputs(months)
                    try:
                        if payment is None:
                            services.payment_create(
                                profession=profession,
                                received_on=received_on,
                                amount=amount,
                                method=form.cleaned_data["method"],
                                notes=form.cleaned_data["notes"],
                                allocations=allocations,
                                student=student,
                                payer=payer,
                            )
                        else:
                            services.payment_update(
                                payment=payment,
                                received_on=received_on,
                                amount=amount,
                                method=form.cleaned_data["method"],
                                notes=form.cleaned_data["notes"],
                                allocations=allocations,
                                student=student,
                                payer=payer,
                            )
                    except ValidationError as error:
                        add_service_errors(form, error)
                    else:
                        messages.success(request, _("Paiement enregistré."))
                        return redirect(_target_url(student=student, payer=payer))
            else:
                is_proposal_refreshed = wants_save
                proposal = selectors.payment_allocation_propose(
                    amount=amount,
                    received_on=received_on,
                    student=student,
                    payer=payer,
                    exclude_payment=payment,
                )
                allocation_form = AllocationForm.for_months(
                    months, initial=_proposal_initial(proposal)
                )
            rows = _allocation_rows(
                months=months,
                allocation_form=allocation_form,
                student=student,
                payer=payer,
                received_on=received_on,
            )
    elif payment is not None:
        form = PaymentForm.for_payment(payment)
        months = selectors.allocatable_month_list(
            student=payment.student, payer=payment.payer, exclude_payment=payment
        )
        initial: dict[str, object] = {}
        for allocation in payment.allocations.all():
            field_name = AllocationForm.field_name(allocation.expected_payment)
            initial[field_name] = allocation.amount
        allocation_form = AllocationForm.for_months(months, initial=initial)
        token = _proposal_token(
            student=payment.student,
            payer=payment.payer,
            amount=payment.amount,
            received_on=payment.received_on,
        )
        rows = _allocation_rows(
            months=months,
            allocation_form=allocation_form,
            student=payment.student,
            payer=payment.payer,
            received_on=payment.received_on,
        )
    else:
        initial_payment: dict[str, object] = {
            "received_on": timezone.localdate(),
            "method": PaymentMethod.BANK_TRANSFER,
        }
        student_id = request.GET.get("student", "")
        payer_id = request.GET.get("payer", "")
        if student_id.isdigit():
            initial_student = student_get(
                profession=profession, student_id=int(student_id)
            )
            initial_payment["student"] = initial_student
            cancel_url = _target_url(student=initial_student, payer=None)
        elif payer_id.isdigit():
            initial_payer = payer_get(profession=profession, payer_id=int(payer_id))
            initial_payment["payer"] = initial_payer
            cancel_url = _target_url(student=None, payer=initial_payer)
        form = PaymentForm.for_profession(profession, initial=initial_payment)

    context = {
        "page_title": _("Paiement") if payment else _("Nouveau paiement"),
        "page_subtitle": _("Mensualité d'un élève ou d'une formule famille"),
        "form": form,
        "allocation_form": allocation_form,
        "allocation_rows": rows,
        "proposal": proposal,
        "proposed_for": token,
        "is_proposal_refreshed": is_proposal_refreshed,
        "action_save": ACTION_SAVE,
        "cancel_url": cancel_url,
    }
    return render(request, "accounting/payment_form.html", context)


@profession_required
def payment_create(request: ProfessionHttpRequest) -> HttpResponse:
    return _payment_form_response(request, payment=None)


@profession_required
def payment_update(request: ProfessionHttpRequest, payment_id: int) -> HttpResponse:
    payment = selectors.payment_get(
        profession=request.profession, payment_id=payment_id
    )
    if payment.is_one_off:
        return redirect("accounting:one_off_income_update", payment_id=payment.pk)
    return _payment_form_response(request, payment=payment)


@profession_required
def payment_delete(request: ProfessionHttpRequest, payment_id: int) -> HttpResponse:
    """Confirmation page, then deletion of a payment or a one-off income."""
    payment = selectors.payment_get(
        profession=request.profession, payment_id=payment_id
    )
    back_url = _target_url(student=payment.student, payer=payment.payer)
    if request.method == "POST":
        services.payment_delete(payment=payment)
        messages.success(request, _("Paiement supprimé."))
        return redirect(back_url)
    context = {
        "page_title": _("Supprimer le paiement"),
        "page_subtitle": _("Comptabilité"),
        "payment": payment,
        "cancel_url": back_url,
    }
    return render(request, "accounting/payment_confirm_delete.html", context)


# --- One-off income ---------------------------------------------------------


def _one_off_income_response(
    request: ProfessionHttpRequest, *, payment: Payment | None
) -> HttpResponse:
    profession = request.profession
    cancel_url = reverse("accounting:ledger_entry_list")
    if payment is not None:
        cancel_url = _target_url(student=payment.student, payer=None)
    if request.method == "POST":
        form = OneOffIncomeForm.for_profession(profession, data=request.POST)
        if form.is_valid():
            student: Student | None = form.cleaned_data["student"]
            try:
                if payment is None:
                    services.one_off_income_create(
                        profession=profession,
                        received_on=form.cleaned_data["received_on"],
                        amount=form.cleaned_data["amount"],
                        method=form.cleaned_data["method"],
                        label=form.cleaned_data["label"],
                        notes=form.cleaned_data["notes"],
                        student=student,
                    )
                else:
                    services.one_off_income_update(
                        payment=payment,
                        received_on=form.cleaned_data["received_on"],
                        amount=form.cleaned_data["amount"],
                        method=form.cleaned_data["method"],
                        label=form.cleaned_data["label"],
                        notes=form.cleaned_data["notes"],
                        student=student,
                    )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Recette ponctuelle enregistrée."))
                return redirect(_target_url(student=student, payer=None))
    elif payment is not None:
        form = OneOffIncomeForm.for_payment(payment)
    else:
        initial: dict[str, object] = {
            "received_on": timezone.localdate(),
            "method": PaymentMethod.BANK_TRANSFER,
        }
        student_id = request.GET.get("student", "")
        if student_id.isdigit():
            initial_student = student_get(
                profession=profession, student_id=int(student_id)
            )
            initial["student"] = initial_student
            cancel_url = _target_url(student=initial_student, payer=None)
        form = OneOffIncomeForm.for_profession(profession, initial=initial)
    context = {
        "page_title": _("Recette ponctuelle"),
        "page_subtitle": _("Cours à la carte, bon cadeau"),
        "form": form,
        "intro": _(
            "Une recette ponctuelle n'est attribuée à aucun mois : elle ne solde "
            "ni mensualité ni arriéré."
        ),
        "submit_label": _("Enregistrer"),
        "cancel_url": cancel_url,
    }
    return render(request, "form_page.html", context)


@profession_required
def one_off_income_create(request: ProfessionHttpRequest) -> HttpResponse:
    return _one_off_income_response(request, payment=None)


@profession_required
def one_off_income_update(
    request: ProfessionHttpRequest, payment_id: int
) -> HttpResponse:
    payment = selectors.payment_get(
        profession=request.profession, payment_id=payment_id
    )
    if not payment.is_one_off:
        raise Http404
    return _one_off_income_response(request, payment=payment)


# --- Expected payments ------------------------------------------------------


def _expected_payment_back_url(expected_payment: ExpectedPayment) -> str:
    return _target_url(student=expected_payment.student, payer=expected_payment.payer)


def _expected_payment_title(expected_payment: ExpectedPayment) -> str:
    return f"{expected_payment.target} · {expected_payment.month:%m.%Y}"


@profession_required
def expected_payment_cancel(
    request: ProfessionHttpRequest, expected_payment_id: int
) -> HttpResponse:
    expected_payment = selectors.expected_payment_get(
        profession=request.profession, expected_payment_id=expected_payment_id
    )
    back_url = _expected_payment_back_url(expected_payment)
    if request.method == "POST":
        form = ExpectedPaymentCancelForm(request.POST)
        if form.is_valid():
            try:
                services.expected_payment_cancel(
                    expected_payment=expected_payment,
                    reason=form.cleaned_data["reason"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Mois annulé."))
                return redirect(back_url)
    else:
        form = ExpectedPaymentCancelForm()
    context = {
        "page_title": _expected_payment_title(expected_payment),
        "page_subtitle": _("Annuler le mois"),
        "form": form,
        "intro": _(
            "Un mois annulé n'est plus dû et n'entre plus dans l'attribution des "
            "paiements. Il reste visible et peut être rétabli."
        ),
        "submit_label": _("Annuler le mois"),
        "cancel_url": back_url,
    }
    return render(request, "form_page.html", context)


@profession_required
@require_POST
def expected_payment_restore(
    request: ProfessionHttpRequest, expected_payment_id: int
) -> HttpResponse:
    expected_payment = selectors.expected_payment_get(
        profession=request.profession, expected_payment_id=expected_payment_id
    )
    back_url = _expected_payment_back_url(expected_payment)
    try:
        services.expected_payment_restore(expected_payment=expected_payment)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, _("Mois rétabli."))
    return redirect(back_url)


@profession_required
def expected_payment_amount_update(
    request: ProfessionHttpRequest, expected_payment_id: int
) -> HttpResponse:
    expected_payment = selectors.expected_payment_get(
        profession=request.profession, expected_payment_id=expected_payment_id
    )
    back_url = _expected_payment_back_url(expected_payment)
    if request.method == "POST":
        form = ExpectedPaymentAmountForm(request.POST)
        if form.is_valid():
            try:
                services.expected_payment_amount_update(
                    expected_payment=expected_payment,
                    amount=form.cleaned_data["amount"],
                )
            except ValidationError as error:
                add_service_errors(form, error)
            else:
                messages.success(request, _("Montant attendu modifié."))
                return redirect(back_url)
    else:
        form = ExpectedPaymentAmountForm(initial={"amount": expected_payment.amount})
    context = {
        "page_title": _expected_payment_title(expected_payment),
        "page_subtitle": _("Modifier le montant attendu"),
        "form": form,
        "intro": _(
            "Un montant modifié à la main n'est plus recalculé automatiquement, "
            "même si la formule change."
        ),
        "submit_label": _("Enregistrer"),
        "cancel_url": back_url,
    }
    return render(request, "form_page.html", context)

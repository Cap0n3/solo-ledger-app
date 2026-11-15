from collections.abc import Sequence
from decimal import Decimal
from typing import Self

from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _
from django_stubs_ext import StrOrPromise

from core.apps.accounts.models import Profession
from core.apps.students.models import Payer, Student
from core.apps.students.selectors import payer_list, student_list

from .models import ExpectedPayment, Payment, PaymentMethod
from .selectors import AllocatableMonth
from .services import AllocationInput

MINIMUM_AMOUNT = Decimal("0.01")


def _amount_field(
    *, label: StrOrPromise, min_value: Decimal = MINIMUM_AMOUNT
) -> forms.DecimalField:
    return forms.DecimalField(
        label=label,
        max_digits=10,
        decimal_places=2,
        min_value=min_value,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.05"}),
    )


def _date_field(
    *, label: StrOrPromise, required: bool = True, help_text: StrOrPromise = ""
) -> forms.DateField:
    return forms.DateField(
        label=label,
        required=required,
        help_text=help_text,
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}
        ),
    )


def _method_field() -> forms.ChoiceField:
    return forms.ChoiceField(
        label=_("Mode de paiement"),
        choices=PaymentMethod.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


def _notes_field() -> forms.CharField:
    return forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class PaymentForm(forms.Form):
    """A monthly payment: who paid, when, how much. Months are chosen below it."""

    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        label=_("Élève"),
        required=False,
        empty_label=_("Aucun"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    payer = forms.ModelChoiceField(
        queryset=Payer.objects.none(),
        label=_("Payeur (formule famille)"),
        required=False,
        empty_label=_("Aucun"),
        help_text=_(
            "À choisir à la place de l'élève lorsque le versement règle une "
            "formule famille."
        ),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    received_on = _date_field(label=_("Date de réception"))
    amount = _amount_field(label=_("Montant (CHF)"))
    method = _method_field()
    notes = _notes_field()

    @classmethod
    def for_profession(
        cls,
        profession: Profession,
        *,
        data: QueryDict | None = None,
        initial: dict[str, object] | None = None,
    ) -> Self:
        """A form whose student and payer choices are limited to the profession."""
        form = cls(data=data, initial=initial)
        student_field = form.fields["student"]
        if isinstance(student_field, forms.ModelChoiceField):
            student_field.queryset = student_list(profession=profession)
        payer_field = form.fields["payer"]
        if isinstance(payer_field, forms.ModelChoiceField):
            payer_field.queryset = payer_list(profession=profession)
        return form

    @classmethod
    def for_payment(cls, payment: Payment) -> Self:
        initial: dict[str, object] = {
            "student": payment.student,
            "payer": payment.payer,
            "received_on": payment.received_on,
            "amount": payment.amount,
            "method": payment.method,
            "notes": payment.notes,
        }
        return cls.for_profession(payment.profession, initial=initial)

    def clean_method(self) -> PaymentMethod:
        return PaymentMethod(self.cleaned_data["method"])

    def clean(self) -> dict[str, object] | None:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return None
        has_student = cleaned_data.get("student") is not None
        has_payer = cleaned_data.get("payer") is not None
        if has_student == has_payer and not self.errors:
            raise forms.ValidationError(
                _(
                    "Choisissez un élève, ou un payeur pour une formule famille, "
                    "mais pas les deux : un paiement concerne une seule personne."
                ),
                code="single_target",
            )
        return cleaned_data


class AllocationForm(forms.Form):
    """One optional amount per month still owed by the student or payer."""

    @staticmethod
    def field_name(expected_payment: ExpectedPayment) -> str:
        return f"month_{expected_payment.pk}"

    @classmethod
    def for_months(
        cls,
        months: Sequence[AllocatableMonth],
        *,
        data: QueryDict | None = None,
        initial: dict[str, object] | None = None,
    ) -> Self:
        form = cls(data=data, initial=initial)
        for month in months:
            form.fields[cls.field_name(month.expected_payment)] = forms.DecimalField(
                label=f"{month.expected_payment.month:%m.%Y}",
                required=False,
                max_digits=10,
                decimal_places=2,
                min_value=Decimal("0"),
                max_value=month.remaining,
                widget=forms.NumberInput(
                    attrs={"class": "form-control form-control-sm", "step": "0.05"}
                ),
            )
        return form

    def allocation_inputs(
        self, months: Sequence[AllocatableMonth]
    ) -> list[AllocationInput]:
        """The shares entered by the user, once the form is valid."""
        inputs: list[AllocationInput] = []
        for month in months:
            amount = self.cleaned_data.get(self.field_name(month.expected_payment))
            if amount is None or amount <= Decimal("0"):
                continue
            inputs.append(
                AllocationInput(expected_payment=month.expected_payment, amount=amount)
            )
        return inputs


class OneOffIncomeForm(forms.Form):
    """A one-off income: a single lesson or a gift voucher, entered freely."""

    label = forms.CharField(
        label=_("Libellé"),
        max_length=200,
        help_text=_("Par exemple « Bon cadeau 5 cours » ou « Cours à la carte »."),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    received_on = _date_field(label=_("Date de réception"))
    amount = _amount_field(label=_("Montant (CHF)"))
    method = _method_field()
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        label=_("Élève"),
        required=False,
        empty_label=_("Aucun"),
        help_text=_(
            "Facultatif. Rattachée à un élève, la recette apparaît sur sa fiche."
        ),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = _notes_field()

    @classmethod
    def for_profession(
        cls,
        profession: Profession,
        *,
        data: QueryDict | None = None,
        initial: dict[str, object] | None = None,
    ) -> Self:
        form = cls(data=data, initial=initial)
        student_field = form.fields["student"]
        if isinstance(student_field, forms.ModelChoiceField):
            student_field.queryset = student_list(profession=profession)
        return form

    @classmethod
    def for_payment(cls, payment: Payment) -> Self:
        initial: dict[str, object] = {
            "label": payment.label,
            "received_on": payment.received_on,
            "amount": payment.amount,
            "method": payment.method,
            "student": payment.student,
            "notes": payment.notes,
        }
        return cls.for_profession(payment.profession, initial=initial)

    def clean_method(self) -> PaymentMethod:
        return PaymentMethod(self.cleaned_data["method"])


class ExpectedPaymentCancelForm(forms.Form):
    reason = forms.CharField(
        label=_("Motif"),
        max_length=200,
        required=False,
        help_text=_("Facultatif, par exemple « accident » ou « absence forcée »."),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class ExpectedPaymentAmountForm(forms.Form):
    amount = _amount_field(label=_("Montant attendu (CHF)"), min_value=Decimal("0"))

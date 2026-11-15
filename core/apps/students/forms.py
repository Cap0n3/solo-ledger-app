from decimal import Decimal
from typing import Self

from django import forms
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from core.apps.accounts.models import Profession
from core.utils.forms import MonthField

from .models import Payer, Plan, Student
from .selectors import payer_list, plan_assignable_list

# Widgets carry the Bootstrap classes so templates stay free of per-field markup.


class PlanForm(forms.Form):
    name = forms.CharField(
        label=_("Nom"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    description = forms.CharField(
        label=_("Description"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    price = forms.DecimalField(
        label=_("Prix (CHF)"),
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "step": "0.01", "min": "0"}
        ),
    )
    kind = forms.ChoiceField(
        label=_("Type"),
        choices=Plan.Kind.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_(
            "Mensuelle : prix par mois. À la carte : prix par cours, saisi à la main."
        ),
    )

    @classmethod
    def for_plan(cls, plan: Plan) -> Self:
        return cls(
            initial={
                "name": plan.name,
                "description": plan.description,
                "price": plan.price,
                "kind": plan.kind,
            }
        )

    def clean_kind(self) -> Plan.Kind:
        return Plan.Kind(self.cleaned_data["kind"])


class PayerForm(forms.Form):
    name = forms.CharField(
        label=_("Nom"),
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    payment_reference_name = forms.CharField(
        label=_("Nom de référence pour les paiements"),
        max_length=150,
        required=False,
        help_text=_(
            "Nom tel qu'il apparaît sur les virements. Vide : le nom du payeur."
        ),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label=_("E-mail"),
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        label=_("Téléphone"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    @classmethod
    def for_payer(cls, payer: Payer) -> Self:
        return cls(
            initial={
                "name": payer.name,
                "payment_reference_name": payer.payment_reference_name,
                "email": payer.email,
                "phone": payer.phone,
                "notes": payer.notes,
            }
        )


# « En pause » is derived from the student's pauses and cannot be chosen.
STORED_STATUS_CHOICES = (
    (Student.Status.ACTIVE.value, Student.Status.ACTIVE.label),
    (Student.Status.ENDED.value, Student.Status.ENDED.label),
)


class StudentForm(forms.Form):
    first_name = forms.CharField(
        label=_("Prénom"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    last_name = forms.CharField(
        label=_("Nom"),
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label=_("E-mail"),
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        label=_("Téléphone"),
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    start_date = forms.DateField(
        label=_("Date de début des cours"),
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}
        ),
    )
    end_date = forms.DateField(
        label=_("Date de fin des cours"),
        required=False,
        help_text=_("Laisser vide tant que l'élève suit les cours."),
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}
        ),
    )
    status = forms.ChoiceField(
        label=_("Statut"),
        choices=STORED_STATUS_CHOICES,
        help_text=_("« En pause » se déduit des pauses saisies sur la fiche."),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    payer = forms.ModelChoiceField(
        queryset=Payer.objects.none(),
        label=_("Payeur"),
        required=False,
        empty_label=_("Aucun"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    payment_reference_name = forms.CharField(
        label=_("Nom de référence pour les paiements"),
        max_length=150,
        required=False,
        help_text=_(
            "Nom tel qu'il apparaît sur les virements. Vide : le nom de l'élève. "
            "Ignoré si un payeur est renseigné."
        ),
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.none(),
        label=_("Formule"),
        required=False,
        empty_label=_("Aucune pour le moment"),
        help_text=_("Attribuée dès le mois de la date de début."),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        label=_("Notes"),
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    @classmethod
    def for_profession(
        cls,
        profession: Profession,
        *,
        data: QueryDict | None = None,
        initial: dict[str, object] | None = None,
        include_plan: bool = True,
    ) -> Self:
        """A form whose payer and plan choices are limited to the profession."""
        form = cls(data=data, initial=initial)
        payer_field = form.fields["payer"]
        if isinstance(payer_field, forms.ModelChoiceField):
            payer_field.queryset = payer_list(profession=profession)
        if include_plan:
            plan_field = form.fields["plan"]
            if isinstance(plan_field, forms.ModelChoiceField):
                plan_field.queryset = plan_assignable_list(profession=profession)
        else:
            del form.fields["plan"]
        return form

    @classmethod
    def for_student(cls, student: Student) -> Self:
        """An unbound edit form; the plan is managed from the student page."""
        initial = {
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.email,
            "phone": student.phone,
            "start_date": student.start_date,
            "end_date": student.end_date,
            "status": student.status,
            "payer": student.payer,
            "payment_reference_name": student.payment_reference_name,
            "notes": student.notes,
        }
        return cls.for_profession(
            student.profession, initial=initial, include_plan=False
        )

    def clean_status(self) -> Student.Status:
        return Student.Status(self.cleaned_data["status"])


class PlanAssignForm(forms.Form):
    plan = forms.ModelChoiceField(
        queryset=Plan.objects.none(),
        label=_("Formule"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    starts_on = MonthField(label=_("À partir du mois"))

    @classmethod
    def for_profession(
        cls,
        profession: Profession,
        *,
        data: QueryDict | None = None,
        initial: dict[str, object] | None = None,
        monthly_only: bool = False,
    ) -> Self:
        form = cls(data=data, initial=initial)
        plan_field = form.fields["plan"]
        if isinstance(plan_field, forms.ModelChoiceField):
            plan_field.queryset = plan_assignable_list(
                profession=profession, monthly_only=monthly_only
            )
        return form


class PlanAssignmentEndForm(forms.Form):
    last_month = MonthField(
        label=_("Dernier mois couvert"),
        help_text=_("La formule reste en vigueur jusqu'à ce mois inclus."),
    )


class StudentPauseForm(forms.Form):
    starts_on = forms.DateField(
        label=_("Début de la pause"),
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}
        ),
    )
    ends_on = forms.DateField(
        label=_("Fin de la pause"),
        required=False,
        help_text=_(
            "Laisser vide tant que la reprise n'est pas connue. Seuls les mois "
            "entièrement compris dans la pause ne sont pas attendus."
        ),
        widget=forms.DateInput(
            format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}
        ),
    )

from decimal import Decimal
from typing import Self

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Plan

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

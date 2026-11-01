"""Form helpers shared across apps."""

from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dates import MONTHS
from django_stubs_ext import StrOrPromise

YEARS_BEFORE = 3
YEARS_AFTER = 2


def add_service_errors(form: forms.Form, error: ValidationError) -> None:
    """Show a business refusal raised by a service as non-field errors.

    Field names in a service error may not exist on the form, so the messages
    are flattened instead of being passed to `add_error` as a dict.
    """
    for message in error.messages:
        form.add_error(None, message)


def default_years() -> list[int]:
    current_year = timezone.localdate().year
    return list(range(current_year - YEARS_BEFORE, current_year + YEARS_AFTER + 1))


class MonthSelectWidget(forms.MultiWidget):
    """Two selects, month then year, for a first-of-month date.

    `<input type="month">` is not supported by desktop Safari and Firefox.
    """

    def __init__(self, years: list[int]) -> None:
        select_attrs = {"class": "form-select d-inline-block w-auto me-2"}
        month_choices = [(str(number), name) for number, name in MONTHS.items()]
        year_choices = [(str(year), str(year)) for year in years]
        widgets = (
            forms.Select(choices=month_choices, attrs=select_attrs),
            forms.Select(choices=year_choices, attrs=select_attrs),
        )
        super().__init__(widgets)

    def decompress(self, value: date | None) -> list[str | None]:
        if value is None:
            return [None, None]
        return [str(value.month), str(value.year)]


class MonthField(forms.MultiValueField):
    """A billing month entered as month + year, cleaned to its first day."""

    def __init__(
        self,
        *,
        label: StrOrPromise,
        required: bool = True,
        help_text: StrOrPromise = "",
        years: list[int] | None = None,
    ) -> None:
        year_list = years if years is not None else default_years()
        month_choices = [(str(number), name) for number, name in MONTHS.items()]
        year_choices = [(str(year), str(year)) for year in year_list]
        fields = (
            forms.ChoiceField(choices=month_choices),
            forms.ChoiceField(choices=year_choices),
        )
        super().__init__(
            fields=fields,
            widget=MonthSelectWidget(year_list),
            label=label,
            required=required,
            help_text=help_text,
            require_all_fields=True,
        )

    def compress(self, data_list: list[str]) -> date | None:
        if not data_list:
            return None
        month, year = data_list
        return date(int(year), int(month), 1)

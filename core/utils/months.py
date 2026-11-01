"""Helpers for billing months, represented by the first day of the month."""

from datetime import date

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_month_start(value: date) -> None:
    """Model validator: billing months are stored as the first day of a month."""
    if value.day != 1:
        raise ValidationError(
            _("La date doit être le premier jour d'un mois."), code="not_month_start"
        )


def month_start(day: date) -> date:
    return day.replace(day=1)


def month_add(month: date, months: int) -> date:
    """Shift a first-of-month date by a number of months (negative allowed)."""
    month_index = month.year * 12 + (month.month - 1) + months
    year, month_offset = divmod(month_index, 12)
    return date(year, month_offset + 1, 1)


def month_span(first_month: date, last_month: date) -> int:
    """Number of months from `first_month` to `last_month`, both inclusive."""
    year_months = (last_month.year - first_month.year) * 12
    return year_months + (last_month.month - first_month.month) + 1


def month_range(first_month: date, last_month: date) -> list[date]:
    """Every first-of-month date from `first_month` to `last_month`, inclusive."""
    months: list[date] = []
    current = month_start(first_month)
    end = month_start(last_month)
    while current <= end:
        months.append(current)
        current = month_add(current, 1)
    return months

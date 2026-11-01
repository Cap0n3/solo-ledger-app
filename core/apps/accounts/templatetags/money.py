"""Swiss amount formatting: 1’234.50 CHF.

Django's fr_CH formats use a comma and a space, so amounts go through this
filter instead of localization settings (which would also format years).
"""

from decimal import ROUND_HALF_UP, Decimal

from django import template

register = template.Library()

THOUSANDS_SEPARATOR = "’"
NO_AMOUNT = "—"


@register.filter
def chf(value: Decimal | None) -> str:
    if value is None:
        return NO_AMOUNT
    amount = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    integer_part, decimal_part = f"{abs(amount):.2f}".split(".")
    groups: list[str] = []
    while len(integer_part) > 3:
        groups.insert(0, integer_part[-3:])
        integer_part = integer_part[:-3]
    groups.insert(0, integer_part)
    return f"{sign}{THOUSANDS_SEPARATOR.join(groups)}.{decimal_part} CHF"

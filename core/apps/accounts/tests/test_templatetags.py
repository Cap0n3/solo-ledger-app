from decimal import Decimal

from core.apps.accounts.templatetags.money import chf


def test_chf_formats_with_swiss_thousands_separator():
    assert chf(Decimal("1234.5")) == "1’234.50 CHF"
    assert chf(Decimal("280")) == "280.00 CHF"
    assert chf(Decimal("1234567.891")) == "1’234’567.89 CHF"
    assert chf(Decimal("-79.6")) == "-79.60 CHF"


def test_chf_shows_a_dash_without_amount():
    assert chf(None) == "—"

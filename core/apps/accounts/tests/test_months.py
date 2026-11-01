import datetime

from core.utils.months import month_add, month_range, month_span, month_start


def test_month_start_drops_the_day():
    assert month_start(datetime.date(2026, 10, 15)) == datetime.date(2026, 10, 1)


def test_month_add_crosses_year_boundaries_in_both_directions():
    assert month_add(datetime.date(2026, 11, 1), 3) == datetime.date(2027, 2, 1)
    assert month_add(datetime.date(2026, 1, 1), -1) == datetime.date(2025, 12, 1)
    assert month_add(datetime.date(2026, 9, 1), 0) == datetime.date(2026, 9, 1)


def test_month_span_is_inclusive():
    assert month_span(datetime.date(2026, 9, 1), datetime.date(2027, 7, 1)) == 11
    assert month_span(datetime.date(2026, 9, 1), datetime.date(2026, 9, 1)) == 1


def test_month_range_lists_every_month():
    months = month_range(datetime.date(2026, 11, 1), datetime.date(2027, 2, 1))

    assert months == [
        datetime.date(2026, 11, 1),
        datetime.date(2026, 12, 1),
        datetime.date(2027, 1, 1),
        datetime.date(2027, 2, 1),
    ]

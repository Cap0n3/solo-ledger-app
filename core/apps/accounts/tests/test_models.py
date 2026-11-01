import datetime

import pytest
from django.core.exceptions import ValidationError

from .factories import LessonYearFactory

pytestmark = pytest.mark.django_db


def test_lesson_year_name_spans_two_calendar_years():
    lesson_year = LessonYearFactory.create(
        first_month=datetime.date(2026, 9, 1), last_month=datetime.date(2027, 7, 1)
    )

    assert lesson_year.name == "2026-2027"


def test_lesson_year_name_within_one_calendar_year():
    lesson_year = LessonYearFactory.create(
        first_month=datetime.date(2026, 1, 1), last_month=datetime.date(2026, 6, 1)
    )

    assert lesson_year.name == "2026"


def test_lesson_year_months_and_contains():
    lesson_year = LessonYearFactory.create(
        first_month=datetime.date(2026, 9, 1), last_month=datetime.date(2027, 7, 1)
    )

    assert len(lesson_year.months) == 11
    assert lesson_year.months[0] == datetime.date(2026, 9, 1)
    assert lesson_year.months[-1] == datetime.date(2027, 7, 1)
    assert lesson_year.contains(datetime.date(2026, 12, 1))
    assert not lesson_year.contains(datetime.date(2026, 8, 1))


def test_lesson_year_rejects_more_than_twelve_months():
    lesson_year = LessonYearFactory.create()
    lesson_year.last_month = datetime.date(2027, 9, 1)

    with pytest.raises(ValidationError) as excinfo:
        lesson_year.full_clean()

    assert "last_month" in excinfo.value.error_dict


def test_lesson_year_rejects_last_month_before_first():
    lesson_year = LessonYearFactory.create()
    lesson_year.last_month = datetime.date(2026, 8, 1)

    with pytest.raises(ValidationError) as excinfo:
        lesson_year.full_clean()

    assert "last_month" in excinfo.value.error_dict


def test_lesson_year_months_must_be_first_of_month():
    lesson_year = LessonYearFactory.create()
    lesson_year.first_month = datetime.date(2026, 9, 15)

    with pytest.raises(ValidationError) as excinfo:
        lesson_year.full_clean()

    assert "first_month" in excinfo.value.error_dict

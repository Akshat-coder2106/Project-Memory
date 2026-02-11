"""Regression tests for datetime intent classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api import _datetime_mode as api_datetime_mode
from api import _is_datetime_request as api_is_datetime_request
from main import _datetime_mode as main_datetime_mode
from main import _is_datetime_request as main_is_datetime_request


def test_food_query_with_tomorrow_not_datetime():
    text = "what should i eat tommorow"
    assert api_datetime_mode(text) == "none"
    assert api_is_datetime_request(text) is False
    assert main_datetime_mode(text) == "none"
    assert main_is_datetime_request(text) is False


def test_food_query_with_numeric_days_not_datetime():
    text = "what should I eat in 3 days"
    assert api_datetime_mode(text) == "none"
    assert api_is_datetime_request(text) is False
    assert main_datetime_mode(text) == "none"
    assert main_is_datetime_request(text) is False


def test_food_query_with_today_not_datetime():
    text = "what should i eat today"
    assert api_datetime_mode(text) == "none"
    assert api_is_datetime_request(text) is False
    assert main_datetime_mode(text) == "none"
    assert main_is_datetime_request(text) is False


def test_direct_datetime_queries_still_work():
    assert api_datetime_mode("what time is it") == "time"
    assert api_datetime_mode("what is tomorrow date") == "date"
    assert api_datetime_mode("what date will it be in 3 days") == "date"
    assert api_datetime_mode("what year is it") == "date"

    assert main_datetime_mode("what time is it") == "time"
    assert main_datetime_mode("what is tomorrow date") == "date"
    assert main_datetime_mode("what date will it be in 3 days") == "date"
    assert main_datetime_mode("what year is it") == "date"

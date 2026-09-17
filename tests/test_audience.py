import pytest

from app.audience import CUSTOMER, STAFF, parse_audience


def test_parse_audience_defaults_and_accepts_staff():
    assert parse_audience(None) == CUSTOMER
    assert parse_audience("Customer") == CUSTOMER
    assert parse_audience("staff") == STAFF


def test_parse_audience_rejects_unknown():
    with pytest.raises(ValueError):
        parse_audience("admin")
    with pytest.raises(ValueError):
        parse_audience(" ")

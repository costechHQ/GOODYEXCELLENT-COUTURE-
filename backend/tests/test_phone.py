import pytest

from app.core.phone import normalise_phone


@pytest.mark.parametrize(
    "raw",
    ["08012345678", "0801 234 5678", "0801-234-5678", "+2348012345678", "2348012345678", "+234 (801) 234-5678"],
)
def test_nigerian_formats_become_one_canonical_form(raw):
    assert normalise_phone(raw) == "+2348012345678"


def test_other_international_numbers_are_kept():
    assert normalise_phone("+44 7911 123456") == "+447911123456"


@pytest.mark.parametrize(
    "raw", ["", "abc", "12345", "0601234567", "080123456", "08012345678901", "+0123456789", "44 7911 123456"]
)
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(ValueError):
        normalise_phone(raw)

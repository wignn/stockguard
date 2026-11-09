import importlib

import pytest


def numbers():
    return importlib.import_module("stokguard.core.numbers")


@pytest.mark.parametrize(
    ("value", "step", "expected"),
    [("18", 1000, 18000), ("1.125", 1, 1125), ("0", 1000, 0), ("0.001", 1, 1)],
)
def test_quantity_uses_exact_thousandths(value, step, expected):
    assert numbers().parse_quantity(value, step) == expected


@pytest.mark.parametrize("value", ["1.1", "1e3", "NaN", "Infinity", "-1", "+1", 18, "1.0000"])
def test_invalid_quantity_is_rejected(value):
    with pytest.raises(ValueError):
        numbers().parse_quantity(value, 1000)


def test_quantity_overflow_is_rejected():
    with pytest.raises(ValueError):
        numbers().parse_quantity("9223372036854775.808", 1)


@pytest.mark.parametrize(
    ("milli", "expected"), [(18000, "18"), (-1125, "-1.125"), (0, "0"), (10, "0.01")]
)
def test_quantity_serialization_preserves_precision(milli, expected):
    assert numbers().format_quantity(milli) == expected


def test_rupiah_is_integer_and_valuation_rounds_half_away_from_zero():
    assert numbers().parse_rupiah("9007199254740993") == 9007199254740993
    assert numbers().value_delta(-1500, 101) == -152
    assert numbers().value_delta(1500, 101) == 152
    for value in ["1.5", "-1", "1e3", 1000, "9223372036854775808"]:
        with pytest.raises(ValueError):
            numbers().parse_rupiah(value)


def test_invalid_steps_and_valuation_overflow_rejected():
    for step in [0, -1, True, 1.5]:
        with pytest.raises(ValueError):
            numbers().parse_quantity("1", step)
    with pytest.raises(ValueError):
        numbers().value_delta(9223372036854775807, 9223372036854775807)

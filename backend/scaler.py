from __future__ import annotations

from math import isclose
from typing import Any

from pint import UnitRegistry


UNIT_MAP = {
    # volume
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tablespoon",
    "tablespoon": "tablespoon",
    "tablespoons": "tablespoon",
    "tsp": "teaspoon",
    "teaspoon": "teaspoon",
    "teaspoons": "teaspoon",
    "ml": "milliliter",
    "milliliter": "milliliter",
    "l": "liter",
    "liter": "liter",
    "fl oz": "fluid_ounce",
    "fluid oz": "fluid_ounce",
    # weight
    "g": "gram",
    "gram": "gram",
    "grams": "gram",
    "kg": "kilogram",
    "oz": "ounce",
    "ounce": "ounce",
    "ounces": "ounce",
    "lb": "pound",
    "pound": "pound",
    "pounds": "pound",
}

METRIC_UNITS = {"gram", "kilogram", "milliliter", "liter"}
IMPERIAL_UNITS = {"ounce", "pound", "cup", "tablespoon", "teaspoon", "fluid_ounce"}

PLURAL_UNITS = {
    "cup": "cups",
    "tablespoon": "tablespoons",
    "teaspoon": "teaspoons",
    "ounce": "ounces",
    "pound": "pounds",
    "gram": "grams",
    "milliliter": "ml",
    "liter": "liters",
    "fluid_ounce": "fl oz",
}

_METRIC_TARGETS = {
    "cup": "milliliter",
    "tablespoon": "milliliter",
    "teaspoon": "milliliter",
    "fluid_ounce": "milliliter",
    "ounce": "gram",
    "pound": "kilogram",
}
_IMPERIAL_TARGETS = {
    "gram": "ounce",
    "kilogram": "pound",
    "milliliter": "fluid_ounce",
    "liter": "fluid_ounce",
}
_FRACTIONS = {
    0.125: "⅛",
    0.25: "¼",
    1 / 3: "⅓",
    0.5: "½",
    2 / 3: "⅔",
    0.75: "¾",
    0.875: "⅞",
}
_ureg = UnitRegistry()


def to_fraction_str(value: float) -> str:
    """Return a human-friendly quantity string using common cooking fractions."""
    if isclose(value, round(value), abs_tol=1e-9):
        return str(int(round(value)))

    whole = int(value)
    remainder = value - whole
    nearest_eighth = round(remainder * 8) / 8

    if nearest_eighth in _FRACTIONS and isclose(remainder, nearest_eighth, abs_tol=0.025):
        symbol = _FRACTIONS[nearest_eighth]
        return f"{whole if whole else ''}{symbol}"

    for fraction, symbol in ((1 / 3, "⅓"), (2 / 3, "⅔")):
        if isclose(remainder, fraction, abs_tol=0.025):
            return f"{whole if whole else ''}{symbol}"

    rounded = round(value, 1)
    if isclose(rounded, round(rounded), abs_tol=1e-9):
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def scale_ingredients(
    ingredients: list[dict],
    original_servings: int,
    target_servings: int,
    unit_system: str = "imperial",
) -> list[dict]:
    """Return scaled ingredients with display quantities, without mutating input."""
    if unit_system not in {"imperial", "metric"}:
        raise ValueError("unit_system must be 'imperial' or 'metric'")

    base_servings = original_servings or target_servings or 1
    factor = target_servings / base_servings
    scaled: list[dict] = []

    for ingredient in ingredients:
        quantity = _float_or_zero(ingredient.get("quantity"))
        raw_unit = str(ingredient.get("unit") or "").strip()
        scaled_quantity = quantity * factor
        display_quantity = scaled_quantity
        display_unit = raw_unit

        if scaled_quantity and raw_unit:
            canonical_unit = UNIT_MAP.get(raw_unit.lower())
            if canonical_unit:
                display_quantity, display_unit = _convert_for_display(
                    scaled_quantity,
                    canonical_unit,
                    unit_system,
                )

        out = dict(ingredient)
        out["quantity"] = scaled_quantity
        out["unit"] = raw_unit
        out["display_quantity"] = to_fraction_str(display_quantity)
        out["display_unit"] = _display_unit(display_unit, display_quantity)
        scaled.append(out)

    return scaled


def _convert_for_display(
    quantity: float,
    canonical_unit: str,
    unit_system: str,
) -> tuple[float, str]:
    if unit_system == "metric" and canonical_unit in IMPERIAL_UNITS:
        target_unit = _METRIC_TARGETS.get(canonical_unit)
    elif unit_system == "imperial" and canonical_unit in METRIC_UNITS:
        target_unit = _IMPERIAL_TARGETS.get(canonical_unit)
    else:
        target_unit = None

    if not target_unit:
        return quantity, canonical_unit

    try:
        converted = (quantity * _ureg(UNIT_MAP.get(canonical_unit, canonical_unit))).to(
            target_unit
        )
    except Exception:
        return quantity, canonical_unit

    return float(converted.magnitude), target_unit


def _display_unit(unit: str, quantity: float) -> str:
    if not unit:
        return ""
    singular = _singular_display_unit(unit)
    if isclose(_display_round_value(quantity), 1.0, abs_tol=1e-9):
        return singular
    return PLURAL_UNITS.get(unit, unit)


def _singular_display_unit(unit: str) -> str:
    if unit == "fluid_ounce":
        return "fl oz"
    return unit


def _display_round_value(value: float) -> float:
    if isclose(value, round(value), abs_tol=1e-9):
        return float(round(value))
    remainder = value - int(value)
    for fraction in _FRACTIONS:
        if isclose(remainder, fraction, abs_tol=0.025):
            return int(value) + fraction
    return round(value, 1)


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

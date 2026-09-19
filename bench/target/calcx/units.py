from __future__ import annotations

from dataclasses import dataclass

# Linear units: factor to the base unit of their dimension.
LINEAR = {
    # length (base: m)
    "mm": ("length", 0.001), "cm": ("length", 0.01), "m": ("length", 1.0), "km": ("length", 1000.0),
    "in": ("length", 0.0254), "ft": ("length", 0.3048), "mi": ("length", 1609.344),
    # mass (base: kg)
    "g": ("mass", 0.001), "kg": ("mass", 1.0), "lb": ("mass", 0.45359237), "oz": ("mass", 0.028349523125),
    # time (base: s)
    "ms": ("time", 0.001), "s": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0), "d": ("time", 86400.0),
}

# Affine units (temperature): (dimension, to_base(x), from_base(x))
AFFINE = {
    "K": ("temp", lambda x: x, lambda x: x),
    "C": ("temp", lambda x: x + 273.15, lambda x: x - 273.15),
    "F": ("temp", lambda x: (x - 32) * 5 / 9 + 273.15, lambda x: (x - 273.15) * 9 / 5 + 32),
}


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str

    def __str__(self) -> str:
        return f"{self.value:g} {self.unit}"


def dimension(unit: str) -> str:
    if unit in LINEAR:
        return LINEAR[unit][0]
    if unit in AFFINE:
        return AFFINE[unit][0]
    raise UnitError(f"unknown unit {unit!r}")


def to_base(q: Quantity) -> float:
    if q.unit in LINEAR:
        return q.value * LINEAR[q.unit][1]
    return AFFINE[q.unit][1](q.value)


def from_base(value: float, unit: str) -> float:
    if unit in LINEAR:
        return value / LINEAR[unit][1]
    return AFFINE[unit][2](value)


def convert(q: Quantity, unit: str) -> Quantity:
    """Convert q to `unit`. Raises UnitError if the dimensions differ."""
    if dimension(q.unit) != dimension(unit):
        raise UnitError(f"cannot convert {q.unit} to {unit}")
    return Quantity(from_base(to_base(q), unit), unit)

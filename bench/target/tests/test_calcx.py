import math

import pytest

from calcx import Quantity, calc, convert, format_report, parse, tokenize
from calcx.evaluator import EvalError
from calcx.parser import ParseError
from calcx.report import evaluate_batch
from calcx.tokenizer import TokenizeError
from calcx.units import UnitError


# --- tokenizer -----------------------------------------------------------
def test_tokenize_basic():
    kinds = [(t.kind, t.value) for t in tokenize("1 + 2.5*x")]
    assert kinds == [("num", "1"), ("op", "+"), ("num", "2.5"), ("op", "*"), ("name", "x")]


def test_tokenize_leading_dot_and_power():
    assert [t.value for t in tokenize(".5 ** 2")] == [".5", "**", "2"]


def test_tokenize_rejects_garbage():
    with pytest.raises(TokenizeError):
        tokenize("1 $ 2")


# --- parser --------------------------------------------------------------
def test_precedence():
    assert calc("1 + 2 * 3") == 7
    assert calc("(1 + 2) * 3") == 9


def test_left_associative_subtraction():
    assert calc("10 - 4 - 3") == 3


def test_right_associative_power():
    assert calc("2 ^ 3 ^ 2") == 512
    assert calc("2 ** 3 ** 2") == 512


def test_unary_minus():
    assert calc("-2 ^ 2") == 4  # (-2)^2 under our unary-binds-tighter grammar
    assert calc("3 - -2") == 5


def test_trailing_input_is_error():
    with pytest.raises(ParseError):
        parse(tokenize("1 2"))


# --- evaluator -----------------------------------------------------------
def test_variables_and_functions():
    assert calc("sqrt(x) + abs(-3)", {"x": 16}) == 7
    assert calc("max(1, 5, 3) - min(4, 2)") == 3


def test_avg_and_round():
    assert calc("avg(1, 2, 3, 4)") == 2.5
    assert calc("round(2.567, 2)") == 2.57


def test_modulo_follows_python_sign_for_positive():
    assert calc("7 % 3") == 1
    assert calc("7.5 % 2") == 1.5


def test_division_by_zero():
    with pytest.raises(EvalError):
        calc("1 / 0")


def test_unknown_variable():
    with pytest.raises(EvalError, match="unknown variable"):
        calc("y + 1")


# --- units ---------------------------------------------------------------
def test_convert_linear():
    assert convert(Quantity(1, "km"), "m").value == 1000
    assert math.isclose(convert(Quantity(1, "mi"), "km").value, 1.609344)


def test_convert_temperature():
    assert math.isclose(convert(Quantity(100, "C"), "F").value, 212)
    assert math.isclose(convert(Quantity(32, "F"), "K").value, 273.15)
    assert math.isclose(convert(Quantity(0, "K"), "C").value, -273.15)


def test_convert_dimension_mismatch():
    with pytest.raises(UnitError):
        convert(Quantity(1, "kg"), "m")


def test_to_function_in_expression():
    env = {"km": "km", "m": "m"}
    assert calc("to(2.5, km, m) + 1", env) == 2501


# --- report --------------------------------------------------------------
def test_evaluate_batch_isolates_errors():
    rows = evaluate_batch(["1+1", "1/0", "2*x"], {"x": 4})
    assert rows[0] == ("1+1", "2")
    assert rows[1][1].startswith("error:")
    assert rows[2] == ("2*x", "8")


def test_format_report_alignment():
    out = format_report([("1+1", "2"), ("sqrt(144)", "12")], title="T")
    lines = out.splitlines()
    assert lines[0] == "T"
    assert lines[1] == "expr       result"
    assert lines[2] == "---------  ------"
    assert lines[3] == "1+1             2"
    assert lines[4] == "sqrt(144)      12"
    assert lines[5] == "2/2 ok"


def test_format_report_counts_errors_as_not_ok():
    rows = evaluate_batch(["1+1", "1/0", "2*3"])
    assert format_report(rows).splitlines()[-1] == "2/3 ok"


def test_format_report_empty():
    assert format_report([], title="X") == "X\n(no rows)"

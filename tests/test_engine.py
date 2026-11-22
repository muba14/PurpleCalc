import math

import pytest

from purplecalc.engine import CalcError, evaluate, format_number, try_preview


def calc(expr, degrees=True):
    return format_number(evaluate(expr, degrees))


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("sin(30)×√(16)+2^8", "258"),  # the example from the design
        ("1+2×3", "7"),
        ("(1+2)×3", "9"),
        ("10÷4", "2.5"),
        ("2^3^2", "512"),  # right associative
        ("−2^2", "-4"),
        ("(−2)^2", "4"),
        ("0.1+0.2", "0.3"),
        ("5!", "120"),
        ("0!", "1"),
        ("50%", "0.5"),
        ("200×10%", "20"),
        ("2π", str(format_number(2 * math.pi))),
        ("3(4)", "12"),
        ("2sin(30)", "1"),
        ("abs(−7)", "7"),
        ("log(1000)", "3"),
        ("ln(e)", "1"),
        ("∛(27)", "3"),
        ("∛(−8)", "-2"),
        ("sin⁻¹(0.5)", "30"),
        ("cos(90)", "0"),
        ("sin(180)", "0"),
        ("tan(45)", "1"),
        ("10^(2)", "100"),
        ("e^(0)", "1"),
        ("1÷4^2", "0.0625"),
        ("2^10−24", "1000"),
        ("1.5E+3+1", "1501"),
        ("√(16", "4"),  # auto-closes parentheses
    ],
)
def test_expressions(expr, expected):
    assert calc(expr) == expected


def test_radians_mode():
    assert calc("sin(π÷2)", degrees=False) == "1"
    assert calc("cos(π)", degrees=False) == "-1"
    assert calc("tan⁻¹(1)", degrees=False) == format_number(math.pi / 4)


@pytest.mark.parametrize(
    "expr",
    ["1÷0", "√(−1)", "log(0)", "ln(−1)", "tan(90)", "(−3)!", "171!", "sin⁻¹(2)", "1+", "×2", "", "2..3", "10^999"],
)
def test_errors(expr):
    with pytest.raises(CalcError):
        evaluate(expr)


def test_preview_is_quiet_for_incomplete_input():
    assert try_preview("5+") is None
    assert try_preview("") is None
    assert try_preview("sin(") is None
    assert try_preview("2+3") == "5"


@pytest.mark.parametrize(
    "value, expected",
    [
        (1e20, "1E+20"),
        (-123456789012345678.0, "-1.2345678901E+17"),
        (1.5e-12, "1.5E-12"),
        (0.000123, "0.000123"),
        (123456789.123, "123456789.123"),
        (-0.0, "0"),
        (1 / 3, "0.333333333333"),
    ],
)
def test_format(value, expected):
    assert format_number(value) == expected


def test_scientific_output_roundtrips():
    big = format_number(evaluate("2^60"))
    assert "E" in big
    assert evaluate(big + "×2") == pytest.approx(2.0**61, rel=1e-9)

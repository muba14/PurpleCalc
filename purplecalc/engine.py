"""Safe expression engine for PurpleCalc.

The expression is parsed with a small recursive-descent parser — ``eval`` is
never used. The engine understands exactly what the UI shows on screen
(``×``, ``÷``, ``−``, ``√(``, ``sin⁻¹(`` …) as well as plain ASCII.

Grammar (lowest to highest precedence)::

    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/') unary | <implicit ×> power)*
    unary   := ('+' | '-') unary | power
    power   := postfix ('^' unary)?          # right associative, -2^2 = -4
    postfix := primary ('!' | '%')*
    primary := NUMBER | 'π' | 'e' | FUNC '(' expr ')' | '(' expr ')'
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

__all__ = ["CalcError", "evaluate", "try_preview", "format_number", "FUNCTIONS"]


class CalcError(Exception):
    """Raised for any invalid or undefined expression."""


# --------------------------------------------------------------------------- #
# Functions
# --------------------------------------------------------------------------- #
def _sin(x: float, deg: bool) -> float:
    return round(math.sin(math.radians(x) if deg else x), 15)


def _cos(x: float, deg: bool) -> float:
    return round(math.cos(math.radians(x) if deg else x), 15)


def _tan(x: float, deg: bool) -> float:
    if deg and math.isclose(math.fmod(abs(x), 180.0), 90.0, abs_tol=1e-12):
        raise CalcError("tan undefined")
    return round(math.tan(math.radians(x) if deg else x), 15)


def _inverse(fn):
    def wrapped(x: float, deg: bool) -> float:
        try:
            r = fn(x)
        except ValueError as exc:
            raise CalcError("domain") from exc
        return math.degrees(r) if deg else r

    return wrapped


def _log10(x: float, _deg: bool) -> float:
    if x <= 0:
        raise CalcError("log domain")
    return math.log10(x)


def _ln(x: float, _deg: bool) -> float:
    if x <= 0:
        raise CalcError("ln domain")
    return math.log(x)


def _sqrt(x: float, _deg: bool) -> float:
    if x < 0:
        raise CalcError("sqrt domain")
    return math.sqrt(x)


def _cbrt(x: float, _deg: bool) -> float:
    return math.copysign(abs(x) ** (1.0 / 3.0), x) if x else 0.0


FUNCTIONS = {
    # display name : implementation(x, degrees_mode)
    "sin⁻¹": _inverse(math.asin),
    "cos⁻¹": _inverse(math.acos),
    "tan⁻¹": _inverse(math.atan),
    "asin": _inverse(math.asin),
    "acos": _inverse(math.acos),
    "atan": _inverse(math.atan),
    "sin": _sin,
    "cos": _cos,
    "tan": _tan,
    "log": _log10,
    "ln": _ln,
    "sqrt": _sqrt,
    "√": _sqrt,
    "∛": _cbrt,
    "abs": lambda x, _d: abs(x),
}
# Longest names first so "sin⁻¹" wins over "sin".
_FUNC_NAMES = sorted(FUNCTIONS, key=len, reverse=True)

_CHAR_MAP = {"×": "*", "÷": "/", "−": "-", "–": "-", "·": "*", "x": "*", "X": "*", ",": "."}


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Tok:
    kind: str  # num | op | func | const | lp | rp | post
    value: object


def tokenize(text: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or ch == ".":
            j = i
            while j < n and (text[j].isdigit() or text[j] == "."):
                j += 1
            # Scientific notation uses a capital E (lower-case e is Euler's number).
            if j < n and text[j] == "E":
                k = j + 1
                if k < n and text[k] in "+-−":
                    k += 1
                if k < n and text[k].isdigit():
                    while k < n and text[k].isdigit():
                        k += 1
                    j = k
            raw = text[i:j].replace("−", "-")
            if raw.count(".") > 1 or raw == ".":
                raise CalcError("bad number")
            toks.append(Tok("num", float(raw)))
            i = j
            continue
        name = next((f for f in _FUNC_NAMES if text.startswith(f, i)), None)
        if name is not None:
            toks.append(Tok("func", FUNCTIONS[name]))
            i += len(name)
            continue
        if ch in ("π",) or text.startswith("pi", i):
            toks.append(Tok("const", math.pi))
            i += 1 if ch == "π" else 2
            continue
        if ch == "e":
            toks.append(Tok("const", math.e))
            i += 1
            continue
        ch = _CHAR_MAP.get(ch, ch)
        if ch in "+-*/^":
            toks.append(Tok("op", ch))
        elif ch == "(":
            toks.append(Tok("lp", ch))
        elif ch == ")":
            toks.append(Tok("rp", ch))
        elif ch in "!%":
            toks.append(Tok("post", ch))
        else:
            raise CalcError(f"unexpected {ch!r}")
        i += 1
    return toks


# --------------------------------------------------------------------------- #
# Parser / evaluator
# --------------------------------------------------------------------------- #
def _factorial(x: float) -> float:
    if x < 0 and float(x).is_integer():
        raise CalcError("factorial domain")
    if float(x).is_integer():
        if x > 170:
            raise CalcError("overflow")
        return float(math.factorial(int(x)))
    try:
        return math.gamma(x + 1)
    except (ValueError, OverflowError) as exc:
        raise CalcError("factorial domain") from exc


class _Parser:
    def __init__(self, toks: list[Tok], degrees: bool):
        self.toks = toks
        self.pos = 0
        self.deg = degrees

    def peek(self) -> Tok | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def take(self) -> Tok:
        tok = self.peek()
        if tok is None:
            raise CalcError("unexpected end")
        self.pos += 1
        return tok

    def parse(self) -> float:
        if not self.toks:
            raise CalcError("empty")
        value = self.expr()
        if self.peek() is not None:
            raise CalcError("trailing input")
        return value

    def expr(self) -> float:
        value = self.term()
        while (tok := self.peek()) is not None and tok.kind == "op" and tok.value in "+-":
            self.take()
            rhs = self.term()
            value = value + rhs if tok.value == "+" else value - rhs
        return value

    def term(self) -> float:
        value = self.unary()
        while (tok := self.peek()) is not None:
            if tok.kind == "op" and tok.value in "*/":
                self.take()
                rhs = self.unary()
                if tok.value == "*":
                    value *= rhs
                else:
                    if rhs == 0:
                        raise CalcError("division by zero")
                    value /= rhs
            elif tok.kind in ("num", "const", "func", "lp"):
                value *= self.power()  # implicit multiplication: 2π, 3(4), 2sin(30)
            else:
                break
        return value

    def unary(self) -> float:
        tok = self.peek()
        if tok is not None and tok.kind == "op" and tok.value in "+-":
            self.take()
            v = self.unary()
            return -v if tok.value == "-" else v
        return self.power()

    def power(self) -> float:
        base = self.postfix()
        tok = self.peek()
        if tok is not None and tok.kind == "op" and tok.value == "^":
            self.take()
            exponent = self.unary()
            try:
                result = math.pow(base, exponent)
            except OverflowError as exc:
                raise CalcError("overflow") from exc
            except ValueError as exc:
                raise CalcError("domain") from exc
            return result
        return base

    def postfix(self) -> float:
        value = self.primary()
        while (tok := self.peek()) is not None and tok.kind == "post":
            self.take()
            value = _factorial(value) if tok.value == "!" else value / 100.0
        return value

    def primary(self) -> float:
        tok = self.take()
        if tok.kind in ("num", "const"):
            return float(tok.value)
        if tok.kind == "lp":
            value = self.expr()
            self._close()
            return value
        if tok.kind == "func":
            nxt = self.take()
            if nxt.kind != "lp":
                raise CalcError("function needs (")
            arg = self.expr()
            self._close()
            return tok.value(arg, self.deg)
        raise CalcError("unexpected token")

    def _close(self) -> None:
        tok = self.take()
        if tok.kind != "rp":
            raise CalcError("missing )")


def _balance(text: str) -> str:
    """Auto-close any parentheses the user left open."""
    missing = text.count("(") - text.count(")")
    return text + ")" * missing if missing > 0 else text


def evaluate(text: str, degrees: bool = True) -> float:
    """Evaluate *text* and return a finite float, or raise :class:`CalcError`."""
    try:
        value = _Parser(tokenize(_balance(text)), degrees).parse()
    except CalcError:
        raise
    except (ValueError, OverflowError, ZeroDivisionError) as exc:
        raise CalcError(str(exc)) from exc
    if math.isnan(value) or math.isinf(value):
        raise CalcError("undefined")
    return value


def try_preview(text: str, degrees: bool = True) -> str | None:
    """Live result preview — returns ``None`` while the input is incomplete."""
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return format_number(evaluate(stripped, degrees))
    except CalcError:
        return None


def format_number(value: float) -> str:
    """Pretty-print a result with up to 12 significant digits."""
    if value == 0:
        return "0"
    rounded = float(f"{value:.12g}")
    if rounded == 0:
        return "0"
    magnitude = abs(rounded)
    if magnitude >= 1e15 or magnitude < 1e-9:
        mantissa, exp = f"{rounded:.10e}".split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        return f"{mantissa}E{int(exp):+d}"
    text = format(Decimal(repr(rounded)).normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text

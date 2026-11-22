"""UI smoke tests — run headless with Qt's offscreen platform."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtCore import QEvent  # noqa: E402

from purplecalc.ui import CalculatorState, CalculatorWindow, create_app  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return create_app([])


@pytest.fixture
def win(app):
    w = CalculatorWindow()
    w.show()
    yield w
    w.close()


def click(win, *ids):
    for key_id in ids:
        win.buttons[key_id].click()


def test_design_example_by_clicks(win):
    click(win, "sin", "3", "0", ")", "×", "sqrt", "1", "6", ")", "+", "2", "pow", "8")
    assert win.state.text == "sin(30)×√(16)+2^8"
    assert win.result_label.text() == "= 258"
    click(win, "=")
    assert win.state.text == "258"
    assert win.prev_label.text() == "sin(30)×√(16)+2^8 ="
    assert win.state.history[0] == ("sin(30)×√(16)+2^8", "258")


def test_second_mode_is_one_shot(win):
    click(win, "2nd")
    assert win.buttons["sin"].text() == "sin⁻¹"
    click(win, "sin")
    assert win.state.text == "sin⁻¹("
    assert win.buttons["sin"].text() == "sin"
    click(win, "0", ".", "5", "=")
    assert win.state.text == "30"


def test_deg_rad_toggle(win):
    click(win, "deg")
    assert win.badge.text() == "RAD"
    click(win, "cos", "π", "=")
    assert win.state.text == "-1"


def test_error_and_recovery(win):
    click(win, "1", "÷", "0", "=")
    assert win.result_label.text() == "Error"
    click(win, "ac")
    assert win.state.text == "" and win.result_label.text() == ""


def test_keyboard(win):
    for ch in "12+3*2":
        win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, ch))
    win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert win.state.text == "18"


def test_history_page(win):
    click(win, "2", "+", "2", "=")
    win.toggle_history()
    assert win.stack.currentIndex() == 1
    assert win.history_list.count() == 1
    win._history_clicked(win.history_list.item(0))
    assert win.stack.currentIndex() == 0
    assert win.state.text == "4"


def test_state_editing_rules():
    s = CalculatorState()
    for k in ["5", "+", "×"]:
        s.press(k)
    assert s.text == "5×"  # operator replaced
    s.press("ac")
    for k in [".", ".", "5"]:
        s.press(k)
    assert s.text == "0.5"
    s.press("ac")
    for k in ["2", "π"]:
        s.press(k)
    assert s.text == "2×π"
    s.press("=")
    s.press("+")
    s.press("1")
    assert s.text.endswith("+1") and s.just_evaluated is False
    s.press("ac")
    for k in ["−", "4", "inv"]:
        s.press(k)
    assert s.text == "1÷(−4)"
    s.press("=")
    assert s.text == "-0.25"
    s.press("ac")
    s.paste("3,5*2")
    assert s.text == "3.5×2"

"""PySide6 user interface for PurpleCalc."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .engine import CalcError, evaluate, format_number, try_preview

APP_NAME = "PurpleCalc"
FONT_FAMILY = "Inter"
FONTS_LOADED = 0  # number of bundled font files registered at start-up

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
BG = "#0c0a12"
CARD = "#15121e"
FN_BG = "#17141f"
FN_TEXT = "#a78bfa"
NUM_BG = "#231e33"
OP_BG = "#372c5a"
ACCENT = "#8b5cf6"
PINK = "#e879f9"
TEXT = "#f4f2ff"
MUTED = "#8a83a3"
ERROR = "#fb7185"

STYLE = f"""
QMainWindow, QWidget#root {{ background: {BG}; }}
QFrame#display {{ background: {CARD}; border-radius: 20px; }}
QLabel#badge {{
    background: #2a2342; color: #c4b5fd; border-radius: 6px;
    padding: 3px 8px; font-size: 11px; font-weight: 600;
}}
QLabel#expr {{ color: {TEXT}; }}
QLabel#result {{ color: {FN_TEXT}; font-size: 18px; }}
QLabel#result[state="error"] {{ color: {ERROR}; }}
QLabel#prev {{ color: {MUTED}; font-size: 15px; }}

QPushButton {{
    border: none; border-radius: 14px; font-size: 15px; font-weight: 600;
    background: {FN_BG}; color: {FN_TEXT};
}}
QPushButton:hover {{ background: #211c2d; }}
QPushButton:pressed {{ background: #2b2440; }}

QPushButton[kind="num"] {{ background: {NUM_BG}; color: {TEXT}; font-size: 21px; font-weight: 500; }}
QPushButton[kind="num"]:hover {{ background: #2d2742; }}
QPushButton[kind="num"]:pressed {{ background: #3a3354; }}

QPushButton[kind="op"] {{ background: {OP_BG}; color: #ece6ff; font-size: 22px; font-weight: 500; }}
QPushButton[kind="op"]:hover {{ background: #43376d; }}
QPushButton[kind="op"]:pressed {{ background: #50427f; }}

QPushButton[kind="danger"] {{ background: #352953; color: {PINK}; font-size: 17px; }}
QPushButton[kind="danger"]:hover {{ background: #403163; }}
QPushButton[kind="danger"]:pressed {{ background: #4b3a73; }}

QPushButton[kind="equal"] {{ background: {ACCENT}; color: white; font-size: 24px; }}
QPushButton[kind="equal"]:hover {{ background: #9b74f8; }}
QPushButton[kind="equal"]:pressed {{ background: #7c4ae6; }}

QPushButton[active="true"] {{ background: {ACCENT}; color: white; }}
QPushButton[active="true"]:hover {{ background: #9b74f8; }}

QPushButton#iconBtn {{ background: transparent; border-radius: 8px; padding: 4px; }}
QPushButton#iconBtn:hover {{ background: #241f33; }}

QWidget#historyPage {{ background: transparent; }}
QLabel#historyTitle {{ color: {TEXT}; font-size: 16px; font-weight: 600; }}
QPushButton#textBtn {{
    background: transparent; color: {FN_TEXT}; font-size: 13px;
    padding: 6px 10px; border-radius: 8px;
}}
QPushButton#textBtn:hover {{ background: #241f33; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border-radius: 12px; margin: 3px 0; }}
QListWidget::item:hover {{ background: #1b1726; }}
QListWidget::item:selected {{ background: #241f33; }}
QLabel#histExpr {{ color: {MUTED}; font-size: 13px; }}
QLabel#histResult {{ color: {TEXT}; font-size: 20px; font-weight: 600; }}
QLabel#empty {{ color: {MUTED}; font-size: 14px; }}
QScrollBar:vertical {{ background: transparent; width: 6px; }}
QScrollBar::handle:vertical {{ background: #2e2742; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


# --------------------------------------------------------------------------- #
# Key definitions
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Key:
    id: str
    label: str
    kind: str = "fn"
    alt_id: str | None = None  # action when "2nd" is active
    alt_label: str | None = None


LAYOUT: list[list[Key]] = [
    [
        Key("2nd", "2nd"),
        Key("deg", "DEG"),
        Key("sin", "sin", alt_id="asin", alt_label="sin⁻¹"),
        Key("cos", "cos", alt_id="acos", alt_label="cos⁻¹"),
        Key("tan", "tan", alt_id="atan", alt_label="tan⁻¹"),
    ],
    [
        Key("pow", "xʸ", alt_id="sq", alt_label="x²"),
        Key("log", "log", alt_id="exp10", alt_label="10ˣ"),
        Key("ln", "ln", alt_id="expe", alt_label="eˣ"),
        Key("(", "("),
        Key(")", ")"),
    ],
    [
        Key("sqrt", "√", alt_id="cbrt", alt_label="∛"),
        Key("ac", "AC", "danger"),
        Key("back", "⌫", "danger"),
        Key("%", "%"),
        Key("÷", "÷", "op"),
    ],
    [Key("!", "x!"), Key("7", "7", "num"), Key("8", "8", "num"), Key("9", "9", "num"), Key("×", "×", "op")],
    [Key("inv", "1/x"), Key("4", "4", "num"), Key("5", "5", "num"), Key("6", "6", "num"), Key("−", "−", "op")],
    [Key("π", "π"), Key("1", "1", "num"), Key("2", "2", "num"), Key("3", "3", "num"), Key("+", "+", "op")],
    [Key("abs", "|x|"), Key("e", "e"), Key("0", "0", "num"), Key(".", ".", "num"), Key("=", "=", "equal")],
]

FUNC_TOKENS = {
    "sin": "sin(",
    "cos": "cos(",
    "tan": "tan(",
    "asin": "sin⁻¹(",
    "acos": "cos⁻¹(",
    "atan": "tan⁻¹(",
    "log": "log(",
    "ln": "ln(",
    "sqrt": "√(",
    "cbrt": "∛(",
    "abs": "abs(",
    "exp10": "10^(",
    "expe": "e^(",
}
BINARY_OPS = {"+", "−", "×", "÷", "^"}

# Keyboard → key id
TEXT_KEYS = {
    **{d: d for d in "0123456789"},
    ".": ".", ",": ".",
    "+": "+", "-": "−", "*": "×", "x": "×", "/": "÷", ":": "÷",
    "^": "pow", "(": "(", ")": ")", "!": "!", "%": "%", "=": "=",
    "p": "π", "e": "e", "s": "sin", "c": "cos", "t": "tan",
    "l": "log", "n": "ln", "r": "sqrt", "a": "abs", "i": "inv", "d": "deg",
}


# --------------------------------------------------------------------------- #
# Calculator state (UI independent, easy to test)
# --------------------------------------------------------------------------- #
class CalculatorState:
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.degrees = True
        self.second = False
        self.just_evaluated = False
        self.last_expression = ""  # shown above the result after "="
        self.error = False
        self.history: list[tuple[str, str]] = []

    # ---- helpers ---------------------------------------------------------
    @property
    def text(self) -> str:
        return "".join(self.tokens)

    def _last(self) -> str:
        return self.tokens[-1] if self.tokens else ""

    def _ends_with_value(self) -> bool:
        last = self._last()
        if not last:
            return False
        ch = last[-1]
        return ch.isdigit() or ch in ").πe!%" or (ch == "E")

    def _ends_with_number(self) -> bool:
        return bool(self.tokens) and (self._last()[-1].isdigit() or self._last()[-1] == ".")

    def _current_number(self) -> str:
        text = self.text
        i = len(text)
        while i > 0 and (text[i - 1].isdigit() or text[i - 1] == "."):
            i -= 1
        return text[i:]

    def _start_fresh_if_needed(self, keep_result: bool) -> None:
        """After '=' a new number starts over, an operator continues with the result."""
        if self.just_evaluated:
            if not keep_result:
                self.tokens = []
                self.last_expression = ""
            self.just_evaluated = False
        if self.error:
            self.error = False

    # ---- public API ------------------------------------------------------
    def press(self, key_id: str) -> None:
        if key_id == "2nd":
            self.second = not self.second
        elif key_id == "deg":
            self.degrees = not self.degrees
        elif key_id == "ac":
            self.tokens, self.just_evaluated, self.error, self.last_expression = [], False, False, ""
        elif key_id == "back":
            self._backspace()
        elif key_id == "=":
            self._equals()
        elif key_id.isdigit():
            self._start_fresh_if_needed(keep_result=False)
            if self._last() in (")", "π", "e", "!", "%"):
                self.tokens.append("×")
            self.tokens.append(key_id)
        elif key_id == ".":
            self._start_fresh_if_needed(keep_result=False)
            if "." in self._current_number():
                return
            if not self._ends_with_number():
                self.tokens.append("0")
            self.tokens.append(".")
        elif key_id in BINARY_OPS or key_id == "pow":
            self._binary("^" if key_id == "pow" else key_id)
        elif key_id == "sq":
            self._start_fresh_if_needed(keep_result=True)
            if self._ends_with_value():
                self.tokens += ["^", "2"]
        elif key_id in ("!", "%"):
            self._start_fresh_if_needed(keep_result=True)
            if self._ends_with_value():
                self.tokens.append(key_id)
        elif key_id in ("π", "e"):
            self._start_fresh_if_needed(keep_result=False)
            if self._ends_with_value():
                self.tokens.append("×")
            self.tokens.append(key_id)
        elif key_id in FUNC_TOKENS:
            self._start_fresh_if_needed(keep_result=False)
            if self._ends_with_value():
                self.tokens.append("×")
            self.tokens.append(FUNC_TOKENS[key_id])
        elif key_id == "(":
            self._start_fresh_if_needed(keep_result=False)
            if self._ends_with_value():
                self.tokens.append("×")
            self.tokens.append("(")
        elif key_id == ")":
            self._start_fresh_if_needed(keep_result=True)
            if self.text.count("(") > self.text.count(")") and self._ends_with_value():
                self.tokens.append(")")
        elif key_id == "inv":
            self._start_fresh_if_needed(keep_result=True)
            if self.tokens:
                self.tokens = ["1÷(", *self.tokens, ")"]
            else:
                self.tokens = ["1÷"]

    def _binary(self, op: str) -> None:
        self._start_fresh_if_needed(keep_result=True)
        last = self._last()
        if not self.tokens or last.endswith("("):
            if op == "−":
                self.tokens.append("−")
            elif not self.tokens:
                self.tokens += ["0", op]
            return
        if last in BINARY_OPS:
            if len(self.tokens) == 1 or self.tokens[-2].endswith("("):
                return  # a leading minus stays a sign
            self.tokens[-1] = op
            return
        if last.endswith("."):
            self.tokens.append("0")
        self.tokens.append(op)

    def _backspace(self) -> None:
        if self.just_evaluated:
            self.tokens, self.just_evaluated, self.last_expression = [], False, ""
            return
        self.error = False
        if self.tokens:
            self.tokens.pop()

    def _equals(self) -> None:
        expr = self.text
        if not expr or self.just_evaluated:
            return
        try:
            result = format_number(evaluate(expr, self.degrees))
        except CalcError:
            self.error = True
            return
        missing = expr.count("(") - expr.count(")")
        shown = expr + ")" * max(missing, 0)
        self.history.insert(0, (shown, result))
        del self.history[100:]
        self.last_expression = shown
        self.tokens = [result]
        self.just_evaluated = True
        self.error = False

    def preview(self) -> str | None:
        if self.just_evaluated or not self.tokens:
            return None
        return try_preview(self.text, self.degrees)

    def load(self, expression: str, result: str) -> None:
        self.tokens = [result]
        self.last_expression = expression
        self.just_evaluated = True
        self.error = False

    def paste(self, text: str) -> None:
        cleaned = "".join(ch for ch in text.strip() if ch.isdigit() or ch in ".,+-−×÷*/^()!%πeE")
        if not cleaned:
            return
        self._start_fresh_if_needed(keep_result=False)
        cleaned = (
            cleaned.replace(",", ".").replace("*", "×").replace("/", "÷").replace("-", "−")
        )
        self.tokens.extend(cleaned)


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #
def ui_font(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(FONT_FAMILY)
    font.setPointSizeF(size)
    font.setWeight(weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


class FitLabel(QLabel):
    """Right-aligned label that shrinks its font to fit, then elides on the left."""

    def __init__(self, max_px: int = 34, min_px: int = 17) -> None:
        super().__init__()
        self.max_px, self.min_px = max_px, min_px
        self._full = ""
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(max_px + 16)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._refit()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refit()

    def _refit(self) -> None:
        width = max(self.width() - 4, 10)
        font = self.font()
        font.setFamily(FONT_FAMILY)
        font.setWeight(QFont.Weight.DemiBold)
        size = self.max_px
        while size > self.min_px:
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(self._full) <= width:
                break
            size -= 1
        font.setPixelSize(size)
        self.setFont(font)
        shown = QFontMetrics(font).elidedText(self._full, Qt.TextElideMode.ElideLeft, width)
        super().setText(shown)


def history_icon(color: str = FN_TEXT, size: int = 20) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    r = QRectF(7, 7, size * 2 - 14, size * 2 - 14)
    p.drawEllipse(r)  # clock face
    c = r.center()
    p.drawLine(c, QPointF(c.x(), c.y() - 9))
    p.drawLine(c, QPointF(c.x() + 7, c.y() + 4))
    p.end()
    return QIcon(pm)


def app_icon_pixmap(size: int = 256) -> QPixmap:
    """The PurpleCalc logo: a purple rounded square with a calculator glyph."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor("#a78bfa"))
    grad.setColorAt(1, QColor("#6d28d9"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 56 * s, 56 * s)
    p.fillPath(path, grad)
    # screen
    screen = QPainterPath()
    screen.addRoundedRect(QRectF(52 * s, 46 * s, 152 * s, 52 * s), 14 * s, 14 * s)
    p.fillPath(screen, QColor(18, 14, 30, 220))
    p.setPen(QPen(QColor("#c4b5fd"), 9 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(150 * s, 66 * s), QPointF(184 * s, 66 * s))
    p.drawLine(QPointF(150 * s, 80 * s), QPointF(184 * s, 80 * s))
    # keys
    for row in range(2):
        for col in range(3):
            key = QPainterPath()
            x = 52 * s + col * 54 * s
            y = 116 * s + row * 50 * s
            key.addRoundedRect(QRectF(x, y, 44 * s, 40 * s), 11 * s, 11 * s)
            last = row == 1 and col == 2
            p.fillPath(key, QColor("#ffffff") if last else QColor(255, 255, 255, 70))
    p.end()
    return pm


class HistoryRow(QWidget):
    def __init__(self, expr: str, result: str) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        e = QLabel(expr + " =")
        e.setObjectName("histExpr")
        e.setAlignment(Qt.AlignmentFlag.AlignRight)
        r = QLabel(result)
        r.setObjectName("histResult")
        r.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(e)
        lay.addWidget(r)


class CalculatorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = CalculatorState()
        self.buttons: dict[str, QPushButton] = {}
        self.keys: dict[str, Key] = {}

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(app_icon_pixmap()))
        self.resize(392, 720)
        self.setMinimumSize(330, 580)

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(14)

        outer.addWidget(self._build_display())
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_keypad())
        self.stack.addWidget(self._build_history())
        outer.addWidget(self.stack, 1)

        self._build_shortcuts()
        self.refresh()

    # ---- construction ----------------------------------------------------
    def _build_display(self) -> QFrame:
        card = QFrame(objectName="display")
        card.setMinimumHeight(150)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(2)

        top = QHBoxLayout()
        self.badge = QLabel("DEG", objectName="badge")
        self.badge.setFont(ui_font(8.5, QFont.Weight.DemiBold))
        top.addWidget(self.badge)
        top.addStretch(1)
        self.history_btn = QPushButton(objectName="iconBtn")
        self.history_btn.setIcon(history_icon())
        self.history_btn.setIconSize(QSize(18, 18))
        self.history_btn.setToolTip("History (Ctrl+H)")
        self.history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.history_btn.clicked.connect(self.toggle_history)
        top.addWidget(self.history_btn)
        lay.addLayout(top)
        lay.addStretch(1)

        self.prev_label = QLabel(objectName="prev")
        self.prev_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.prev_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.prev_label)

        self.expr_label = FitLabel()
        self.expr_label.setObjectName("expr")
        lay.addWidget(self.expr_label)

        self.result_label = QLabel(objectName="result")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.result_label.setMinimumHeight(26)
        lay.addWidget(self.result_label)
        return card

    def _build_keypad(self) -> QWidget:
        pad = QWidget()
        grid = QGridLayout(pad)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for r, row in enumerate(LAYOUT):
            for c, key in enumerate(row):
                btn = QPushButton(key.label)
                btn.setProperty("kind", key.kind)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                btn.setMinimumSize(52, 50)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _=False, k=key: self.on_key(k))
                grid.addWidget(btn, r, c)
                self.buttons[key.id] = btn
                self.keys[key.id] = key
        return pad

    def _build_history(self) -> QWidget:
        page = QWidget(objectName="historyPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 0, 4, 0)
        head = QHBoxLayout()
        title = QLabel("History", objectName="historyTitle")
        head.addWidget(title)
        head.addStretch(1)
        clear = QPushButton("Clear", objectName="textBtn")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self.clear_history)
        back = QPushButton("Back", objectName="textBtn")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self.toggle_history)
        head.addWidget(clear)
        head.addWidget(back)
        lay.addLayout(head)

        self.history_list = QListWidget()
        self.history_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_list.itemClicked.connect(self._history_clicked)
        lay.addWidget(self.history_list, 1)

        self.empty_label = QLabel("No calculations yet", objectName="empty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty_label, 1)
        return page

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Copy, self, activated=self.copy_result)
        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self.paste)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self.toggle_history)

    # ---- behaviour -------------------------------------------------------
    def on_key(self, key: Key) -> None:
        action = key.alt_id if (self.state.second and key.alt_id) else key.id
        was_second = self.state.second
        self.state.press(action)
        if was_second and key.alt_id and action == key.alt_id:
            self.state.second = False  # one-shot like a real scientific calculator
        self.refresh()

    def press_id(self, key_id: str) -> None:
        key = self.keys.get(key_id)
        if key is None:
            return
        self._flash(self.buttons[key_id])
        self.on_key(key)

    def _flash(self, btn: QPushButton) -> None:
        btn.setDown(True)
        QTimer.singleShot(90, lambda: btn.setDown(False))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            return super().keyPressEvent(event)
        if self.stack.currentIndex() == 1 and key == Qt.Key.Key_Escape:
            self.toggle_history()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.press_id("=")
        elif key == Qt.Key.Key_Backspace:
            self.press_id("back")
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_Delete):
            self.press_id("ac")
        elif key == Qt.Key.Key_F2:
            self.press_id("2nd")
        elif (text := event.text()) in TEXT_KEYS:
            self.press_id(TEXT_KEYS[text])
        else:
            super().keyPressEvent(event)

    def copy_result(self) -> None:
        st = self.state
        value = st.text if st.just_evaluated else (st.preview() or st.text)
        if value:
            QGuiApplication.clipboard().setText(value.replace("−", "-"))

    def paste(self) -> None:
        self.state.paste(QGuiApplication.clipboard().text())
        self.refresh()

    def toggle_history(self) -> None:
        showing = self.stack.currentIndex() == 1
        if not showing:
            self._fill_history()
        self.stack.setCurrentIndex(0 if showing else 1)

    def clear_history(self) -> None:
        self.state.history.clear()
        self._fill_history()

    def _fill_history(self) -> None:
        self.history_list.clear()
        for expr, result in self.state.history:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, (expr, result))
            row = HistoryRow(expr, result)
            item.setSizeHint(row.sizeHint())
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, row)
        has = bool(self.state.history)
        self.history_list.setVisible(has)
        self.empty_label.setVisible(not has)

    def _history_clicked(self, item: QListWidgetItem) -> None:
        expr, result = item.data(Qt.ItemDataRole.UserRole)
        self.state.load(expr, result)
        self.stack.setCurrentIndex(0)
        self.refresh()

    # ---- rendering -------------------------------------------------------
    def refresh(self) -> None:
        st = self.state
        self.badge.setText("DEG" if st.degrees else "RAD")
        self.buttons["deg"].setText("RAD" if not st.degrees else "DEG")

        second = self.buttons["2nd"]
        second.setProperty("active", "true" if st.second else "false")
        second.style().unpolish(second)
        second.style().polish(second)
        for key_id, key in self.keys.items():
            if key.alt_label:
                self.buttons[key_id].setText(key.alt_label if st.second else key.label)

        self.prev_label.setText(f"{st.last_expression} =" if st.just_evaluated else "")
        self.prev_label.setVisible(st.just_evaluated)
        self.expr_label.set_full_text(st.text or "0")

        self.result_label.setProperty("state", "error" if st.error else "ok")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)
        if st.error:
            self.result_label.setText("Error")
        else:
            preview = st.preview()
            self.result_label.setText(f"= {preview}" if preview is not None else "")


# --------------------------------------------------------------------------- #
# Platform niceties
# --------------------------------------------------------------------------- #
def _load_fonts() -> None:
    global FONT_FAMILY, FONTS_LOADED
    font_dir = Path(__file__).resolve().parent / "fonts"
    for f in sorted(font_dir.glob("*.otf")):
        if QFontDatabase.addApplicationFont(str(f)) != -1:
            FONTS_LOADED += 1
    if not FONTS_LOADED and sys.platform == "win32":
        FONT_FAMILY = "Segoe UI"


def _windows_dark_titlebar(window: QWidget) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(window.winId()))
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old builds)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break
        colour = QColor(BG)
        colorref = ctypes.c_int(colour.red() | (colour.green() << 8) | (colour.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), ctypes.sizeof(colorref))  # Win11 caption
    except Exception:  # pragma: no cover - purely cosmetic
        pass


def _windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"muba14.PurpleCalc.{__version__}")
    except Exception:  # pragma: no cover
        pass


def create_app(argv: list[str] | None = None) -> QApplication:
    _windows_app_id()
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    _load_fonts()
    app.setFont(ui_font(10.5))
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(app_icon_pixmap()))
    return app


def smoke_test() -> int:
    """Used by CI on the frozen .exe: build the window, do one calculation, exit."""
    create_app([sys.argv[0]])
    window = CalculatorWindow()
    window.show()
    for key_id in ["sin", "3", "0", ")", "×", "sqrt", "1", "6", ")", "+", "2", "pow", "8", "="]:
        window.buttons[key_id].click()
    ok_calc = window.state.text == "258"
    bundled = list((Path(__file__).resolve().parent / "fonts").glob("Inter-*.otf"))
    ok_font = len(bundled) == 3
    print(f"PurpleCalc {__version__} smoke test: calc={'ok' if ok_calc else 'FAIL'} font={'ok' if ok_font else 'FAIL'}")
    window.close()
    return 0 if (ok_calc and ok_font) else 1


def run() -> int:
    if "--smoke-test" in sys.argv:
        return smoke_test()
    app = create_app()
    window = CalculatorWindow()
    window.show()
    _windows_dark_titlebar(window)
    return app.exec()

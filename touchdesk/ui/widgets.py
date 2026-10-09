"""Reusable touchscreen widgets."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from touchdesk.desks.faderlaw import float_to_db, format_db


def repolish(w: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property change."""
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def set_prop(w: QWidget, name: str, value) -> None:
    if w.property(name) != value:
        w.setProperty(name, value)
        repolish(w)


# ---------------------------------------------------------------- icons
def paint_icon(p: QPainter, kind: str, r: QRectF, color: QColor) -> None:
    """Simple vector icons, so nothing depends on fonts or image files."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()

    def pt(fx, fy):
        return QPointF(x + fx * w, y + fy * h)

    if kind == "bluetooth":
        pen = QPen(color, max(1.5, w * 0.09))
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(pt(0.28, 0.30))
        for fx, fy in ((0.72, 0.70), (0.50, 0.90), (0.50, 0.10), (0.72, 0.30), (0.28, 0.70)):
            path.lineTo(pt(fx, fy))
        p.drawPath(path)
        return

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)

    def tri(x0, flip=False):
        path = QPainterPath()
        if flip:
            path.moveTo(pt(x0 + 0.3, 0.2))
            path.lineTo(pt(x0, 0.5))
            path.lineTo(pt(x0 + 0.3, 0.8))
        else:
            path.moveTo(pt(x0, 0.2))
            path.lineTo(pt(x0 + 0.3, 0.5))
            path.lineTo(pt(x0, 0.8))
        path.closeSubpath()
        p.drawPath(path)

    if kind == "play":
        path = QPainterPath(pt(0.32, 0.2))
        path.lineTo(pt(0.78, 0.5))
        path.lineTo(pt(0.32, 0.8))
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "pause":
        p.drawRect(QRectF(pt(0.28, 0.22), pt(0.43, 0.78)))
        p.drawRect(QRectF(pt(0.57, 0.22), pt(0.72, 0.78)))
    elif kind == "next":
        tri(0.2)
        tri(0.45)
        p.drawRect(QRectF(pt(0.75, 0.2), pt(0.82, 0.8)))
    elif kind == "prev":
        p.drawRect(QRectF(pt(0.18, 0.2), pt(0.25, 0.8)))
        tri(0.25, flip=True)
        tri(0.5, flip=True)


class IconButton(QPushButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setObjectName("BtButton")

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        color = QColor("#ffffff" if self.isEnabled() else "#555555")
        m = self.width() * 0.25
        paint_icon(p, self.kind, QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m), color)


class IconLabel(QWidget):
    """A label that shows either text or a small vector icon."""

    def __init__(self, text: str = "", icon: str = "", parent=None):
        super().__init__(parent)
        self._text, self._icon = text, icon
        self.dim = False
        self.setObjectName("StripName")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setText(self, text: str) -> None:
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def sizeHint(self):
        from PySide6.QtCore import QSize

        return QSize(60, self.fontMetrics().height() + 12)

    def paintEvent(self, e):
        p = QPainter(self)
        color = QColor("#bbbbbb" if self.dim else "#ffffff")
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self._icon:
            side = min(r.width(), r.height())
            paint_icon(p, self._icon, QRectF(r.center().x() - side / 2, r.y(), side, side), color)
            return
        p.setPen(color)
        f = self.font()
        f.setBold(True)
        p.setFont(f)
        text = p.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, int(r.width()))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)


# ---------------------------------------------------------------- channel strip
class ChannelStrip(QWidget):
    """Name, fader, level readout and ON/OFF button for one channel."""

    moved = Signal(int, float)  # index, position 0..1
    toggled = Signal(int, bool)  # index, new "on" state
    touched = Signal()

    STEPS = 1000

    def __init__(self, index: int, label: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.index = index
        self.label = label
        self.level_display = "0-10"
        self._on: bool | None = None
        self.setObjectName("Strip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.name = IconLabel(label, icon)
        self.fader = QSlider(Qt.Orientation.Vertical)
        self.fader.setObjectName("Fader")
        self.fader.setRange(0, self.STEPS)
        self.fader.setPageStep(0)  # tapping the groove must not jump the level
        self.fader.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.readout = QLabel("–")
        self.readout.setObjectName("Readout")
        self.readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mute = QPushButton("–")
        self.mute.setObjectName("Mute")
        self.mute.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.name)
        fader_box = QHBoxLayout()
        fader_box.setContentsMargins(0, 10, 0, 10)
        fader_box.addWidget(self.fader, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addLayout(fader_box, 1)
        lay.addWidget(self.readout)
        lay.addWidget(self.mute)

        self.fader.valueChanged.connect(self._fader_moved)
        self.fader.sliderPressed.connect(self.touched)
        self.mute.clicked.connect(self._mute_clicked)
        self.mute.pressed.connect(self.touched)

    # The session tells us the desk's state; don't echo it back as a move.
    def show_state(self, position: float, level: float | None, on: bool | None, name: str) -> None:
        if not self.fader.isSliderDown():
            self.fader.blockSignals(True)
            self.fader.setValue(round(position * self.STEPS))
            self.fader.blockSignals(False)
        self._update_readout(level)
        self._on = on
        live = on is not False
        self.mute.setText("–" if on is None else ("ON" if on else "OFF"))
        for w in (self, self.mute):
            set_prop(w, "live", live)
        self._update_fader_mode()
        self.name.dim = not live
        self.name.setText(name or self.label)

    def _update_fader_mode(self) -> None:
        # Qt ignores :disabled on slider parts reliably, so use a property.
        mode = "offline" if not self.isEnabled() else ("off" if self._on is False else "on")
        set_prop(self.fader, "mode", mode)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.EnabledChange:
            self._update_fader_mode()

    def _update_readout(self, level: float | None) -> None:
        if level is None:
            self.readout.setText("–")
        elif self.level_display == "db":
            self.readout.setText(format_db(float_to_db(level)))
        else:
            self.readout.setText(str(round(self.fader.value() / self.STEPS * 10)))

    def _fader_moved(self, value: int) -> None:
        self.moved.emit(self.index, value / self.STEPS)
        self.touched.emit()

    def _mute_clicked(self) -> None:
        self.toggled.emit(self.index, not bool(self._on))


# ---------------------------------------------------------------- PIN pad
class PinPad(QWidget):
    """Masked PIN entry with a 0-9 keypad."""

    submitted = Signal(str)
    touched = Signal()

    def __init__(self, prompt: str = "Enter PIN", max_len: int = 8, parent=None):
        super().__init__(parent)
        self.max_len = max_len
        self.digits = ""

        self.prompt = QLabel(prompt)
        self.prompt.setObjectName("PinPrompt")
        self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dots = QLabel("")
        self.dots.setObjectName("PinDots")
        self.dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message = QLabel("")
        self.message.setObjectName("PinMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.keys: list[QPushButton] = []
        for n in range(1, 10):
            grid.addWidget(self._key(str(n), lambda _=False, n=n: self._add(str(n))), (n - 1) // 3, (n - 1) % 3)
        grid.addWidget(self._key("Del", self._delete, small=True), 3, 0)
        grid.addWidget(self._key("0", lambda: self._add("0")), 3, 1)
        grid.addWidget(self._key("Ent", self._submit, small=True), 3, 2)

        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addStretch(1)
        left.addWidget(self.prompt)
        left.addSpacing(8)
        left.addWidget(self.dots, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addSpacing(6)
        left.addWidget(self.message)
        left.addStretch(1)
        lay.addStretch(1)
        lay.addLayout(left)
        lay.addSpacing(40)
        lay.addLayout(grid)
        lay.addStretch(1)

    def _key(self, text, fn, small=False) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("Key")
        if small:
            b.setProperty("small", True)
        b.clicked.connect(fn)
        b.pressed.connect(self.touched)
        self.keys.append(b)
        return b

    def _add(self, d: str) -> None:
        if len(self.digits) < self.max_len:
            self.digits += d
            self.message.setText("")
            self._show()

    def _delete(self) -> None:
        self.digits = self.digits[:-1]
        self._show()

    def _submit(self) -> None:
        if self.digits:
            pin, self.digits = self.digits, ""
            self._show()
            self.submitted.emit(pin)

    def _show(self) -> None:
        self.dots.setText("● " * len(self.digits))

    def clear(self, message: str = "") -> None:
        self.digits = ""
        self._show()
        self.message.setText(message)

    def set_locked(self, locked: bool) -> None:
        for k in self.keys:
            k.setEnabled(not locked)


class LongPressArea(QWidget):
    """Emits long_pressed after the area is held for `ms` milliseconds."""

    long_pressed = Signal()

    def __init__(self, ms: int = 3000, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self, singleShot=True, interval=ms)
        self._timer.timeout.connect(self.long_pressed)

    def mousePressEvent(self, e):
        self._timer.start()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._timer.stop()
        super().mouseReleaseEvent(e)

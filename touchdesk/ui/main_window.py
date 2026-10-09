"""The main window: top bar plus the current screen."""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from touchdesk.bluetooth import BluetoothBackend
from touchdesk.config import Config
from touchdesk.session import DeskSession
from touchdesk.ui import theme
from touchdesk.ui.screens import AdminScreen, BluetoothPanel, LockScreen, MixerScreen
from touchdesk.ui.widgets import LongPressArea

log = logging.getLogger(__name__)


class ActivityWatcher(QObject):
    """Sees every touch/click anywhere in the app (for the auto-lock timer)."""

    activity = Signal()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin, QEvent.Type.KeyPress):
            self.activity.emit()
        return False


class MainWindow(QWidget):
    LOCK, MIXER, ADMIN = range(3)

    def __init__(self, config: Config, session: DeskSession, bt: BluetoothBackend | None, scale: float = 1.0):
        super().__init__()
        self.config = config
        self.session = session
        self.setObjectName("Root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("TouchDesk")
        self.setStyleSheet(theme.stylesheet(scale))

        # --- screens
        self.lock = LockScreen(config)
        self.mixer = MixerScreen(config, session, BluetoothPanel(bt) if bt is not None else None)
        self.admin = AdminScreen(config, session)
        self.stack = QStackedWidget()
        self.stack.setObjectName("Main")
        for w in (self.lock, self.mixer, self.admin):
            self.stack.addWidget(w)

        # --- top bar
        bar = LongPressArea(3000)
        bar.setObjectName("TopBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.long_pressed.connect(self._admin_requested)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        title = QLabel(config.data.get("display", {}).get("title") or "TouchDesk")
        title.setObjectName("Title")
        bl.addWidget(title)
        bl.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("Status")
        bl.addWidget(self.status)
        self.b_muteall = QPushButton("Mute All")
        self.b_lock = QPushButton("Lock")
        bl.addWidget(self.b_muteall)
        bl.addWidget(self.b_lock)
        self.b_muteall.clicked.connect(session.mute_all)
        self.b_lock.clicked.connect(self.lock_now)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(bar)
        body = QVBoxLayout()
        body.setContentsMargins(round(7 * scale), round(7 * scale), round(7 * scale), round(7 * scale))
        body.addWidget(self.stack)
        lay.addLayout(body, 1)

        # --- wiring
        self.lock.unlocked.connect(lambda: self.show_page(self.MIXER))
        self.lock.admin.connect(lambda: self.show_page(self.ADMIN))
        self.lock.back.clicked.connect(lambda: self.show_page(self.MIXER))
        self.admin.closed.connect(self._admin_closed)
        self.admin.settings_changed.connect(self._settings_changed)
        self.admin.exit_requested.connect(QApplication.instance().quit)
        session.connection_changed.connect(self._update_status)
        session.info_changed.connect(lambda _: self._update_status())

        self.idle = QTimer(self, singleShot=True)
        self.idle.timeout.connect(self._idle_timeout)
        self.watcher = ActivityWatcher(self)
        self.watcher.activity.connect(self._restart_idle)
        QApplication.instance().installEventFilter(self.watcher)

        self._settings_changed()
        self.show_page(self.LOCK if config.security["pin_enabled"] else self.MIXER)
        self._update_status()

    # ------------------------------------------------------------ navigation
    def show_page(self, page: int) -> None:
        self.stack.setCurrentIndex(page)
        # Reached by long-press with the PIN lock off: offer a way back.
        self.lock.back.setVisible(page == self.LOCK and not self.config.security["pin_enabled"])
        # Mute All stays usable even when locked: anyone can silence feedback.
        self.b_lock.setVisible(bool(self.config.security["pin_enabled"]) and page != self.LOCK)
        if page == self.LOCK:
            self.lock.reset()
        if page == self.ADMIN:
            self.admin.pages.setCurrentIndex(0)
            self.admin.refresh()
        self._restart_idle()

    def lock_now(self) -> None:
        if self.config.security["pin_enabled"]:
            self.show_page(self.LOCK)

    def _admin_requested(self) -> None:
        """Long-press on the top bar opens the installer PIN prompt."""
        if self.stack.currentIndex() != self.ADMIN:
            self.lock.pad.prompt.setText("Enter PIN")
            self.show_page(self.LOCK)

    def _admin_closed(self) -> None:
        self.show_page(self.MIXER if not self.config.security["pin_enabled"] else self.LOCK)

    def _settings_changed(self) -> None:
        self.mixer.apply_settings()
        if not self.config.security["pin_enabled"] and self.stack.currentIndex() == self.LOCK:
            self.show_page(self.MIXER)
        self.b_lock.setVisible(bool(self.config.security["pin_enabled"]) and self.stack.currentIndex() != self.LOCK)
        self._restart_idle()

    # ------------------------------------------------------------ auto-lock
    def _restart_idle(self) -> None:
        mins = int(self.config.security["lock_after_minutes"])
        if self.config.security["pin_enabled"] and mins > 0:
            self.idle.start(mins * 60_000)
        else:
            self.idle.stop()

    def _idle_timeout(self) -> None:
        if self.stack.currentIndex() != self.LOCK:
            log.info("No activity - locking")
            self.show_page(self.LOCK)

    # ------------------------------------------------------------ status
    def _update_status(self, *_):
        s = self.session
        if s.online:
            text, colour = "● Desk connected", theme.OK
        elif s.host is None:
            text, colour = "● Searching for desk", theme.WARN
        else:
            text, colour = "● Desk offline", theme.BAD
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {colour};")

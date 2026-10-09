"""Start-up: read settings, connect to the desk, show the window."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path

from touchdesk import __version__

log = logging.getLogger("touchdesk")

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "touchdesk"


def setup_logging(verbose: bool) -> Path | None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path = STATE_DIR / "touchdesk.log"
        fh = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3)
        fh.setFormatter(fmt)
        root.addHandler(fh)
        return path
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="touchdesk", description="Simple touchscreen remote for OSC sound desks.")
    ap.add_argument("--config", help="settings file (default: ~/.config/touchdesk/config.json)")
    ap.add_argument("--windowed", action="store_true", help="run in an 800x480 window instead of full screen")
    ap.add_argument("--ip", help="desk IP address, overriding the settings file")
    ap.add_argument("--verbose", action="store_true", help="log every detail")
    ap.add_argument("--version", action="version", version=f"TouchDesk {__version__}")
    args = ap.parse_args(argv)

    logfile = setup_logging(args.verbose)
    log.info("TouchDesk %s starting (log: %s)", __version__, logfile)

    # Log crashes inside Qt callbacks instead of losing them.
    def excepthook(exc_type, exc, tb):
        log.critical("Unexpected error", exc_info=(exc_type, exc, tb))

    sys.excepthook = excepthook

    from touchdesk import config as cfgmod

    try:
        config = cfgmod.load(args.config)
    except cfgmod.ConfigError as e:
        log.error("%s", e)
        print(f"\nTouchDesk can't start:\n{e}\n", file=sys.stderr)
        return 2
    if args.ip:
        config.data["desk"]["ip"] = args.ip

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QCursor, QGuiApplication
    from PySide6.QtWidgets import QApplication

    from touchdesk.bluetooth import create_backend
    from touchdesk.session import DeskSession
    from touchdesk.ui.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("TouchDesk")
    # Let Ctrl+C in a terminal close the app.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    keepalive = QTimer()
    keepalive.start(250)  # lets Python see the signals while Qt is running
    keepalive.timeout.connect(lambda: None)

    display = config.data["display"]
    fullscreen = display.get("fullscreen", True) and not args.windowed
    screen = QGuiApplication.primaryScreen().size() if fullscreen else None
    scale = min(screen.width() / 800, screen.height() / 480) if screen else 1.0

    session = DeskSession(config)
    bt = create_backend(bool(config.data["bluetooth"]["enabled"]))
    window = MainWindow(config, session, bt, scale)
    if display.get("hide_cursor", True) and fullscreen:
        app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))
    if fullscreen:
        window.showFullScreen()
    else:
        window.resize(800, 480)
        window.show()

    session.start()
    if bt:
        bt.start()
    code = app.exec()
    session.stop()
    log.info("TouchDesk stopped")
    return code

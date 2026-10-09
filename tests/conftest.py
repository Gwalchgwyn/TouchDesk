import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fake_desk import FakeDesk  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def wait_until(cond, timeout=3.0):
    """Run the Qt event loop until cond() is true (or time runs out)."""
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def pump(seconds):
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


@pytest.fixture
def desk():
    d = FakeDesk(port=0, host="127.0.0.1").start()
    yield d
    d.stop()


_status = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _status["code"] = int(exitstatus)


def pytest_unconfigure(config):
    # Same reason as touchdesk/__main__.py: avoid a PySide6 crash during
    # interpreter clean-up on some Python versions (seen on 3.11).
    import sys

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_status["code"])

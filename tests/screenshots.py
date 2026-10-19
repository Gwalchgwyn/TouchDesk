"""Render every screen to PNG (no display needed) for visual checking.

    QT_QPA_PLATFORM=offscreen python3 tests/screenshots.py out_dir
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from conftest import pump, wait_until  # noqa: E402
from fake_desk import FakeDesk  # noqa: E402
from touchdesk import config as cfgmod  # noqa: E402
from touchdesk.bluetooth import BluetoothBackend  # noqa: E402
from touchdesk.session import DeskSession  # noqa: E402
from touchdesk.ui.main_window import MainWindow  # noqa: E402


class DemoBT(BluetoothBackend):
    available = True
    device_name = "Gareth's iPhone"
    has_player = True
    status = "playing"
    track = {"Title": "Calon Lân", "Artist": "Côr Meibion", "Album": "Hymns & Arias"}
    remembered = 6


def make_demo_art(path):
    """A stand-in album cover (gradient + shapes), since we can't ship real artwork."""
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter

    img = QImage(200, 200, QImage.Format.Format_RGB32)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 200, 200)
    g.setColorAt(0, QColor("#c0392b"))
    g.setColorAt(1, QColor("#1b2a49"))
    p.fillRect(img.rect(), g)
    p.setBrush(QColor(255, 255, 255, 60))
    p.setPen(QColor(0, 0, 0, 0))
    p.drawEllipse(40, 40, 120, 120)
    p.end()
    img.save(str(path))
    return str(path)


def shoot(win, out, name, w=800, h=480):
    win.resize(w, h)
    pump(0.15)
    win.grab().save(str(out / f"{name}.png"))
    print("saved", name)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    QApplication.instance() or QApplication([])
    DemoBT.art_path = make_demo_art(out / "_demo_art.png")
    desk = FakeDesk(port=0, host="127.0.0.1").start()
    desk.state["/ch/02/mix/fader"] = 0.45
    desk.state["/ch/03/mix/on"] = 0
    desk.state["/ch/04/mix/fader"] = 0.6

    def make(extra=None, bt=DemoBT(), w=800, h=480):
        data = {"desk": {"ip": "127.0.0.1", "port": desk.port}, "use_desk_names": False}
        data.update(extra or {})
        cfg = cfgmod.from_dict(data, Path("/home/pi/.config/touchdesk/config.json"))
        cfg.save = lambda *a, **k: None
        s = DeskSession(cfg)
        scale = min(w / 800, h / 480)
        win = MainWindow(cfg, s, bt, scale)
        win.resize(w, h)
        win.show()
        s.start()
        wait_until(lambda: s.online and all(c.level is not None for c in s.channels), 3)
        return win, s

    win, s = make()
    shoot(win, out, "1-lock")
    win.lock.pad._add("1"); win.lock.pad._add("2")
    shoot(win, out, "1b-lock-typing")
    for _ in range(3):
        win.lock._check("9999")
    shoot(win, out, "1c-lock-wrong")
    win.show_page(win.MIXER)
    shoot(win, out, "2-mixer")
    win.show_page(win.ADMIN)
    shoot(win, out, "4-admin")
    win.admin._change_pin("pin")
    shoot(win, out, "4b-admin-pin")
    s.stop(); win.close()

    class NoArtBT(DemoBT):
        art_path = ""

    win, s = make({"level_display": "db", "display": {"title": "Blue Room"},
                   "channels": [{"label": f"#{i}", "type": "ch", "number": 4 + i,
                                 **({"icon": "bluetooth"} if i == 4 else {})} for i in range(1, 5)],
                   "security": {"pin_enabled": False}}, bt=NoArtBT())
    shoot(win, out, "3-blue-room-db-no-artwork")
    s.stop(); win.close()

    desk.silent = True
    win, s = make({"security": {"pin_enabled": False}}, bt=BluetoothBackend())
    shoot(win, out, "5-desk-offline")
    shoot(win, out, "5b-desk-offline-1024x600", 1024, 600)
    s.stop(); win.close()
    desk.stop()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "screens")

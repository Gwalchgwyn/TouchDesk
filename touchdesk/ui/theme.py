"""Colours and the Qt stylesheet. Designed for an 800x480 screen, scaled to fit others.

The colours follow TouchDesk 1.x so existing users see a familiar screen.
"""

from __future__ import annotations

BG = "#0d1f2d"  # top bar and window
PANEL = "#082740"  # main area
STRIP_ON = "#2b2b2b"
STRIP_OFF = "#4a4a4a"
FILL_ON = "#007fe0"
FILL_OFF = "#70b0e1"
TEXT = "#ffffff"
TEXT_DIM = "#9aa7b3"
LIVE = "#f80101"  # the red "ON" from 1.x
MUTED_TEXT = "#818181"
OK = "#3ecf6a"
WARN = "#f0a020"
BAD = "#ff4d4d"
KEY = "#2b2b2b"
KEY_DOWN = "#606060"
ACCENT = "#007fe0"


def stylesheet(s: float) -> str:
    """s = scale factor relative to 800x480."""

    def px(v: float) -> str:
        return f"{max(1, round(v * s))}px"

    return f"""
    QWidget {{ color: {TEXT}; font-family: "Carlito", "DejaVu Sans", sans-serif; font-size: {px(16)}; }}
    #Root {{ background: {BG}; }}
    #Main {{ background: {PANEL}; border: 1px solid #ffffff; }}

    /* top bar */
    #TopBar {{ background: {BG}; }}
    #TopBar QPushButton {{
        background: {BG}; border: none; border-left: 1px solid #ffffff;
        min-width: {px(106)}; min-height: {px(50)}; font-size: {px(16)}; font-weight: bold;
    }}
    #TopBar QPushButton:pressed {{ background: {PANEL}; }}
    #TopBar QPushButton:disabled {{ color: #4d5d6b; }}
    #TopBar QPushButton[tab="true"] {{ border-left: none; border-right: 1px solid #ffffff; }}
    #TopBar QPushButton[tab="true"]:checked {{ background: {PANEL}; }}
    #Title {{ font-size: {px(18)}; font-weight: bold; padding: 0 {px(12)}; }}
    #Status {{ font-size: {px(14)}; padding: 0 {px(10)}; }}

    /* channel strips */
    #Strip {{ background: {STRIP_ON}; border-right: 1px solid black; }}
    #Strip[live="false"] {{ background: {STRIP_OFF}; }}
    #StripName {{ font-size: {px(16)}; font-weight: bold; padding: {px(4)} {px(2)}; }}
    #Readout {{ font-size: {px(18)}; font-weight: bold; }}
    #Mute {{
        background: {STRIP_ON}; color: {LIVE}; border: none; border-top: 1px solid black;
        font-size: {px(32)}; font-weight: bold; min-height: {px(56)};
    }}
    #Mute[live="false"] {{ background: {STRIP_OFF}; color: {MUTED_TEXT}; }}
    #Mute:disabled {{ color: #5a5a5a; }}

    QSlider#Fader {{ background: transparent; min-width: {px(72)}; }}
    QSlider#Fader::groove:vertical {{ width: {px(8)}; border-radius: {px(3)}; background: transparent; }}
    QSlider#Fader::handle:vertical {{
        background: #8d8d8d; border: 2px solid black; height: {px(44)};
        margin: 0 -{px(26)}; border-radius: {px(22)};
    }}
    QSlider#Fader::handle:vertical:pressed {{ background: #565656; }}
    QSlider#Fader::add-page:vertical {{ background: {FILL_ON}; border-radius: {px(3)}; }}
    QSlider#Fader::sub-page:vertical {{ background: white; border-radius: {px(3)}; }}
    QSlider#Fader[mode="off"]::handle:vertical {{ background: #cdcdcd; }}
    QSlider#Fader[mode="off"]::add-page:vertical {{ background: {FILL_OFF}; }}
    QSlider#Fader[mode="offline"]::handle:vertical {{ background: #555555; border-color: #333333; }}
    QSlider#Fader[mode="offline"]::add-page:vertical {{ background: #3a4a58; }}
    QSlider#Fader[mode="offline"]::sub-page:vertical {{ background: #707070; }}

    /* banners */
    #Banner {{
        background: rgba(13, 31, 45, 230); border: 2px solid {WARN}; border-radius: {px(10)};
        font-size: {px(20)}; padding: {px(16)};
    }}

    /* keypad */
    #Key {{
        background: {KEY}; border: 1px solid black; border-radius: {px(33)};
        min-width: {px(66)}; max-width: {px(66)}; min-height: {px(66)}; max-height: {px(66)};
        font-size: {px(32)}; font-weight: bold;
    }}
    #Key[small="true"] {{ font-size: {px(22)}; }}
    #Key:pressed {{ background: {KEY_DOWN}; }}
    #Key:disabled {{ color: #555555; background: #1e2a33; }}
    #PinDots {{
        background: white; color: black; border: 3px solid black;
        font-size: {px(36)}; min-height: {px(64)}; min-width: {px(230)};
    }}
    #PinPrompt {{ font-size: {px(20)}; font-weight: bold; }}
    #PinMessage {{ font-size: {px(16)}; color: {WARN}; min-height: {px(22)}; }}

    /* bluetooth */
    #BtHeader {{ font-size: {px(22)}; font-weight: bold; }}
    #BtDevice {{ color: {TEXT_DIM}; font-size: {px(15)}; }}
    #BtField {{ color: {TEXT_DIM}; font-size: {px(16)}; }}
    #BtValue {{ font-size: {px(18)}; }}
    #BtButton {{
        background: {KEY}; border: 1px solid black; border-radius: {px(30)};
        min-width: {px(60)}; max-width: {px(60)}; min-height: {px(60)}; max-height: {px(60)};
    }}
    #BtButton:pressed {{ background: {KEY_DOWN}; }}

    /* installer settings */
    #AdminTitle {{ font-size: {px(22)}; font-weight: bold; }}
    #AdminInfo {{ font-size: {px(15)}; color: {TEXT_DIM}; }}
    #AdminButton {{
        background: {KEY}; border: 1px solid black; border-radius: {px(8)};
        min-height: {px(52)}; font-size: {px(16)}; font-weight: bold; padding: 0 {px(10)};
    }}
    #AdminButton:pressed {{ background: {KEY_DOWN}; }}
    #AdminButton[primary="true"] {{ background: {ACCENT}; }}
    """

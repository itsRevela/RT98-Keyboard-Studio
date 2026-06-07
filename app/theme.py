"""Visual theme: a warm beige palette with soft pastel (green/pink/blue) accents.

`PALETTE` holds the colors (also used by custom-painted widgets); `stylesheet()`
returns the global Qt Style Sheet.
"""
from __future__ import annotations

PALETTE = {
    "bg":        "#EDE4D3",   # app background (warm beige)
    "surface":   "#F8F3E9",   # cards / panels (cream)
    "surface2":  "#E4D9C3",   # rail / dock (slightly deeper beige)
    "border":    "#D8CBB2",   # soft tan borders
    "border_lo": "#E7DDC9",   # subtle dividers
    "text":      "#4A4137",   # warm dark-brown text
    "muted":     "#9A8C76",   # secondary text
    "canvas":    "#2C2823",   # dark viewport behind previews (content pops)
    "green":     "#A6D2A9",   # pastel green (primary / connected)
    "green_hi":  "#93C698",
    "pink":      "#F0B9C8",   # pastel pink (active / play)
    "pink_hi":   "#E9A7BA",
    "blue":      "#AECBEC",   # pastel blue (selection / focus / slider fill)
    "blue_hi":   "#9BBEE6",
    "danger":    "#E6A6A6",   # soft red (remove / errors)
}


def stylesheet() -> str:
    p = PALETTE
    return f"""
* {{
    font-family: "Segoe UI", "Inter", system-ui, sans-serif;
    font-size: 13px;
    color: {p['text']};
}}
QWidget#root, QMainWindow, QWidget {{ background: {p['bg']}; }}

/* --- top bar --- */
QFrame#topbar {{
    background: {p['surface']};
    border-bottom: 1px solid {p['border']};
}}
QLabel#appTitle {{ font-size: 17px; font-weight: 700; color: {p['text']}; padding: 0 6px; }}
QLabel#statusDot {{ font-size: 15px; padding: 0 5px; color: {p['muted']}; }}
QLabel#statusDot[state="on"] {{ color: {p['green_hi']}; }}
QLabel#statusDot[state="off"] {{ color: {p['muted']}; }}
QLabel#statusDot[state="busy"] {{ color: {p['blue_hi']}; }}
QLabel#statusText {{ color: {p['muted']}; font-size: 12px; padding: 0 10px; }}

/* --- cards / panels --- */
QFrame#card, QFrame#rail, QFrame#dock {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 14px;
}}
QFrame#rail, QFrame#dock {{ background: {p['surface2']}; }}
QLabel#cardTitle {{ color: {p['muted']}; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; }}
QLabel#muted {{ color: {p['muted']}; font-size: 12px; }}

/* --- buttons --- */
QPushButton {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 7px 14px;
    color: {p['text']};
}}
QPushButton:hover {{ background: {p['blue']}; border-color: {p['blue_hi']}; }}
QPushButton:pressed {{ background: {p['blue_hi']}; }}
QPushButton:disabled {{ color: {p['muted']}; background: {p['border_lo']};
    border-color: {p['border_lo']}; }}
QPushButton#primary {{
    background: {p['green']}; border: 1px solid {p['green_hi']};
    font-weight: 700; padding: 9px 20px;
}}
QPushButton#primary:hover {{ background: {p['green_hi']}; }}
QPushButton#primary:disabled {{ background: {p['border_lo']}; border-color: {p['border_lo']}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {p['border']}; }}
QPushButton#ghost:hover {{ background: {p['surface']}; }}
QPushButton#danger:hover {{ background: {p['danger']}; border-color: {p['danger']}; }}
QPushButton#round {{
    background: {p['pink']}; border: 1px solid {p['pink_hi']};
    border-radius: 20px; padding: 0; font-size: 15px; color: {p['text']};
}}
QPushButton#round:hover {{ background: {p['pink_hi']}; }}
QPushButton#round:disabled {{ background: {p['border_lo']}; border-color: {p['border_lo']}; }}

/* --- sliders --- */
QSlider:horizontal {{ min-height: 24px; }}
QSlider::groove:horizontal {{
    height: 6px; border-radius: 3px; background: {p['border']};
}}
QSlider::sub-page:horizontal {{ background: {p['blue_hi']}; border-radius: 3px; }}
QSlider::add-page:horizontal {{ background: {p['border']}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {p['surface']}; border: 2px solid {p['blue_hi']};
    width: 14px; height: 14px; margin: -6px 0; border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{ border-color: {p['green_hi']}; background: {p['green']}; }}

/* --- screen slot tiles --- */
QFrame#slotTile {{
    background: {p['surface2']};
    border: 2px solid {p['border']};
    border-radius: 12px;
}}
QFrame#slotTile[selected="true"] {{
    border-color: {p['blue_hi']};
    background: {p['surface']};
}}
QLabel#slotThumb {{
    background: {p['canvas']};
    border-radius: 8px;
    color: {p['muted']};
    font-size: 11px;
}}
QLabel#slotThumb[empty="true"] {{ background: {p['border_lo']}; }}
QWidget#slotCap {{ background: transparent; }}

/* --- library rail rows (item widgets) --- */
QWidget#railRow, #railRow QWidget {{ background: transparent; }}

/* --- list / rail --- */
QListWidget {{
    background: transparent; border: none; outline: 0;
}}
QListWidget::item {{
    color: {p['text']}; border-radius: 10px; padding: 4px; margin: 3px;
}}
QListWidget::item:selected {{ background: {p['blue']}; color: {p['text']}; }}
QListWidget::item:hover {{ background: {p['border_lo']}; }}

/* --- inputs --- */
QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {p['surface']}; border: 1px solid {p['border']};
    border-radius: 8px; padding: 4px 8px;
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {p['surface']}; border: 1px solid {p['border']};
    selection-background-color: {p['blue']}; outline: 0;
}}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {p['border']}; background: {p['surface']};
}}
QCheckBox::indicator:checked {{ background: {p['green']}; border-color: {p['green_hi']}; }}

/* --- progress --- */
QProgressBar {{
    background: {p['border']}; border: none; border-radius: 7px;
    height: 12px; text-align: center; color: {p['text']}; font-size: 10px;
}}
QProgressBar::chunk {{ background: {p['green_hi']}; border-radius: 7px; }}

QToolTip {{ background: {p['text']}; color: {p['surface']}; border: none;
    padding: 5px 8px; border-radius: 6px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QMessageBox {{ background: {p['surface']}; }}
"""

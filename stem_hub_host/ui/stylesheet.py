"""加载 QSS 样式表."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication

from . import theme


_QSS_CACHE: Optional[str] = None


_LEGACY_COLOR_TOKENS = {
    "#050B12": lambda: theme.BG_OUTER,
    "#0A1119": lambda: theme.BG_BASE,
    "#101A26": lambda: theme.BG_CARD,
    "#111A24": lambda: theme.BG_CARD,
    "#152032": lambda: theme.BG_CARD_HOVER,
    "#22344A": lambda: theme.BG_CARD_HOVER,
    "#0A1320": lambda: theme.BG_SUB_CARD,
    "#0E1A24": lambda: theme.BG_SUB_CARD,
    "#16242E": lambda: theme.BG_SUB_CARD,
    "#0C1521": lambda: theme.BG_INPUT,
    "#0A1018": lambda: theme.BG_INPUT,
    "#1A2A38": lambda: theme.BG_CONTROL,
    "#1E2A38": lambda: theme.BORDER,
    "#2A3A4E": lambda: theme.BORDER_LIGHT,
    "#5A6E84": lambda: theme.FG_TERTIARY,
    "#3A4A5E": lambda: theme.FG_DISABLED,
    "#E6EDF3": lambda: theme.FG_PRIMARY,
    "#8DA0B8": lambda: theme.FG_SECONDARY,
    "#5EEAD4": lambda: theme.ACCENT,
    "#7FF0DD": lambda: theme.ACCENT_HOVER,
    "#2DD4BF": lambda: theme.ACCENT_PRESSED,
    "#0E7490": lambda: theme.ACCENT_DARK,
    "#1A4A45": lambda: theme.ACCENT_DIM,
    "#3FB950": lambda: theme.STATUS_OK,
    "#D29922": lambda: theme.STATUS_WARN,
    "#F85149": lambda: theme.STATUS_ERROR,
    "#0E3D3A": lambda: theme.BG_TEAL_DARK,
    "#1F6F66": lambda: theme.BORDER_TEAL,
}


def _qss_path() -> Path:
    return Path(__file__).parent / "style.qss"


def get_qss() -> str:
    global _QSS_CACHE
    if _QSS_CACHE is None:
        qss = _qss_path().read_text(encoding="utf-8")
        for legacy, token in _LEGACY_COLOR_TOKENS.items():
            qss = qss.replace(legacy, token())
        _QSS_CACHE = qss
    return _QSS_CACHE


def invalidate_cache() -> None:
    global _QSS_CACHE
    _QSS_CACHE = None


def apply_to(app: QApplication) -> None:
    invalidate_cache()
    app.setStyleSheet(get_qss())

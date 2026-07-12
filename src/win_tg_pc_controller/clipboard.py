from __future__ import annotations

import platform
from types import ModuleType

from .i18n import Language, t


MAX_CLIPBOARD_DISPLAY = 3500


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise RuntimeError("clipboard controls are only supported on Windows")


def _load_tkinter() -> ModuleType:
    try:
        import tkinter as tk
    except ImportError as exc:
        raise RuntimeError("tkinter is not available in this Python installation") from exc
    return tk


def _root():
    tk = _load_tkinter()
    root = tk.Tk()
    root.withdraw()
    return root


def get_clipboard_text() -> str:
    _require_windows()
    tk = _load_tkinter()
    root = _root()
    try:
        try:
            value = root.clipboard_get()
        except tk.TclError:
            return ""
        return value if isinstance(value, str) else ""
    finally:
        root.destroy()


def set_clipboard_text(text: str) -> None:
    _require_windows()
    root = _root()
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    finally:
        root.destroy()


def clear_clipboard() -> None:
    set_clipboard_text("")


def format_clipboard_text(text: str, language: Language) -> str:
    if not text:
        return t(language, "clipboard.empty")
    if len(text) > MAX_CLIPBOARD_DISPLAY:
        return text[:MAX_CLIPBOARD_DISPLAY] + "\n... clipboard text truncated ..."
    return text

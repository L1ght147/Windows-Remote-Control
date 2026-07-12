from win_tg_pc_controller.clipboard import MAX_CLIPBOARD_DISPLAY, format_clipboard_text


def test_format_clipboard_text_handles_empty_text() -> None:
    assert "empty" in format_clipboard_text("", "en")


def test_format_clipboard_text_truncates_long_text() -> None:
    text = "x" * (MAX_CLIPBOARD_DISPLAY + 10)
    formatted = format_clipboard_text(text, "en")

    assert len(formatted) < len(text)
    assert "truncated" in formatted

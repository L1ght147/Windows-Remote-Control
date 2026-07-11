from win_tg_pc_controller.windows_session import (
    WindowsSessionInfo,
    format_windows_session,
    screenshot_unavailable_reason,
)


def test_format_windows_session_marks_active_session() -> None:
    text = format_windows_session(
        WindowsSessionInfo(
            user="PC\\User",
            is_windows=True,
            is_admin=False,
            process_id=123,
            process_session_id=1,
            active_console_session_id=1,
            desktop_accessible=True,
            explorer_sessions=(1,),
        )
    )

    assert "Bot in active session: yes" in text
    assert "Desktop accessible: yes" in text
    assert "Explorer sessions: 1" in text


def test_screenshot_reason_for_wrong_session() -> None:
    reason = screenshot_unavailable_reason(
        WindowsSessionInfo(
            user="PC\\User",
            is_windows=True,
            is_admin=False,
            process_id=123,
            process_session_id=0,
            active_console_session_id=1,
            desktop_accessible=True,
            explorer_sessions=(1,),
        )
    )

    assert reason is not None
    assert "активной пользовательской сессии" in reason


def test_screenshot_reason_for_locked_desktop() -> None:
    reason = screenshot_unavailable_reason(
        WindowsSessionInfo(
            user="PC\\User",
            is_windows=True,
            is_admin=False,
            process_id=123,
            process_session_id=1,
            active_console_session_id=1,
            desktop_accessible=False,
            explorer_sessions=(1,),
        )
    )

    assert reason is not None
    assert "рабочий стол недоступен" in reason

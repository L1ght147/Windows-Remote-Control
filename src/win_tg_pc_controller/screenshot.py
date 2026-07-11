from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import mss
from PIL import Image

from .windows_session import collect_windows_session_info, screenshot_unavailable_reason


@dataclass(frozen=True)
class MonitorInfo:
    id: int
    width: int
    height: int
    left: int
    top: int
    is_all: bool = False


def list_monitors() -> list[MonitorInfo]:
    try:
        with mss.mss() as screen:
            monitors = []
            for index, monitor in enumerate(screen.monitors):
                monitors.append(
                    MonitorInfo(
                        id=index,
                        width=int(monitor["width"]),
                        height=int(monitor["height"]),
                        left=int(monitor["left"]),
                        top=int(monitor["top"]),
                        is_all=index == 0,
                    )
                )
            return monitors
    except Exception as exc:
        raise RuntimeError(f"скриншоты недоступны: {exc}") from exc


def capture_screenshot_png(monitor_id: int = 0) -> BytesIO:
    info = collect_windows_session_info()
    reason = screenshot_unavailable_reason(info)
    if reason is not None:
        raise RuntimeError(f"скриншот недоступен: {reason}")

    buffer = BytesIO()
    try:
        with mss.mss() as screen:
            if monitor_id < 0 or monitor_id >= len(screen.monitors):
                raise ValueError("Unknown monitor")
            monitor = screen.monitors[monitor_id]
            shot = screen.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
            image.save(buffer, format="PNG")
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "скриншот недоступен: Windows не отдала изображение рабочего стола. "
            "Проверьте, что бот запущен в пользовательской сессии, рабочий стол не заблокирован "
            f"и нет активного UAC/secure desktop. Техническая причина: {exc}"
        ) from exc
    buffer.seek(0)
    buffer.name = f"screenshot-monitor-{monitor_id}.png"
    return buffer

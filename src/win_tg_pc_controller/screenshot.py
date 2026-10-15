from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import mss
from PIL import Image

from .windows_session import collect_windows_session_info, screenshot_unavailable_reason


# Telegram limits for photos sent with sendPhoto.
PHOTO_MAX_BYTES = 10_000_000
PHOTO_MAX_DIMENSIONS_SUM = 10000
JPEG_QUALITIES = (90, 80, 70)
DOWNSCALE_STEP = 0.75


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


def _resized(image: Image.Image, scale: float) -> Image.Image:
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def _encode(image: Image.Image, image_format: str, **options: object) -> BytesIO:
    buffer = BytesIO()
    image.save(buffer, format=image_format, **options)
    return buffer


def encode_for_telegram(image: Image.Image, name_stem: str) -> BytesIO:
    """Encode a screenshot in memory so Telegram accepts it as a photo.

    PNG is kept when it fits; otherwise the image is sent as JPEG, downscaled
    until it fits the size limit. Nothing is written to disk.
    """
    scale = PHOTO_MAX_DIMENSIONS_SUM / (image.width + image.height)
    if scale < 1:
        image = _resized(image, scale)

    buffer = _encode(image, "PNG")
    extension = "png"
    while buffer.getbuffer().nbytes > PHOTO_MAX_BYTES:
        for quality in JPEG_QUALITIES:
            buffer = _encode(image, "JPEG", quality=quality)
            extension = "jpg"
            if buffer.getbuffer().nbytes <= PHOTO_MAX_BYTES:
                break
        else:
            image = _resized(image, DOWNSCALE_STEP)

    buffer.seek(0)
    buffer.name = f"{name_stem}.{extension}"
    return buffer


def capture_screenshot(monitor_id: int = 0) -> BytesIO:
    info = collect_windows_session_info()
    reason = screenshot_unavailable_reason(info)
    if reason is not None:
        raise RuntimeError(f"скриншот недоступен: {reason}")

    try:
        with mss.mss() as screen:
            if monitor_id < 0 or monitor_id >= len(screen.monitors):
                raise ValueError("Unknown monitor")
            monitor = screen.monitors[monitor_id]
            shot = screen.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "скриншот недоступен: Windows не отдала изображение рабочего стола. "
            "Проверьте, что бот запущен в пользовательской сессии, рабочий стол не заблокирован "
            f"и нет активного UAC/secure desktop. Техническая причина: {exc}"
        ) from exc
    return encode_for_telegram(image, f"screenshot-monitor-{monitor_id}")

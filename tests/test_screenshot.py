import os

from PIL import Image

import win_tg_pc_controller.screenshot as screenshot_module
from win_tg_pc_controller.screenshot import encode_for_telegram


def _noise(width: int, height: int) -> Image.Image:
    return Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))


def test_small_screenshot_stays_png() -> None:
    buffer = encode_for_telegram(Image.new("RGB", (800, 600), "white"), "shot")

    assert buffer.name == "shot.png"
    assert Image.open(buffer).size == (800, 600)


def test_wide_screenshot_is_scaled_to_dimension_limit() -> None:
    buffer = encode_for_telegram(Image.new("RGB", (11520, 2160), "white"), "shot")

    width, height = Image.open(buffer).size
    assert width + height <= screenshot_module.PHOTO_MAX_DIMENSIONS_SUM


def test_large_screenshot_is_compressed_to_size_limit(monkeypatch) -> None:
    monkeypatch.setattr(screenshot_module, "PHOTO_MAX_BYTES", 100_000)

    buffer = encode_for_telegram(_noise(800, 600), "shot")

    assert buffer.name == "shot.jpg"
    assert buffer.getbuffer().nbytes <= 100_000
    assert buffer.tell() == 0

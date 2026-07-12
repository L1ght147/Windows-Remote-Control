from pathlib import Path

from win_tg_pc_controller.language_store import LanguageStore


def test_language_store_persists_selected_language(tmp_path: Path) -> None:
    path = tmp_path / "user_settings.json"

    store = LanguageStore(path)
    assert store.get(123) is None

    store.set(123, "en")

    reloaded = LanguageStore(path)
    assert reloaded.get(123) == "en"


def test_language_store_ignores_unknown_language_values(tmp_path: Path) -> None:
    path = tmp_path / "user_settings.json"
    path.write_text('{"123": "de", "456": "ru"}', encoding="utf-8")

    store = LanguageStore(path)

    assert store.get(123) is None
    assert store.get(456) == "ru"

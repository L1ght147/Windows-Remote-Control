from win_tg_pc_controller.i18n import MESSAGES, LocalizedError, t


def test_all_languages_define_the_same_keys() -> None:
    assert set(MESSAGES["ru"]) == set(MESSAGES["en"])


def test_translation_uses_selected_language() -> None:
    assert t("ru", "menu.status") == "🖥 Статус"
    assert t("en", "menu.status") == "🖥 Status"


def test_timer_failure_is_fully_localized() -> None:
    assert t("en", "timer.failed") == "❌ Auto screenshots stopped."


def test_localized_error_renders_in_requested_language() -> None:
    error = LocalizedError("screenshot.capture_failed", error="boom")

    assert "boom" in error.localized("ru")
    assert error.localized("ru").startswith("скриншот недоступен")
    assert str(error).startswith("screenshot is unavailable")


def test_english_messages_have_no_cyrillic() -> None:
    bilingual_keys = {"language.choose"}
    untranslated = [
        key
        for key, value in MESSAGES["en"].items()
        if key not in bilingual_keys and any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in value)
    ]

    assert untranslated == []

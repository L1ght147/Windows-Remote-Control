from win_tg_pc_controller.i18n import localize_text, t


def test_localize_text_translates_main_menu_label() -> None:
    assert localize_text("en", "🖥 Статус") == "🖥 Status"


def test_localize_text_keeps_russian_text() -> None:
    assert localize_text("ru", "🖥 Статус") == "🖥 Статус"


def test_timer_failure_is_fully_localized() -> None:
    assert t("en", "timer.failed") == "❌ Auto screenshots stopped."

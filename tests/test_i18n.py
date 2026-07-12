from win_tg_pc_controller.i18n import localize_text


def test_localize_text_translates_main_menu_label() -> None:
    assert localize_text("en", "🖥 Статус") == "🖥 Status"


def test_localize_text_keeps_russian_text() -> None:
    assert localize_text("ru", "🖥 Статус") == "🖥 Статус"

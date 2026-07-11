from win_tg_pc_controller.security import ConfirmationStore, is_allowed_user


def test_allowed_user_exact_match() -> None:
    assert is_allowed_user(123, 123)
    assert not is_allowed_user(456, 123)
    assert not is_allowed_user(None, 123)


def test_confirmation_requires_same_action() -> None:
    store = ConfirmationStore(ttl_seconds=30)
    store.request(123, "shutdown")

    assert not store.confirm(123, "reboot")
    assert not store.confirm(123, "shutdown")


def test_confirmation_can_be_cancelled() -> None:
    store = ConfirmationStore(ttl_seconds=30)
    store.request(123, "sleep")

    assert store.cancel(123)
    assert not store.confirm(123, "sleep")


def test_confirmation_can_allow_multiple_actions_once() -> None:
    store = ConfirmationStore(ttl_seconds=30)
    store.request_any(123, ["app:run:notepad", "app:run_admin:notepad"])

    assert store.confirm(123, "app:run_admin:notepad")
    assert not store.confirm(123, "app:run:notepad")

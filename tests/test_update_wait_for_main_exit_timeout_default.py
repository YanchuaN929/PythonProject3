import inspect


def test_wait_for_main_exit_default_timeout_is_30_seconds():
    from update import updater_cli

    sig = inspect.signature(updater_cli.wait_for_main_exit)
    assert sig.parameters["timeout"].default == 30




"""Broker CDP port fallback must not reuse another profile's reservation."""

import socket

from notebooklm_tools.utils import cdp


def test_fallback_skips_other_profiles_reserved_port(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_AUTH_BROKER_ENABLED", "true")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_BROKER_PROFILES", "pte,harmonywave13")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_BROKER_HEADLESS_CDP_PORT", "19224")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_BROKER_CDP_PORT_STRIDE", "2")

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def bind(self, address):
            if address[1] in (19224, 19225):
                raise OSError("synthetic port already occupied")

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: FakeSocket())
    blocked = cdp._other_broker_reserved_headless_ports("pte")
    assert blocked == {19226}
    assert (
        cdp.find_available_port(
            starting_from=19224,
            max_attempts=4,
            allow_ephemeral_fallback=False,
            excluded_ports=blocked,
        )
        == 19227
    )

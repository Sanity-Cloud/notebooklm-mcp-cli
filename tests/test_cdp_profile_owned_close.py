from notebooklm_tools.utils import cdp


def test_close_profile_owned_cdp_browser_closes_exact_managed_profile(monkeypatch):
    closed: list[tuple[str, str]] = []
    cleared: list[int] = []
    alive = iter([True, False, False])

    monkeypatch.setattr(cdp, "_listener_pid", lambda _port: 4242)
    monkeypatch.setattr(cdp, "_mapped_chrome_owns_profile", lambda _pid, _profile, _port: True)
    monkeypatch.setattr(
        cdp,
        "_fetch_cdp_version",
        lambda _port, timeout=1: {
            "webSocketDebuggerUrl": "ws://127.0.0.1:9227/devtools/browser/managed"
        },
    )
    monkeypatch.setattr(
        cdp, "execute_cdp_command", lambda url, command: closed.append((url, command))
    )
    monkeypatch.setattr(cdp, "_pid_is_alive", lambda _pid: next(alive))
    monkeypatch.setattr(cdp, "_clear_port_map", cleared.append)
    monkeypatch.setattr(cdp.time, "sleep", lambda _seconds: None)

    assert cdp.close_profile_owned_cdp_browser("http://127.0.0.1:9227", "harmonywave13") is True
    assert closed == [("ws://127.0.0.1:9227/devtools/browser/managed", "Browser.close")]
    assert cleared == [9227]


def test_close_profile_owned_cdp_browser_leaves_foreign_browser_running(monkeypatch):
    monkeypatch.setattr(cdp, "_listener_pid", lambda _port: 4242)
    monkeypatch.setattr(cdp, "_mapped_chrome_owns_profile", lambda _pid, _profile, _port: False)
    monkeypatch.setattr(
        cdp,
        "execute_cdp_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("foreign browser must not close")
        ),
    )

    assert cdp.close_profile_owned_cdp_browser("http://127.0.0.1:9227", "harmonywave13") is False


def test_close_profile_owned_cdp_browser_rejects_remote_endpoint(monkeypatch):
    monkeypatch.setattr(
        cdp,
        "_listener_pid",
        lambda _port: (_ for _ in ()).throw(
            AssertionError("remote endpoint must not be inspected")
        ),
    )

    assert cdp.close_profile_owned_cdp_browser("http://192.0.2.10:9227", "harmonywave13") is False


def test_launch_chrome_process_opens_notebooklm_url_immediately(monkeypatch, tmp_path):
    launched: list[list[str]] = []

    class FakeProcess:
        pid = 1234

    monkeypatch.setattr(cdp, "get_chrome_path", lambda: "chrome")
    monkeypatch.setattr(cdp, "_get_profile_dir_for_launch", lambda _path, _profile: tmp_path)
    monkeypatch.setattr(
        cdp.subprocess,
        "Popen",
        lambda args, **_kwargs: launched.append(args) or FakeProcess(),
    )

    process = cdp.launch_chrome_process(port=9227, profile_name="harmonywave13")

    assert process is not None
    assert launched[0][-1] == cdp.NOTEBOOKLM_URL
    assert f"--user-data-dir={tmp_path}" in launched[0]
    assert "--remote-debugging-port=9227" in launched[0]

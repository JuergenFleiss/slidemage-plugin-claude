# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""The public route contract, cheap registration and host-owned services."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

from claude import activate
from claude.code import hook, launch
from claude.code.route import TERMINAL_ONLY
from claude.credentials import ApiCredentials
from fake_host import FakeHost, FakeSurfaceContext
from slidemage.plugin_api import Route


@pytest.fixture
def host(tmp_path):
    return FakeHost(tmp_path)


def test_activate_registers_routes_one_combined_section_and_hook(host):
    activate(host)
    host.active = False
    assert list(host.routes) == ["anthropic_api", "claude_code"]
    assert [(p, title) for p, title, _ in host.sections] == [("ai", "Claude")]
    build = host.sections[0][2]
    for route, service in zip(host.routes.values(), ("Anthropic API", "Claude Code")):
        assert route.service == service and route.is_local is False
        assert route.settings_section() is None
    assert host.entry_points == {"hook": hook.main}
    assert host.secret.env_var == "ANTHROPIC_API_KEY"
    assert not host.terminals and not host.watches and not host.tool_calls
    assert host.secret.reads == 0


def test_activate_has_no_network_or_slow_work(host, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("activate attempted I/O, a CLI probe, widgets or a heavy host service")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(launch, "find_claude", forbidden)
    monkeypatch.setattr(launch, "signed_in", forbidden)
    monkeypatch.setattr(host.secret, "get", forbidden)
    for name in ("terminal", "ai_tools", "watch_external_edits", "run_in_background", "Page"):
        monkeypatch.setattr(host, name, forbidden)
    activate(host)


def test_activation_in_a_fresh_process_does_not_load_qt_or_providers():
    result = subprocess.run([sys.executable, "-c", """
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from fake_host import FakeHost, FakeSurfaceContext
from slidemage.plugin_api import Route
from claude import activate
with TemporaryDirectory() as folder:
    activate(FakeHost(Path(folder)))
assert not any(n.startswith('PySide6') for n in sys.modules)
assert 'claude.api.provider' not in sys.modules
assert 'claude.code.terminal.session' not in sys.modules
"""], env={**os.environ, "PYTHONPATH": os.pathsep.join(["tests", ".", os.environ.get("PYTHONPATH", "")])},
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_route_problems_and_static_choices(host, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("claude.credentials._legacy_key", lambda ctx=None: None)
    monkeypatch.setattr(launch, "find_claude", lambda: None)
    activate(host)
    api, code = host.routes.values()
    assert api.problem(None, Route("anthropic_api", "chat")).startswith("No Anthropic API key yet")
    assert api.model_choices(None, "chat") == []
    assert code.provider(None, Route("claude_code", "chat")) is None
    assert api.chat_surface() is None and api.task_runner(None, Route("anthropic_api", "chat")) is None
    assert api.draft_backend(None, Route("anthropic_api", "chat")) is None
    assert api.translation_backend(None, Route("anthropic_api", "chat")) is None
    assert api.split_choice("custom") == ("custom", None) and api.valid_choice(None, "custom")
    assert not api.valid_choice(None, "")
    assert api.work_label(Route("anthropic_api", "chat", "custom")) == "custom · API"
    assert code.split_choice("opus:high") == ("opus", "high")
    assert code.valid_choice(None, "opus:high") and not code.valid_choice(None, "opus:invalid")
    assert code.work_label(Route("claude_code", "chat")) == "Claude Code · terminal"
    assert code.work_label(Route("claude_code", "chat", "opus", "high")) == "Claude Code · Opus · effort high"
    assert code.default_choice("chat") == "" and code.model_choices(None, "translation") == []
    assert code.choice_label("haiku:medium") == "Haiku · medium"
    assert len(code.model_choices(None, "chat")) == 9
    host.secret.set("sk-host")
    assert api.problem(None, Route("anthropic_api", "chat")) == ""
    assert api.default_choice("chat") in api.model_choices(None, "chat")
    provider = api.provider(None, SimpleNamespace(model="chosen-model", task="chat"))
    assert provider.model == "chosen-model" and provider._api_key == "sk-host"


def test_legacy_credentials_use_host_migration_and_clear_never_resurrects(host, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    host.legacy_value = "sk-old"
    credentials = ApiCredentials(host)
    assert credentials.get().value == "sk-old"
    host.secret.set("sk-new")
    assert credentials.get().value == "sk-new"
    credentials.set("")
    assert ApiCredentials(host).get() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    assert credentials.get().value == "sk-env"


def test_task_buttons_and_ai_requests_on_claude_code_say_to_use_the_terminal(host):
    from slidemage.plugin_api import ProviderError
    activate(host)
    code = host.routes["claude_code"]
    for task in ("chat", "translation", "fixes_notes_transcripts"):
        assert code.problem(None, Route("claude_code", task)) == TERMINAL_ONLY
    with pytest.raises(ProviderError) as refused:
        code.request_provider(None, Route("claude_code", "chat", "opus", "high"))
    assert str(refused.value) == TERMINAL_ONLY and "terminal" in TERMINAL_ONLY
    assert code.task_runner(None, Route("claude_code", "translation")) is None


def test_terminal_surface_uses_host_services_and_guards_late_callbacks(qapp, host, monkeypatch):
    from claude.code.terminal import session as module
    from claude.code import scope
    monkeypatch.setattr(launch, "has_transcript", lambda _: True)
    class Server:
        url, token = "http://localhost:1/mcp", "secret"
        def __init__(self, toolbox): self.toolbox = toolbox
        def start(self): pass
        def stop(self): pass
    context = FakeSurfaceContext(host)
    surface = module.ClaudeCodeSession(host, context, host.root / "claude", launch, scope, Server,
                                       lambda: launch.hook_command(host))
    try:
        surface.start(80, 24, choice="sonnet:high")
        first = host.terminals[-1]
        assert first.cwd == host.root and first.env[launch.TOKEN_ENV] == "secret"
        assert host.watches[0].running
        event = SimpleNamespace(added=(), modified=(host.root / "slide.tex",), removed=())
        host.watches[0].on_change(event)
        assert context.changes == [event]
        surface.set_scope("deck")
        surface._server.toolbox()
        assert host.tool_calls[-1][0] == "deck"
        kept = surface.session_id
        surface.start(80, 24, resume=True, choice="opus:medium")
        assert not first.running and surface.session_id == kept
        command = host.terminals[-1].argv
        assert command[command.index("--model") + 1] == "opus" and "--resume" in command
        surface.stop()
        assert not surface.running and not host.watches[0].running
    finally:
        surface.shutdown()


def test_settings_builder_saves_key_and_checks_auth_off_activation(qapp, host, monkeypatch):
    from PySide6.QtWidgets import QLineEdit, QPushButton, QLabel
    monkeypatch.setattr("claude.credentials._legacy_key", lambda ctx=None: None)
    monkeypatch.setattr(launch, "find_claude", lambda: None)
    activate(host)
    page = host.sections[0][2]()
    try:
        assert any("not installed" in label.text() for label in page.findChildren(QLabel))
        page.findChild(QLineEdit).setText("sk-saved")
        next(button for button in page.findChildren(QPushButton) if button.text() == "Save key").click()
        assert host.secret.values["key"] == "sk-saved"
        assert host.model_notifications == ["anthropic_api"]
    finally:
        page.close()


def test_fake_host_exposes_real_host_methods():
    from inspect import isfunction
    from slidemage.plugin_api import Host
    assert {name for name, value in vars(Host).items() if isfunction(value) and not name.startswith("_")} <= set(dir(FakeHost))


def test_surface_start_failure_stops_watch_and_can_be_retried(qapp, host, monkeypatch):
    from claude.code.terminal import session as module
    from claude.code import scope
    class Server:
        url, token = "http://localhost:1/mcp", "t"
        def __init__(self, toolbox): pass
        def start(self): pass
        def stop(self): pass
    surface = module.ClaudeCodeSession(host, FakeSurfaceContext(host), host.root / "claude", launch, scope,
                                       Server, lambda: launch.hook_command(host))
    start = host.start
    monkeypatch.setattr(host, "start", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cannot start")))
    try:
        with pytest.raises(OSError, match="cannot start"):
            surface.start(80, 24)
        assert not host.watches[0].running and not surface.running
        monkeypatch.setattr(host, "start", start)
        surface.start(80, 24)
        assert surface.running and host.watches[0].running
        host.terminals[-1].options["on_exit"](0)
        assert not host.watches[0].running
    finally:
        surface.shutdown()


def test_translate_is_taken_as_a_prompt_with_the_slide_as_an_at_path(host, tmp_path):
    from types import SimpleNamespace
    activate(host)
    code = host.routes["claude_code"]
    route, ctx = Route("claude_code", "translation"), SimpleNamespace(root=tmp_path)
    slide = tmp_path / "slides" / "1y8-EN-Title-current.tex"
    prompt = code.task_prompt(ctx, route, "translate", slide, "DE")
    assert prompt.startswith("Translate @slides/1y8-EN-Title-current.tex into DE.") and "add_slide" in prompt
    assert '@"slides/my slide-EN-T-current.tex"' in code.task_prompt(ctx, route, "translate", tmp_path / "slides" / "my slide-EN-T-current.tex", "DE")
    assert code.task_prompt(ctx, route, "translate", None, "") == ""             # only asked whether it is taken
    assert code.task_prompt(ctx, route, "update_translation", slide, "") is None
    assert code.task_prompt(ctx, route, "proofread", slide, "") is None

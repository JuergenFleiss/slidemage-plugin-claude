# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""Structural Host fake: recorded registrations and services, with unused operations unavailable."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace


class FakeSettings:
    def __init__(self):
        self.data = {}
        self.saved = 0

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        self.saved += 1


class FakeCredentials:
    def __init__(self):
        self.env_var = None
        self.values = {}
        self.reads = 0

    def get(self, name="key"):
        self.reads += 1
        value = os.environ.get(self.env_var, "").strip() if self.env_var and name == "key" else ""
        return value or self.values.get(name)

    def where(self, name="key"):
        if self.env_var and name == "key" and os.environ.get(self.env_var, "").strip():
            return "environment"
        return "file" if self.values.get(name) else ""

    def set(self, value, name="key"):
        if value.strip():
            self.values[name] = value.strip()
            return "file"
        self.values.pop(name, None)
        return ""

    def clear(self, name="key"):
        self.set("", name)


class FakeWatch:
    def __init__(self, on_change):
        self.on_change = on_change
        self.running = False
        self.stops = []

    def start(self):
        self.running = True

    def stop(self, *, last_look=True):
        self.stops.append(last_look)
        self.running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def emit(self, **changes):
        self.on_change(SimpleNamespace(**{"added": (), "removed": (), "modified": (), **changes}))


class FakeTerminal:
    def __init__(self, argv, env, cwd, **options):
        self.argv, self.env, self.cwd, self.options = argv, env, cwd, options
        self.running = True
        self.widget = object() if options.get("with_widget", True) else None
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    def resize(self, cols, rows):
        self.size = (cols, rows)

    def stop(self):
        self.running = False

    def close(self):
        self.stop()
        self.closed, self.widget = True, None


class FakeHost:
    def __init__(self, root: Path):
        self.root = root
        self.routes, self.sections, self.entry_points = {}, [], {}
        self.secret = FakeCredentials()
        self.store = FakeSettings()
        self.terminals, self.watches, self.tool_calls = [], [], []
        self.current_focus = SimpleNamespace(deck=None, slide=None, scope="slide")
        self.active = True
        self.legacy_value = None
        self.model_notifications = []
        self.argv = [sys.executable, "-m", "slidemage", "--plugin", "claude:hook"]

    def cache_dir(self):
        path = self.root / ".cache"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def legacy_cache_dir(self):
        return None

    def _unavailable(self):
        raise NotImplementedError("FakeHost does not implement this unused operation")

    def add_command(self, id, title, run, enabled=lambda deck: True): self._unavailable()
    def add_menu_entry(self, menu, command_id): self._unavailable()
    def add_deck_settings_tab(self, title, build, footer_action=None): self._unavailable()
    def add_settings_tab(self, title, build): self._unavailable()
    def add_sidebar_box(self, key, title, build, size="compact", when=lambda deck: True): self._unavailable()
    def refresh_sidebar_box(self, key): self._unavailable()
    def add_render_priority(self, soon): self._unavailable()
    def insert_positions(self, deck): self._unavailable()
    def insert_slides(self, deck, position, slides, language): self._unavailable()
    def edit_deck_text(self, deck, change): self._unavailable()
    def deck_language(self, deck): self._unavailable()
    def project_languages(self): self._unavailable()
    def project_root(self): return self.root
    def deck_output_folder(self, deck, view="instructor"): self._unavailable()
    def deck_slides(self, deck, view, language): self._unavailable()
    def slide_source(self, ref): self._unavailable()
    def open_slide(self, ref): self._unavailable()
    def open_url(self, url): self._unavailable()
    def open_deck_settings(self, deck, tab=None): self._unavailable()
    def log(self, message, level="info"): self._unavailable()
    def debug_enabled(self): self._unavailable()
    def show_message(self, text, error=False): self._unavailable()

    def _register(self):
        if not self.active:
            raise RuntimeError("registrations are only allowed in activate()")

    def add_ai_route(self, route):
        self._register()
        if route.id in self.routes:
            raise ValueError(route.id)
        self.routes[route.id] = route

    def add_settings_section(self, page, title, build):
        self._register()
        self.sections.append((page, title, build))

    def add_entry_point(self, name, fn):
        self._register()
        if name in self.entry_points:
            raise ValueError(name)
        self.entry_points[name] = fn

    def entry_point_command(self, name):
        assert name == "hook"
        return list(self.argv)

    def credentials(self, env_var=None):
        self.secret.env_var = env_var
        return self.secret

    def settings(self):
        return self.store

    def legacy_secret(self, name):
        assert name == "anthropic_api_key"
        return self.legacy_value

    def legacy_ollama_host(self): return "http://localhost:11434"
    def model_choices_changed(self, route_id): self.model_notifications.append(route_id)
    def acquire_route_task(self, route_id, label): self._unavailable()
    def ai_chat(self): self._unavailable()
    def run_in_background_with_progress(self, work, progress, done):
        self.run_in_background(lambda: work(progress), done)
    def style_chat_widget(self, widget, role): pass
    def theme_color(self, name): return "#000000"
    def Surface(self): self._unavailable()
    def Button(self, *args, **kwargs): self._unavailable()
    def Chip(self, *args, **kwargs): self._unavailable()
    def IconButton(self, *args, **kwargs): self._unavailable()
    def IconLabel(self, *args, **kwargs): self._unavailable()
    def Window(self, title): self._unavailable()
    def Card(self, raised=False): self._unavailable()
    def SegmentedControl(self, items, current=None): self._unavailable()
    def Badge(self, text, tone="neutral"): self._unavailable()
    def ElidedLabel(self, text): self._unavailable()
    def RowButton(self, title, sub="", *, icon=None, chip=("", ""), selectable=False): self._unavailable()
    def PlainList(self): self._unavailable()
    def Label(self, text, role="body"): self._unavailable()
    def ModalSheet(self, title, parent=None): self._unavailable()
    def toast(self, parent, text): self._unavailable()
    def theme(self): self._unavailable()
    def on_theme_changed(self, callback): self._unavailable()
    def icon(self, name, color, px=16): self._unavailable()

    def terminal(self):
        return self

    def start(self, argv, env=None, cwd=None, *, on_output=None, on_exit=None,
              with_widget=True, cols=80, rows=24, widget=None):
        terminal = FakeTerminal(argv, env, cwd, on_output=on_output, on_exit=on_exit,
                                with_widget=with_widget, cols=cols, rows=rows)
        self.terminals.append(terminal)
        return terminal

    def watch_external_edits(self, on_change):
        watch = FakeWatch(on_change)
        self.watches.append(watch)
        return watch

    def ai_tools(self, scope="slide", *, focus_slide=None, mode="auto", cancel=None, workspace=None):
        self.tool_calls.append((scope, focus_slide, mode, cancel, workspace))
        return SimpleNamespace(specs=[], execute=lambda call: None)

    def focus(self):
        return self.current_focus

    def run_in_background(self, work, done):
        try:
            result = work()
        except BaseException as error:
            done(None, error)
        else:
            done(result, None)

    def Page(self):
        from PySide6.QtCore import Signal
        from PySide6.QtWidgets import QWidget, QVBoxLayout

        class Page(QWidget):
            changed = Signal()

            def __init__(self):
                super().__init__()
                self.body = QVBoxLayout(self)
        return Page()

    def Field(self, label, widget):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.addWidget(QLabel(label))
        layout.addWidget(widget)
        return field

    def caption(self, text, tone=""):
        from PySide6.QtWidgets import QLabel
        return QLabel(text)


class FakeSurfaceContext:
    def __init__(self, host):
        self.host = host
        self.project_root = host.root
        self.changes = []
        self.current_scope = "slide"

    def selected_route(self, route_id, task, choice=""):
        from slidemage.plugin_api import Route
        model, _, effort = choice.partition(":")
        return Route(route_id, task, model, effort or None)

    def focus_details(self):
        focus = self.host.current_focus
        return SimpleNamespace(slide_id=None, slide=focus.slide, deck=focus.deck, view="", language="", dirty=False)

    def apply_external_edits(self, changes): self.changes.append(changes)
    def build_tools(self, host, scope, cancel):
        return host.ai_tools(scope, focus_slide=host.current_focus.slide, cancel=cancel)
    def scope(self): return self.current_scope
    def close(self): pass

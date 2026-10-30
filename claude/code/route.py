# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""Claude Code's task runner and terminal conversation route."""
from __future__ import annotations

import threading
from typing import Any

from slidemage.plugin_api import Host, Route
from claude.api.route import TASKS

NO_CLAUDE = "Claude Code is not installed on this computer, so nothing was sent and no other model is used."
CHAT_IN_TERMINAL = ("On Cloud · Claude Code the conversation is the terminal in the assistant; the chat "
                    "with Ollama or the API is not available on this route.")
MODELS = ("sonnet", "haiku", "opus")
EFFORTS = ("low", "medium", "high")


class ClaudeCodeRoute:
    id = "claude_code"
    service = "Claude Code"
    is_local = False
    tasks = TASKS

    def __init__(self, host: Host) -> None:
        self.host = host

    def problem(self, ctx: Any, route: Route) -> str:
        return CHAT_IN_TERMINAL if route.task == "chat" else ""

    def model_choices(self, ctx: Any, task: str) -> list[str]:
        return [f"{model}:{effort}" for model in MODELS for effort in EFFORTS]

    def default_choice(self, task: str) -> str:
        return "" if task == "chat" else "haiku:medium"

    def choice_label(self, choice: str) -> str:
        model, _, effort = choice.partition(":")
        return f"{model.capitalize()} · {effort}"

    def split_choice(self, choice: str) -> tuple[str, str | None]:
        model, _, effort = choice.partition(":")
        return model, effort or None

    def valid_choice(self, ctx: Any, choice: str) -> bool:
        return choice in self.model_choices(ctx, "chat")

    def work_label(self, route: Route) -> str:
        return " · ".join(["Claude Code", *([route.model.capitalize(), f"effort {route.effort}"] if route.model
                                             else ["terminal"])])

    @staticmethod
    def _claude():
        from slidemage.plugin_api import ProviderError
        from claude.code.launch import find_claude
        path = find_claude()
        if path is None:
            raise ProviderError(NO_CLAUDE)
        return path

    def provider(self, ctx: Any, route: Route):
        return None

    def request_provider(self, ctx: Any, route: Route):
        from claude.code.provider import ClaudeCodeProvider
        return ClaudeCodeProvider(self._claude(), route.model, route.effort)

    def task_runner(self, ctx: Any, route: Route):
        from claude.code.runner import run_task
        claude = self._claude()
        def run(task, captured: str, request: str, cancel=None, span=None):
            return run_task(ctx, claude, task, captured, request, route.model, route.effort,
                            cancel=cancel, span=span)
        return run

    def draft_backend(self, ctx: Any, route: Route, cancel=None):
        from claude.code.images import ClaudeDraftBackend
        return ClaudeDraftBackend(ctx, self._claude(), route.model, route.effort, cancel or threading.Event())

    def translation_backend(self, ctx: Any, route: Route, cancel=None):
        from claude.code.images import ClaudeTranslationBackend
        return ClaudeTranslationBackend(ctx, self._claude(), route.model, route.effort, cancel or threading.Event())

    def slide_translator(self, ctx: Any, route: Route):
        from claude.code.runner import SlideTranslator
        return SlideTranslator(ctx, self._claude(), route.model, route.effort)

    def chat_surface_v2(self, context):
        from claude.code.terminal.view import ClaudeCodeView
        from claude.code import launch, scope
        from claude.code.mcp_server import McpServer
        return ClaudeCodeView(self.host, context, launch, scope, McpServer,
                              lambda: launch.hook_command(self.host))

    def chat_surface(self, *args, **kwargs):
        return None  # the public v2 context is required for the terminal

    def settings_section(self):
        return None  # registered once for both routes with add_settings_section

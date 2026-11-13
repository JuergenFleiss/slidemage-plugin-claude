# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""Claude Code's terminal conversation route: the terminal is all it offers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from slidemage.plugin_api import Host, ProviderError, Route
from claude.code.terminal.draft import mention

TERMINAL_ONLY = ("On Cloud · Claude Code, ask Claude in the terminal. The task buttons (except Translate, which "
                 "types its prompt there) and AI requests need Cloud · Anthropic API or Local.")
MODELS = ("sonnet", "haiku", "opus")
EFFORTS = ("low", "medium", "high")


class ClaudeCodeRoute:
    id = "claude_code"
    service = "Claude Code"
    is_local = False
    tasks = frozenset({"chat"})

    def __init__(self, host: Host) -> None:
        self.host = host

    def problem(self, ctx: Any, route: Route) -> str:
        return TERMINAL_ONLY

    def model_choices(self, ctx: Any, task: str) -> list[str]:
        return [f"{model}:{effort}" for model in MODELS for effort in EFFORTS] if task == "chat" else []

    def default_choice(self, task: str) -> str:
        return ""

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

    def provider(self, ctx: Any, route: Route):
        return None

    def request_provider(self, ctx: Any, route: Route):
        raise ProviderError(TERMINAL_ONLY)

    def draft_backend(self, ctx: Any, route: Route, cancel=None):
        return None

    def translation_backend(self, ctx: Any, route: Route, cancel=None):
        return None

    def slide_translator(self, ctx: Any, route: Route):
        return None

    def task_runner(self, ctx: Any, route: Route):
        return None

    def task_prompt(self, ctx: Any, route: Route, task_name: str, slide_path: Path | None, language: str) -> str | None:
        """The Translate button types this into Claude Code's input box; the user sends it (view.fill_prompt). With no
        slide core only asks whether the task is taken: it is."""
        if task_name != "translate":
            return None
        if slide_path is None:
            return ""
        slide = mention(slide_path.relative_to(ctx.root).as_posix())
        return (f"Translate {slide} into {language}. Call add_slide with translation_of set to that slide, language "
                f"{language}, and a slug and frame title in {language}: it makes a linked copy and puts it after the "
                "source in the deck. Then translate the copy's text in place with modify_slide. Keep LaTeX commands, "
                "layout and labels unchanged.")

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

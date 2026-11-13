# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""Claude Code's terminal conversation route: the terminal is all it offers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from slidemage.plugin_api import Host, ProviderError, Route
from claude.code.terminal.draft import mention

TERMINAL_ONLY = ("On Cloud · Claude Code, ask Claude in the terminal. Task buttons type their prompt there for you "
                 "to send; image tasks and other AI requests need Cloud · Anthropic API or Local.")
# What a task button types into Claude Code's input box, as one line, for the user to send. {slide} and {deck} are
# @mentions, {language} the language's name ("German"), {code} its code ("DE"). A deck bubble (`<task>_deck`) is one
# prompt for the deck: it names the bubble's criterion, never its slides.
_TRANSLATE = ("First read_guide translation. Then call add_slide with translation_of set to the slide, language {code}, "
              "and a slug and frame title in {language}: it makes a linked copy after the source in the deck. Then "
              "translate the copy's text in place with modify_slide, giving the copy's path. Keep LaTeX commands, "
              "layout and labels unchanged.")
_UPDATE = ("First read_guide translation. A translation's header line '%% Translation of: <slide>' names its source. "
           "Change only what the source's changes require, with modify_slide.")
PROMPTS = {
    "translate": "Translate {slide} into {language}. " + _TRANSLATE,
    "update_translation": "Update the {language} translation {slide} to the current version of its source slide. " + _UPDATE,
    "fix_latex": "Fix the LaTeX errors in {slide}: run lint on it, then fix each listed error with the smallest change, "
                 "using modify_slide. Change nothing else.",
    "proofread": "Proofread {slide}: fix spelling, grammar, punctuation and capitalization only, with modify_slide. "
                 "Do not reword. If there is nothing to fix, say so.",
    "concise": "Make the text of {slide} more concise with modify_slide: shorter wording, the same statements, the "
               "same structure (environments, overlays, citations).",
    "title": "Write a shorter, more informative frame title for {slide}, in its language, and set it with "
             "modify_slide. Change nothing else.",
    "note": "Write a speaker note for {slide}: two to four plain sentences in its language, what the instructor says "
            "to present it. Add it with modify_slide as a \\note command inside the frame.",
    "readable": "Make {slide} readable in a lecture hall: run check_readability on it, then fix what it reports with "
                "modify_slide. Never change what a statement says.",
    "rewrite": "Rewrite the text I have selected in {slide} (read_selection) with modify_slide; change nothing outside "
               "the selection. What to do: {instruction}",
    "proofread_selection": "Proofread the text I have selected in {slide} (read_selection): spelling, grammar, "
                           "punctuation and capitalization only, no rewording. Use modify_slide; change nothing "
                           "outside the selection.",
    "translate_deck": "Translate the slides of {deck} that are in another language of the project and have no linked "
                      "{language} translation yet into {language}, one slide after the other. " + _TRANSLATE,
    "update_translation_deck": "Update the translations in {deck} that no longer match their source slide: compare each "
                               "with its source's current text, update those that differ and leave the others alone. "
                               + _UPDATE,
    "fix_latex_deck": "Fix the LaTeX errors in the slides of {deck} that have lint errors (list_slides flags them): for "
                      "each, run lint on it, then fix each listed error with the smallest change, using modify_slide. "
                      "Change nothing else.",
    "summarise_deck": "Summarise the deck {deck} for me: what it covers, in slide order, in a few short paragraphs in "
                      "the slides' language. Read its slides with list_slides. Do not change any file.",
}
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

    def task_prompt(self, ctx: Any, route: Route, task_name: str, slide_path: Path | None, language: str, *,
                    language_name: str = "", instruction: str = "", deck_path: Path | None = None) -> str | None:
        """A task button types this into Claude Code's input box; the user sends it (view.fill_prompt). A deck bubble
        has no slide, only the deck. With neither core only asks whether the task is taken: it is when PROMPTS has it."""
        if slide_path is None and deck_path is None:
            return "" if any(key.removesuffix("_deck") == task_name for key in PROMPTS) else None
        template = PROMPTS.get(task_name if slide_path is not None else f"{task_name}_deck")
        if template is None:
            return None
        mentions = {name: mention(path.relative_to(ctx.root).as_posix())
                    for name, path in (("slide", slide_path), ("deck", deck_path)) if path is not None}
        text = template.format(**mentions, language=language_name or language, code=language, instruction=instruction)
        return " ".join(text.split())                       # one line: a line end would send it

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

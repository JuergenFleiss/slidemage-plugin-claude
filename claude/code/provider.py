# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""A self-contained, text-only chat request through the isolated Claude Code runner."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from slidemage.plugin_api import Cancelled, ChatReply, ProviderError
from claude.code import runner


@dataclass
class ClaudeCodeProvider:
    claude: Path
    model: str
    effort: str | None
    cancel: threading.Event = field(default_factory=threading.Event, init=False)
    is_local = False

    @property
    def label(self) -> str:
        return f"Claude Code · {self.model}" if self.model else "Claude Code"

    def list_models(self) -> list[str]:
        return list(runner.MODELS)

    def abort(self) -> None:
        self.cancel.set()

    def chat(
        self, messages: list[dict[str, str]], *, system: str = "",
        images: list[bytes] | None = None, schema: dict | None = None,
        temperature: float = 0.2, max_tokens: int = 2048, timeout: float = 300.0,
        think: bool = False, num_ctx: int | None = None,
    ) -> ChatReply:
        if self.cancel.is_set():
            raise Cancelled("Aborted.")
        if images:
            raise ProviderError("Claude Code request chat supports text only.")
        # History is data in this one request, never a resumed CLI session. Replace the CLI system prompt
        # even when none was supplied. Tool access is disabled by the runner, independent of these prompts.
        request = "Answer the final user message in this JSON conversation:\n" + json.dumps(messages, ensure_ascii=False)
        # The CLI controls its output budget; max_tokens and the other backend-specific hints are not CLI
        # flags. Only an explicit CLI stop signal marks a reply as truncated.
        try:
            result = runner.run_text(self.claude, request, system or "Answer the user's request.", self.model,
                                     self.effort, time.monotonic() + timeout, self.cancel, schema)
        except OSError as exc:
            raise ProviderError(f"Could not run Claude Code: {exc}") from exc
        if result.cancelled or self.cancel.is_set():
            raise Cancelled("Aborted.")
        if result.error:
            raise ProviderError(result.error)
        return ChatReply(text=result.text, truncated=result.truncated)

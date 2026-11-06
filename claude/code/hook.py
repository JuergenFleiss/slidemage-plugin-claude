# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""The hooks that record Claude writes and keep the embedded Claude Code away from what SlideMage manages (UI redesign
step 10c). Claude Code runs this command before every Edit, Write or MultiEdit, with the call as JSON on
stdin; exit code 2 blocks the call and hands stderr to Claude as the reason, any other code lets it go.

    SlideMage --plugin claude:hook           (argv supplied by host.entry_point_command)

The rules are the chat tools' (tools/edits.py): an edit that changes a slide's protected parts, as SlideMage's
plugin_api.protected_spans reports them, is refused, and a frozen version (-vX-Y-Z.tex) is read-only. From SlideMage
v0.14.25 those are the '%%' lines at the top of a slide and its \\setSlideVersion line, and the ordinary '%' notes at
the top are editable; before, the whole comment block at the top was protected. \\vbox to 0pt{...} blocks are not
protected since SlideMage v9.4.0. The messages say whichever rule the running SlideMage applies (notes_editable).
Everything else, and anything this hook cannot work out (except a slide that exists but cannot be read), is allowed: it must never get in the way of a
call that is fine, and a crash is only a warning. It cannot see what a Bash command does to a file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from typing import Any
from claude.code import scope as claude_scope
from slidemage.plugin_api import hook_context_from_environment, protected_spans

BLOCK = 2
FROZEN_MESSAGE = ("{name} is a frozen version of a slide: a historical record, read-only. "
                  "Edit the slide's -current.tex file instead.")
UNREADABLE_MESSAGE = ("{name} cannot be read as UTF-8 text, so SlideMage cannot check that the edit leaves the "
                      "slide's protected parts alone. Ask the user to look at the file.")
FILE_TOOLS = ("Edit", "Write", "MultiEdit")


# The same user-facing guard as SlideMage's slide_protection; only the public span reader is needed.
_PROBE = "% a note\n%% Included in decks: x\n%%\n\n\\setSlideVersion{1-0-0}\nbody\n"


def notes_editable() -> bool:
    """Whether the running SlideMage leaves the ordinary '%' notes at the top of a slide editable (v0.14.25 on) or
    protects the whole comment block there (before)."""
    return all(not (start <= 0 < end) for start, end in protected_spans(_PROBE))


def protected_description() -> str:
    """What is protected, in the words of the running SlideMage's rule."""
    if notes_editable():
        return ("the '%%' lines at the top of the file (such as '%% Included in decks:') or the \\setSlideVersion "
                "line. SlideMage manages those; leave them as they are and change only the rest of the slide. The "
                "ordinary '%' notes at the top may be edited.")
    return ("the comment block at the top of the file or the \\setSlideVersion line. SlideMage manages those; "
            "leave them as they are and change only the rest of the slide.")


PROTECTED_MESSAGE = "That edit would change a protected part of the slide: " + protected_description()


def protected_problem(before: str, after: str) -> str | None:
    """The message when `after` changes a protected part of `before`. The protected texts must stay the same and in
    the same order. A non-comment line put above them, or moving them out of the comment block at the top, loses them
    in SlideMage's reading and is refused that way too."""
    def parts(text: str):
        return [text[start:end] for start, end in protected_spans(text)]
    return None if parts(before) == parts(after) else PROTECTED_MESSAGE


def _read(ctx: Any, path: Path) -> str | None:
    try:
        return ctx.read_text(path).replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        return None


def _lf(value: object) -> str | None:
    return value.replace("\r\n", "\n") if isinstance(value, str) else None


def _replace(text: str, old: str, new: str, everywhere: bool) -> str | None:
    """`text` after Claude Code's Edit of old -> new; None when that edit would fail on its own."""
    count = text.count(old)
    if not old or count == 0 or (count > 1 and not everywhere):
        return None
    return text.replace(old, new) if everywhere else text.replace(old, new, 1)


def _result(tool: str, args: dict, before: str) -> str | None:
    """The file's text after the call, or None if it cannot be worked out."""
    if tool == "Write":
        return _lf(args.get("content"))
    edits = args.get("edits") if tool == "MultiEdit" else [args]
    text = before
    for edit in edits if isinstance(edits, list) else []:
        old, new = _lf(edit.get("old_string")), _lf(edit.get("new_string"))
        if old is None or new is None:
            return None
        text = _replace(text, old, new, bool(edit.get("replace_all")))
        if text is None:
            return None
    return text


def blocked_reason(ctx: Any, event: dict) -> str | None:
    """Why the hook call `event` (Claude Code's JSON) must be blocked, or None to let it go."""
    tool, args = event.get("tool_name"), event.get("tool_input")
    raw = args.get("file_path") if isinstance(args, dict) else None
    if tool not in FILE_TOOLS or not isinstance(raw, str):
        return None
    try:
        base = Path(event["cwd"]) if isinstance(event.get("cwd"), str) else ctx.root
        path = (Path(raw) if Path(raw).is_absolute() else base / raw).resolve()
    except (OSError, RuntimeError):
        return None
    outside = claude_scope.edit_problem(claude_scope.load(os.environ.get(claude_scope.FOCUS_ENV)), ctx.root, path)
    if outside:
        return outside
    kind = ctx.slide_kind(path)
    if kind == "frozen":
        return FROZEN_MESSAGE.format(name=path.name)
    if kind != "current":
        return None
    before = _read(ctx, path)
    if before is None:
        # A slide that exists but cannot be read (not UTF-8, no permission): its protected parts cannot be
        # compared, so the call is refused rather than let through blind.
        return UNREADABLE_MESSAGE.format(name=path.name) if path.exists() else None
    after = _result(tool, args, before)
    return protected_problem(before, after) if after is not None else None


def record_write(ctx: Any, event: dict) -> None:
    """Pre captures text; successful Post records the slide and inserted calls, and sends a citation
    changed in the image descriptions store (media/alt-text.json) to review.

    Tool ids isolate simultaneous calls. The temporary pre snapshot is only
    needed to identify deck insertions and no-op writes; the review store itself is locked.
    """
    args = event.get("tool_input")
    raw = args.get("file_path") if isinstance(args, dict) else None
    if event.get("tool_name") not in FILE_TOOLS or not isinstance(raw, str):
        return
    base = Path(event.get("cwd") or ctx.root)
    path = (Path(raw) if Path(raw).is_absolute() else base / raw).resolve()
    if not path.is_relative_to(ctx.root.resolve()):
        return
    slide = ctx.slide_kind(path) == "current"
    deck = ctx.is_deck(path)
    store = ctx.is_image_store(path)
    if not slide and not deck and not store:
        return
    identity = str(event.get("tool_use_id") or f"{event.get('session_id', '')}:{path}")
    if event.get("hook_event_name") == "PreToolUse":
        ctx.write_snapshot(identity, {"new": not path.exists(), "before": _read(ctx, path)})
        return
    saved = ctx.read_snapshot(identity)
    ctx.delete_snapshot(identity)
    response = event.get("tool_response")
    if isinstance(response, dict) and (response.get("isError") or response.get("is_error")):
        return
    source = f"Claude Code terminal: {event['tool_name']}"
    if store:
        ctx.flag_edited_sources(path, saved.get("before") or "")   # a changed citation is to review
    elif slide and ("before" not in saved or saved["before"] != _read(ctx, path)):
        ctx.mark_review(path, "draft" if saved.get("new") else "edit", source, before=saved.get("before"))
    elif deck and path.is_file() and "before" in saved:
        ctx.record_inserted_slides(path, saved["before"] or "", ctx.read_text(path), source)


def main(args: list[str] | None = None) -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        if isinstance(event, dict) and event.get("hook_event_name") == "UserPromptSubmit":
            hook_context_from_environment().timing_event("prompt")
            data = claude_scope.load(os.environ.get(claude_scope.FOCUS_ENV))
            if data:
                print(claude_scope.prompt_context(data))   # stdout becomes context for this prompt
            return 0
        ctx = hook_context_from_environment()
        if isinstance(event, dict) and event.get("hook_event_name") == "PostToolUse":
            record_write(ctx, event)
            return 0
        reason = blocked_reason(ctx, event) if isinstance(event, dict) else None
        if not reason and isinstance(event, dict) and event.get("hook_event_name") == "PreToolUse":
            record_write(ctx, event)
    except Exception as exc:  # noqa: BLE001 -- not the hook's business to stop a call that is fine
        print(f"SlideMage hook: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if reason:
        print(reason, file=sys.stderr)
        return BLOCK
    return 0


if __name__ == "__main__":
    sys.exit(main())

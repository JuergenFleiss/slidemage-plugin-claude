# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""The PreToolUse hook of the embedded Claude Code (ai/claude_hook.py) with hook JSON as Claude Code sends it:
protected parts and frozen versions are blocked (exit code 2, the reason on stderr), everything else is
allowed, and so is anything the hook cannot work out."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

import pytest
from conftest import SLIDE_TEXT

from claude.code import hook as claude_hook
from claude.code.hook import PROTECTED_MESSAGE, notes_editable

from slidemage import project as slidemage_project
from slidemage.project import ProjectContext
from slidemage.plugins.hook import HookContext

@pytest.fixture
def ctx(root):
    return HookContext(ProjectContext.at(root))

CURRENT = "abc-EN-Hello-current.tex"
FROZEN = "abc-EN-Hello-v1-0-0.tex"


def event(root, tool, name=CURRENT, **tool_input):
    path = str(root / "slides" / name)
    return {"session_id": "s", "cwd": str(root), "hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": {"file_path": path, **tool_input}}


def edit(root, old, new, name=CURRENT, **more):
    return event(root, "Edit", name, old_string=old, new_string=new, **more)


@pytest.mark.parametrize("old, new", [
    ("First point", "1st point"),
    ("\\item First point", "\\item First\n\t\t\\item inserted"),
    ("First point\r\n\t\t\\item Second point", "x"),
    ("\\hbox{overlay}", "\\hbox{changed}"),                  # inside \vbox to 0pt{...}: editable since SlideMage v9.4.0
])
def test_an_edit_of_the_body_is_allowed(ctx, root, old, new):
    assert claude_hook.blocked_reason(ctx, edit(root, old, new)) is None


@pytest.mark.parametrize("old, new", [
    ("%% Included in decks: test", "%% Included in decks: test, other"),         # the header comment
    ("\\setSlideVersion{1-0-0}", "\\setSlideVersion{2-0-0}"),
    ("\\setSlideVersion{1-0-0}\r\n", ""),                                         # deleting a protected line
    ("\\setSlideVersion{1-0-0}\r\n\\begin", "\\begin"),
])
def test_an_edit_of_a_protected_part_is_blocked(ctx, root, old, new):
    assert claude_hook.blocked_reason(ctx, edit(root, old, new)) == PROTECTED_MESSAGE


def test_replace_all_counts_every_occurrence(ctx, root):
    assert claude_hook.blocked_reason(ctx, edit(root, "point", "idea", replace_all=True)) is None
    assert claude_hook.blocked_reason(ctx, edit(root, "1-0-0", "2-0-0", replace_all=True)) == PROTECTED_MESSAGE


def test_write_compares_the_whole_new_text(ctx, root):
    keep = SLIDE_TEXT.replace("First point", "1st")
    assert claude_hook.blocked_reason(ctx, event(root, "Write", content=keep)) is None
    assert claude_hook.blocked_reason(ctx, event(root, "Write", content="\\begin{standardframe}{x}\\end{standardframe}")) \
        == PROTECTED_MESSAGE


def test_multiedit_applies_the_edits_in_order(ctx, root):
    fine = [{"old_string": "First", "new_string": "1st"}, {"old_string": "Second", "new_string": "2nd"}]
    assert claude_hook.blocked_reason(ctx, event(root, "MultiEdit", edits=fine)) is None
    bad = [*fine, {"old_string": "1-0-0", "new_string": "9-9-9"}]
    assert claude_hook.blocked_reason(ctx, event(root, "MultiEdit", edits=bad)) == PROTECTED_MESSAGE
    # a later edit with replace_all reaches the version line as well as the text the first edit wrote
    chained = [{"old_string": "First", "new_string": "1-0-0 mark"},
               {"old_string": "1-0-0", "new_string": "2-0-0", "replace_all": True}]
    assert claude_hook.blocked_reason(ctx, event(root, "MultiEdit", edits=chained)) == PROTECTED_MESSAGE


@pytest.mark.parametrize("tool", ["Edit", "Write"])
def test_a_frozen_version_is_read_only(ctx, root, tool):
    event_ = edit(root, "First", "1st", FROZEN) if tool == "Edit" else event(root, "Write", FROZEN, content="x")
    reason = claude_hook.blocked_reason(ctx, event_)
    assert reason and FROZEN in reason and "frozen version" in reason and "-current.tex" in reason


def test_what_is_not_a_slide_or_cannot_be_judged_is_allowed(ctx, root):
    deck = event(root, "Edit", old_string="\\section{Intro}", new_string="\\section{Start}")
    deck["tool_input"]["file_path"] = str(root / "decks" / "test.tex")
    assert claude_hook.blocked_reason(ctx, deck) is None
    bib = event(root, "Write", content="@book{x}")
    bib["tool_input"]["file_path"] = str(root / "SlideMage.bib")
    assert claude_hook.blocked_reason(ctx, bib) is None
    assert claude_hook.blocked_reason(ctx, edit(root, "not in the file at all", "x")) is None      # Edit fails on its own
    assert claude_hook.blocked_reason(ctx, edit(root, "", "x")) is None
    assert claude_hook.blocked_reason(ctx, event(root, "Write", "zzz-EN-New-current.tex", content="x")) is None   # new file
    assert claude_hook.blocked_reason(ctx, event(root, "Read")) is None
    assert claude_hook.blocked_reason(ctx, event(root, "Bash")) is None
    assert claude_hook.blocked_reason(ctx, {"tool_name": "Edit", "tool_input": "garbage"}) is None
    assert claude_hook.blocked_reason(ctx, {}) is None
    assert claude_hook.blocked_reason(ctx, edit(root, "point", "idea")) is None     # twice in the file, no replace_all


def test_a_relative_path_is_taken_from_the_session_folder(ctx, root):
    relative = edit(root, "\\setSlideVersion{1-0-0}", "")
    relative["tool_input"]["file_path"] = f"slides/{CURRENT}"
    assert claude_hook.blocked_reason(ctx, relative) == PROTECTED_MESSAGE


# -- the command ---------------------------------------------------------------------------------------------

def run_main(monkeypatch, capsys, payload: str, root=None):
    if root is not None:
        monkeypatch.setenv(slidemage_project.ENV_VAR, str(root))
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload.encode())))
    code = claude_hook.main()
    return code, capsys.readouterr().err


def test_main_exits_2_with_the_reason_on_stderr_to_block(root, monkeypatch, capsys):
    code, err = run_main(monkeypatch, capsys, json.dumps(edit(root, "\\setSlideVersion{1-0-0}", "")), root)
    assert code == 2 and err.strip() == PROTECTED_MESSAGE
    code, err = run_main(monkeypatch, capsys, json.dumps(edit(root, "First point", "1st point")), root)
    assert code == 0 and err == ""


def test_main_never_blocks_because_of_its_own_trouble(monkeypatch, capsys):
    code, err = run_main(monkeypatch, capsys, "this is not json")
    assert code == 1 and "SlideMage hook" in err        # a non-blocking error: Claude Code goes on
    assert run_main(monkeypatch, capsys, "[]")[0] == 0


@pytest.mark.parametrize("argv, tool, name, arguments, reason", [
    (["-m", "claude.code.hook"], "Edit", CURRENT,
     {"old_string": "\\setSlideVersion{1-0-0}", "new_string": ""}, b"protected part"),
    (["-m", "claude.code.hook"], "Write", FROZEN, {"content": "x"}, b"frozen version"),
], ids=["plugin-edit", "plugin-write"])
def test_the_command_as_claude_code_runs_it(tmp_path, argv, tool, name, arguments, reason):
    """The plugin hook blocks edits in a real process without a window (dispatch awaits 3a/3c)."""
    project = make_project_in(tmp_path)
    payload = json.dumps({"cwd": str(project), "tool_name": tool, "tool_input": {
        "file_path": str(project / "slides" / name), **arguments}})
    env = {**os.environ, slidemage_project.ENV_VAR: str(project), "QT_QPA_PLATFORM": "offscreen"}
    done = subprocess.run([sys.executable, *argv], input=payload.encode(), env=env,
                          capture_output=True, timeout=60)
    assert done.returncode == 2 and reason in done.stderr


def make_project_in(tmp_path):
    """A real project folder (the subprocess reads it by SlideMage's project variable, so it needs the marker file)."""
    from slidemage import project

    root = tmp_path / "proj"
    (root / "slides").mkdir(parents=True)
    (root / project.MARKER).write_text("")
    (root / "slides" / CURRENT).write_bytes(SLIDE_TEXT.encode())
    return root.resolve()


def test_a_slide_that_cannot_be_read_is_refused_not_waved_through(ctx, root):
    (root / "slides" / CURRENT).write_bytes(b"\xff\xfe not utf-8 \x00")
    for call in (edit(root, "not utf-8", "x"), event(root, "Write", content="\\begin{x}")):
        reason = claude_hook.blocked_reason(ctx, call)
        assert reason and CURRENT in reason and "UTF-8" in reason


def test_the_hook_does_not_import_the_heavy_packages():
    """Each hook is a fresh process: it must start without the tools package, the compiler, PDF code or Qt."""
    code = ("import sys, claude.code.hook; "
            "print([m for m in sys.modules if m.split('.')[0] in ('fitz', 'pymupdf', 'PySide6') "
            "or m.startswith(('slidemage.ai.tools', 'slidemage.compiler', 'slidemage.preview_build', 'slidemage.slide_preview'))])")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert done.stdout.strip() == "[]", done.stdout + done.stderr


# SlideMage v0.14.25: the ordinary '%' notes at the top of a slide are its own text; only the '%%' lines are protected.
NOTE = "% Source: a paper, slide 3.\r\n"


@pytest.mark.skipif(not notes_editable(), reason="this SlideMage protects the whole comment block at the top")
def test_a_note_at_the_top_may_change_when_slidemage_allows_it(ctx, root):
    (root / "slides" / "abc-EN-Hello-current.tex").write_bytes((NOTE + SLIDE_TEXT).encode("utf-8"))
    assert claude_hook.blocked_reason(ctx, edit(root, "a paper", "Smith (2020)")) is None
    assert claude_hook.blocked_reason(ctx, edit(root, NOTE, "")) is None
    assert claude_hook.blocked_reason(ctx, edit(root, "decks: test", "decks: x")) == PROTECTED_MESSAGE
    assert "may be edited" in PROTECTED_MESSAGE


def test_the_message_follows_the_running_slidemage_and_never_names_overlay_blocks():
    assert "vbox" not in PROTECTED_MESSAGE and "setSlideVersion" in PROTECTED_MESSAGE
    assert ("may be edited" in PROTECTED_MESSAGE) == notes_editable()

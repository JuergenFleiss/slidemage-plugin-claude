# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""Starting the user's own Claude Code inside SlideMage (UI redesign step 10c): where `claude` is, and the
command line and environment that connect it to SlideMage's MCP server and protected-region hook.

Everything goes through command-line flags and the child's environment (`--mcp-config`, `--settings`,
`--append-system-prompt`): nothing is written to ~/.claude, to the project's .claude/ or to a .mcp.json.
The MCP bearer token is not on the command line (visible in `ps`): the config names the environment
variable it is read from, and only the child process gets it. No Qt.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from claude._processes import no_console_kwargs
from slidemage.plugin_api import Host
from claude.code.scope import FOCUS_ENV
from claude.code.hook import notes_editable
from slidemage.plugin_api import IMAGE_DESCRIPTION_RULES, CLAUDE_CODE_PRE_APPROVED

SERVER_NAME = "slidemage"
TOKEN_ENV = "SLIDEMAGE_MCP_TOKEN"
HOOK_MATCHER = "Edit|Write|MultiEdit"
INSTALL_URL = "https://docs.claude.com/en/docs/claude-code/setup"
AUTH_TIMEOUT_S = 15

ORIENTATION = (
    "You are running inside SlideMage, a desktop app for writing LaTeX (beamer) slide decks; the project is the "
    "current folder and the user sees SlideMage's editor beside this terminal. Each prompt's [SlideMage scope: ...] "
    "line carries the focus and scope: follow it; call get_focus only if the focus is missing or stale. "
    "Batch independent reads in one turn. Read before you change; use read_buffer for open files with unsaved "
    "edits and read_selection for a selection. For existing slides use modify_slide, for new drafts use "
    "create_slide, for skeletons or translations in place use add_slide, insert_slide to put an existing slide into "
    "the deck, and use native Edit/Write for other "
    "files; never make a slide file by hand. "
    "Read read_guide before writing something you are unsure of. Make the smallest change requested, keep the "
    "slide's style, and never invent a macro, citation key or fact. Check the preview after layout changes with "
    "render_preview when needed. Refreshing previews or compiling a deck is slow: use refresh_preview and "
    "refresh_deck_previews only when asked, and compile only when asked. Use check_readability to check and "
    "recheck readability changes. Slides are slides/<id>-<LANG>-<Slug>-current.tex, decks decks/<name>.tex. "
    "Never edit a frozen slides/*-vX-Y-Z.tex, " + (
        "the '%%' lines at the top of a slide (such as '%% Included in decks:') or its \\setSlideVersion line: a "
        "hook refuses those edits. The ordinary '%' notes at the top of a slide are its own text and may be edited. "
        if notes_editable() else
        "a slide's comment block at the top (all its '%' lines) or its \\setSlideVersion line: a hook refuses those "
        "edits. ") + "Overlay blocks (\\vbox to 0pt{...}) may be edited, but they hold measured page coordinates: "
    "change those only when asked. Do not rename slides, change deck calls "
    "or touch other tool-managed lines unless asked. SlideMage reloads files you change; if the user has unsaved "
    "edits in the same file it asks them first. After native edits to slides or add_slide, call show_slide so "
    "they see it. To translate a slide, read it, then write the translated slide with add_slide or modify_slide as "
    "the tools allow; do the translation yourself. "
    "Answer in the user's language, briefly: one or two sentences on what you did, no recap of slide content "
    "or list of things to check; end with at most one question offering a concrete next step. " + IMAGE_DESCRIPTION_RULES)


def _extra_dirs() -> list[Path]:
    home = Path.home()
    dirs = [home / ".local" / "bin", home / ".claude" / "local", home / ".npm-global" / "bin",
            Path("/usr/local/bin"), Path("/opt/homebrew/bin")]
    if sys.platform == "win32":
        dirs += [Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "npm",
                 Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Programs" / "claude"]
    return dirs


def find_claude() -> Path | None:
    """The user's `claude`: on PATH, else in the places its installers use (a desktop launcher often has a
    shorter PATH than a terminal)."""
    found = shutil.which("claude")
    if found:
        return Path(found)
    names = ("claude.exe", "claude.cmd", "claude") if sys.platform == "win32" else ("claude",)
    for folder in _extra_dirs():
        for name in names:
            candidate = folder / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
    return None


def signed_in(claude: Path) -> bool | None:
    """Whether `claude auth status` says the user is signed in; None when it cannot tell (an older Claude Code
    without the command, no answer in time). Blocks for a moment: not for the GUI thread."""
    try:
        done = subprocess.run([str(claude), "auth", "status"], capture_output=True, text=True, timeout=AUTH_TIMEOUT_S,
                              stdin=subprocess.DEVNULL, env=clean_environment(claude), **no_console_kwargs())
        status = json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    logged = status.get("loggedIn") if isinstance(status, dict) else None
    return logged if isinstance(logged, bool) else None


_WINDOWS_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_SHELL_SAFE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")


def _windows_word(arg: str) -> str:
    """One word of a hook command that bash (Claude Code's shell on Windows, Git Bash), cmd and PowerShell all read
    the same way. Backslashes in a path are escape characters to bash (D:\\SlideMage\\SlideMage.exe became
    D:SlideMageSlideMage.exe), so a Windows path gets forward slashes, which every Windows shell and program accepts.
    A word with a space or a shell character goes in double quotes, the one quote all three understand (bash's
    single quotes are not quotes to cmd); inside them bash needs \\ " $ ` escaped."""
    if _WINDOWS_PATH.match(arg):
        arg = arg.replace("\\", "/")
    if _SHELL_SAFE.match(arg):
        return arg
    return '"' + re.sub(r'([\\"$`])', r"\\\1", arg) + '"'


def hook_command(host: Host) -> str:
    """Quote the host-supplied argv; core owns source/frozen entry-point dispatch."""
    argv = host.entry_point_command("hook")
    return " ".join(map(_windows_word, argv)) if sys.platform == "win32" else shlex.join(argv)


def mcp_config(url: str) -> dict:
    return {"mcpServers": {SERVER_NAME: {
        "type": "http", "url": url, "headers": {"Authorization": f"Bearer ${{{TOKEN_ENV}}}"}}}}


def settings(hook: str) -> dict:
    """Extra settings for this session only: the protected-region hook, and the pre-approved tools allowed
    without asking (add_slide asks, like any tool that changes files)."""
    return {
        "hooks": {"PreToolUse": [{"matcher": HOOK_MATCHER, "hooks": [{"type": "command", "command": hook}]}],
                  "PostToolUse": [{"matcher": HOOK_MATCHER, "hooks": [{"type": "command", "command": hook}]}],
                  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": hook}]}]},
        "permissions": {"allow": [f"mcp__{SERVER_NAME}__{t.spec.name}" for t in CLAUDE_CODE_PRE_APPROVED]}}


def _require_host(host: Host | None) -> Host:
    if host is None:
        raise RuntimeError("Claude Code needs a host entry point (or an explicit hook command)")
    return host


def build_command(claude: Path, url: str, hook: str | None = None, *,
                  host: Host | None = None, model: str = "", effort: str | None = None,
                  session_id: str = "", resume: bool = False) -> list[str]:
    """Start with the saved chat choice, or inherit Claude Code's defaults when no choice is saved. `session_id`
    names the conversation (--session-id), or with `resume` continues it (--resume): --model and --effort apply to
    this session only, so a new default reaches a running conversation this way without becoming Claude Code's own
    default, as /model would make it."""
    command = hook if hook is not None else hook_command(_require_host(host))
    session = (["--resume", session_id] if resume else ["--session-id", session_id]) if session_id else []
    return [str(claude), *session, *(["--model", model] if model else []),
            *(["--effort", effort] if effort else []),
            "--mcp-config", json.dumps(mcp_config(url)),
            "--settings", json.dumps(settings(command)),
            "--append-system-prompt", ORIENTATION]


def has_transcript(session_id: str, base: dict[str, str] | None = None) -> bool:
    """Whether Claude Code saved the conversation `session_id` (CLAUDE_CONFIG_DIR, else ~/.claude, then
    projects/<folder>/<id>.jsonl), so that --resume can continue it: a session where nothing was sent has none."""
    env = os.environ if base is None else base
    home = Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return bool(session_id) and any((home / "projects").glob(f"*/{session_id}.jsonl"))


# Claude Code settings of the user that survive the clean-up of `environment`: the user's own login (a subscription
# token from `claude setup-token`, an API key, Bedrock, Vertex or Foundry) and plain tuning. Everything else named
# CLAUDE_CODE_* is dropped: the session markers of a Claude Code that started SlideMage.
KEEP_CLAUDE_CODE = ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                    "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_SKIP_BEDROCK_AUTH", "CLAUDE_CODE_SKIP_VERTEX_AUTH",
                    "CLAUDE_CODE_SKIP_FOUNDRY_AUTH", "CLAUDE_CODE_MAX_OUTPUT_TOKENS", "CLAUDE_CODE_GIT_BASH_PATH",
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")
DROP = ("CLAUDECODE", "CLAUDE_AGENT_SDK_VERSION", "CLAUDE_PID", "CLAUDE_EFFORT")


# How long Claude Code waits for one tool call of this server, in ms. Its default ends a call after about a
# minute, which is far shorter than refresh_deck_previews (one long compile, up to DECK_TIMEOUT_S = 1 h): the
# agent saw "timed out" while the rerender went on and retried it. The user's own setting wins.
MCP_TOOL_TIMEOUT_ENV, MCP_TOOL_TIMEOUT_MS = "MCP_TOOL_TIMEOUT", "3660000"


def _inherited(name: str) -> bool:
    if name in KEEP_CLAUDE_CODE:
        return True
    return not (name in DROP or name.startswith("CLAUDE_CODE_"))


def clean_environment(claude: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """The app's environment as the user set it, without the markers of a Claude Code session SlideMage was
    started from, and with `claude`'s own folder on PATH (an npm install runs through `node` found there)."""
    env = {name: value for name, value in (os.environ if base is None else base).items() if _inherited(name)}
    env["PATH"] = os.pathsep.join([str(claude.parent), env.get("PATH", "")]) if env.get("PATH") else str(claude.parent)
    env.setdefault(MCP_TOOL_TIMEOUT_ENV, MCP_TOOL_TIMEOUT_MS)
    return env


# The hook finds the project through SlideMage, which reads SLIDEMAGE_PROJECT from v10 on and SLIDEMASTER_PROJECT
# before; both are set, so the plugin works with either, and v10 says nothing about the old name when the new one is set.
PROJECT_ENVS = ("SLIDEMAGE_PROJECT", "SLIDEMASTER_PROJECT")


def environment(token: str, project: Path, claude: Path, base: dict[str, str] | None = None,
                focus_file: Path | None = None) -> dict[str, str]:
    """The terminal's environment: the user's own login, colour, the token and the hook's project/focus.

    The host owns entry-point dispatch. Preserve its inherited PYTHONPATH without guessing a source tree.
    """
    env = clean_environment(claude, base)
    env.update({"TERM": "xterm-256color", "COLORTERM": "truecolor", TOKEN_ENV: token,
                **{name: str(project) for name in PROJECT_ENVS}})
    if focus_file is not None:
        env[FOCUS_ENV] = str(focus_file)
    return env

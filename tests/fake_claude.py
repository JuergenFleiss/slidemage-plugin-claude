# SPDX-FileCopyrightText: 2026 Stefan Palan, Jürgen Fleiß
# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for the `claude` program, for the tests of the Claude Code view: a script that logs what it
was started with (argv, cwd, selected environment) to $FAKE_CLAUDE_LOG, prints a banner, echoes what is typed
(raw terminal) and ends at "/exit". It never talks to a model or the network."""
from __future__ import annotations

import io
import stat
import sys
import zipfile
from pathlib import Path

SCRIPT = '''#!{python}
import json, os, sys
log = os.environ.get("FAKE_CLAUDE_LOG")
if log:
    with open(log, "w") as f:
        json.dump({{"argv": sys.argv[1:], "cwd": os.getcwd(), "token": os.environ.get("SLIDEMAGE_MCP_TOKEN"),
                   "term": os.environ.get("TERM"), "project": os.environ.get("SLIDEMAGE_PROJECT")}}, f)
sys.stdout.write("Fake Claude Code\\r\\n> ")
sys.stdout.flush()
import tty
tty.setraw(0)
typed = ""
while True:
    data = os.read(0, 1024).decode("utf-8", "replace")
    if not data:
        break
    for ch in data:
        if ch in "\\r\\n":
            if typed.strip() == "/exit":
                sys.stdout.write("\\r\\nbye\\r\\n"); sys.stdout.flush(); sys.exit(3)
            sys.stdout.write("\\r\\necho: " + typed + "\\r\\n> "); typed = ""
        else:
            typed += ch; sys.stdout.write(ch)
    sys.stdout.flush()
'''


def make_fake_claude(folder: Path) -> Path:
    script = SCRIPT.format(python=sys.executable)
    if sys.platform == "win32":
        return _windows_exe(folder / "claude.exe", script)
    path = folder / "claude"
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _windows_exe(path: Path, script: str) -> Path:
    """Windows runs no shebang script, so the fake is a claude.exe the way pip makes a console script: the
    distlib launcher, then the line naming the Python to run, then a zip holding the script as __main__.py.
    The launcher hands the arguments over unchanged (a .cmd wrapper would let cmd.exe reinterpret the JSON
    of --mcp-config). The terminal part needs a POSIX terminal, and the tests of it are POSIX-only."""
    try:
        from pip._vendor import distlib
    except ImportError:
        import pytest
        pytest.skip("the fake claude.exe needs pip's script launcher (pip._vendor.distlib)")
    launcher = (Path(distlib.__file__).parent / "t64.exe").read_bytes()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("__main__.py", script)
    path.write_bytes(launcher + f'#!"{sys.executable}"\r\n'.encode() + archive.getvalue())
    return path

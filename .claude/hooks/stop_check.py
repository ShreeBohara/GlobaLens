#!/usr/bin/env python3
"""Stop hook: a session may not finish while `mise run check` fails.

Each time Claude Code is about to end a turn, this hook runs `mise run check` (lint, types and
unit tests) in the project:

  - the check passes: the turn ends, and the count of blocks is cleared;
  - the check fails: the hook blocks the stop and hands Claude the end of the check's output;
  - the check has already failed MAX_BLOCKS (8) times in a row in this session: the hook gives
    up, lets the turn end, and tells the user that the work is not verified.

So the hook is a first check, not a gate: the required CI check (`ci-ok`) is the gate that
cannot be passed (master plan section 9, Appendix D).

Claude Code has a cap of its own: it overrides a Stop hook that has blocked eight times in a
row with no tool call in between. That count restarts whenever Claude calls a tool, so a
session that keeps trying and failing would never be released by it. This hook therefore keeps
its own count, per session, of failing checks in a row.

Standard library only, and it runs on the system `python3` (3.9 or later).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, cast

MAX_BLOCKS = 8
CHECK_COMMAND = ["mise", "run", "check"]
CHECK_TIMEOUT_SECONDS = 840  # under the hook's own timeout in .claude/settings.json (900 s)
TAIL_LINES = 60
TAIL_CHARS = 6000
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def state_file(session_id: str) -> str:
    """Where this session's count of blocks in a row is kept (outside the repository)."""
    root = os.environ.get("GLOBALENS_HOOK_STATE_DIR") or os.path.join(
        tempfile.gettempdir(), "globalens-stop-hook"
    )
    os.makedirs(root, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "unknown"
    return os.path.join(root, f"{safe}.blocks")


def read_blocks(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            return max(0, int(handle.read().strip() or "0"))
    except (OSError, ValueError):
        return 0


def write_blocks(path: str, blocks: int) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(str(blocks))


def clear_blocks(path: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(path)


def run_check(project_dir: str) -> tuple[bool, str]:
    """Run the check. Return whether it passed and the end of its output."""
    env = dict(os.environ)
    # The project's own mise.toml is trusted for this run: the hook itself comes from the same
    # repository, and Claude Code only runs it in a folder the user has trusted.
    trusted = [project_dir] + [p for p in env.get("MISE_TRUSTED_CONFIG_PATHS", "").split(":") if p]
    env["MISE_TRUSTED_CONFIG_PATHS"] = ":".join(trusted)
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"
    try:
        result = subprocess.run(
            CHECK_COMMAND,
            cwd=project_dir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return (
            False,
            "`mise` is not on PATH, so the check could not run. Install mise (mise.jdx.dev).",
        )
    except subprocess.TimeoutExpired:
        return False, f"`mise run check` did not finish within {CHECK_TIMEOUT_SECONDS} seconds."
    output = ANSI.sub("", result.stdout or "")
    tail = "\n".join(output.splitlines()[-TAIL_LINES:])[-TAIL_CHARS:]
    return result.returncode == 0, f"exit code {result.returncode}\n{tail}"


def main() -> int:
    try:
        payload: Any = json.load(sys.stdin)
    except ValueError:
        payload = {}
    data = cast("dict[str, Any]", payload) if isinstance(payload, dict) else {}
    session_id = str(data.get("session_id") or "unknown")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or str(data.get("cwd") or os.getcwd())
    path = state_file(session_id)

    passed, detail = run_check(project_dir)
    if passed:
        clear_blocks(path)
        return 0

    blocks = read_blocks(path)
    if blocks >= MAX_BLOCKS:
        clear_blocks(path)
        message = (
            f"Stop hook: `mise run check` still fails after {MAX_BLOCKS} blocks in a row, so the "
            "hook has stopped blocking. This work is NOT verified. The required CI check (ci-ok) "
            "is the gate."
        )
        print(json.dumps({"systemMessage": message}))
        return 0

    blocks += 1
    write_blocks(path, blocks)
    reason = (
        f"`mise run check` failed, so this turn is not done (block {blocks} of {MAX_BLOCKS} in a "
        "row; after that the hook lets the session stop and CI stays the gate). Fix what fails "
        "and finish again. If you cannot fix it, say plainly that the check is failing and why; "
        "do not report the work as done.\n\n"
        f"{detail}"
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

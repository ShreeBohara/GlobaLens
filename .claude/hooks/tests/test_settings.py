"""The committed settings file is valid and points at hook scripts that exist."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CLAUDE_DIR = Path(__file__).resolve().parents[2]
SETTINGS: dict[str, Any] = json.loads((CLAUDE_DIR / "settings.json").read_text())


def hook_commands(event: str) -> list[str]:
    return [hook["command"] for group in SETTINGS["hooks"][event] for hook in group["hooks"]]


def test_each_hook_command_runs_a_script_that_exists() -> None:
    commands = hook_commands("PreToolUse") + hook_commands("Stop")
    assert len(commands) == 2
    for command in commands:
        match = re.fullmatch(
            r'/usr/bin/python3 "\$CLAUDE_PROJECT_DIR/\.claude/(hooks/\w+\.py)"', command
        )
        assert match, command
        assert (CLAUDE_DIR / match.group(1)).is_file()


def test_the_pretooluse_hook_watches_bash() -> None:
    (group,) = SETTINGS["hooks"]["PreToolUse"]
    assert re.search(group["matcher"], "Bash")
    assert re.search(group["matcher"], "mcp__terminal__run_in_terminal")
    assert not re.search(group["matcher"], "Read")


def test_deny_rules_cover_the_four_kinds_of_command() -> None:
    deny: list[str] = SETTINGS["permissions"]["deny"]
    for rule in (
        "Bash(tofu apply *)",
        "Bash(tofu destroy *)",
        "Bash(wrangler deploy *)",
        "Bash(ssh *)",
    ):
        assert rule in deny

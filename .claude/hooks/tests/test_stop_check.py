"""The Stop hook blocks while the check fails, passes when it is clean, and gives up after 8.

A stand-in `mise` is put first on PATH, so the hook's real code path runs without running the
repository's real check.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "stop_check.py"

FAKE_MISE = """#!/bin/sh
echo "$@" > "$FAKE_MISE_DIR/args"
pwd > "$FAKE_MISE_DIR/cwd"
echo "$MISE_TRUSTED_CONFIG_PATHS" > "$FAKE_MISE_DIR/trusted"
echo "fake check output"
exit "$(cat "$FAKE_MISE_DIR/exit_code")"
"""


class Harness:
    """A project folder, a stand-in `mise`, and a place for the hook's state."""

    def __init__(self, root: Path) -> None:
        self.bin = root / "bin"
        self.project = root / "project"
        self.state = root / "state"
        self.fake = root / "fake"
        self.empty = root / "empty"
        for folder in (self.bin, self.project, self.fake, self.empty):
            folder.mkdir()
        mise = self.bin / "mise"
        mise.write_text(FAKE_MISE)
        mise.chmod(0o755)
        self.set_check(passes=True)

    def set_check(self, passes: bool) -> None:
        (self.fake / "exit_code").write_text("0" if passes else "1")

    def stop(self, session_id: str = "session-a", path: str | None = None) -> dict[str, object]:
        """Fire the Stop hook once. Return its JSON output, or {} if it printed nothing."""
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin" if path is None else path,
            "CLAUDE_PROJECT_DIR": str(self.project),
            "GLOBALENS_HOOK_STATE_DIR": str(self.state),
            "FAKE_MISE_DIR": str(self.fake),
        }
        payload = {"hook_event_name": "Stop", "session_id": session_id, "stop_hook_active": False}
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        output: dict[str, object] = json.loads(result.stdout) if result.stdout.strip() else {}
        return output


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def test_passes_on_a_clean_check(harness: Harness) -> None:
    assert harness.stop() == {}
    assert (harness.fake / "args").read_text().strip() == "run check"
    assert os.path.samefile((harness.fake / "cwd").read_text().strip(), harness.project)
    assert str(harness.project) in (harness.fake / "trusted").read_text()


def test_blocks_on_a_failing_check(harness: Harness) -> None:
    harness.set_check(passes=False)
    output = harness.stop()
    assert output["decision"] == "block"
    reason = str(output["reason"])
    assert "block 1 of 8" in reason
    assert "exit code 1" in reason
    assert "fake check output" in reason


def test_gives_up_after_eight_blocks_in_a_row(harness: Harness) -> None:
    harness.set_check(passes=False)
    for number in range(1, 9):
        output = harness.stop()
        assert output["decision"] == "block"
        assert f"block {number} of 8" in str(output["reason"])
    ninth = harness.stop()
    assert "decision" not in ninth
    assert "NOT verified" in str(ninth["systemMessage"])
    # Giving up clears the count, so the next failing stop is block 1 again.
    assert "block 1 of 8" in str(harness.stop()["reason"])


def test_a_passing_check_resets_the_count(harness: Harness) -> None:
    harness.set_check(passes=False)
    harness.stop()
    harness.stop()
    harness.set_check(passes=True)
    assert harness.stop() == {}
    harness.set_check(passes=False)
    assert "block 1 of 8" in str(harness.stop()["reason"])


def test_sessions_are_counted_apart(harness: Harness) -> None:
    harness.set_check(passes=False)
    harness.stop("session-a")
    harness.stop("session-a")
    assert "block 1 of 8" in str(harness.stop("session-b")["reason"])
    assert "block 3 of 8" in str(harness.stop("session-a")["reason"])


def test_blocks_when_mise_is_missing(harness: Harness) -> None:
    # An empty folder as PATH: a system folder such as /usr/bin may hold a real mise.
    output = harness.stop(path=str(harness.empty))
    assert output["decision"] == "block"
    assert "`mise` is not on PATH" in str(output["reason"])

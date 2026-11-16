"""The PreToolUse hook refuses production-changing commands and lets ordinary ones through."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "deny_prod.py"


def run_hook(tool_name: str, tool_input: dict[str, object]) -> str | None:
    """Run the hook as Claude Code does. Return the refusal reason, or None if it allowed."""
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    reason = output["permissionDecisionReason"]
    assert isinstance(reason, str) and reason
    return reason


def bash(command: str) -> str | None:
    return run_hook("Bash", {"command": command, "description": "test"})


DENIED = [
    # tofu apply and destroy, in the forms a plain deny rule misses
    "tofu apply",
    "tofu apply -auto-approve",
    "tofu destroy",
    "tofu -chdir=infra/live/storage apply",
    "tofu -chdir=infra/live/node-paid destroy -auto-approve",
    "terraform apply",
    "/opt/homebrew/bin/tofu apply",
    "cd infra/live/edge && tofu apply",
    "tofu plan -out=tfplan; tofu apply tfplan",
    "TF_VAR_x=1 tofu apply",
    "mise exec -- tofu apply",
    "timeout 600 tofu apply",
    "bash -c 'tofu apply -auto-approve'",
    'sh -lc "cd infra/live/storage && tofu destroy"',
    'echo "$(tofu apply)"',
    "echo `tofu destroy`",
    "bash <<'EOF'\ntofu apply\nEOF",
    "cat <<EOF | sh\ntofu destroy\nEOF",
    "eval 'tofu apply'",
    "find infra -name '*.tf' -exec tofu apply {} \\;",
    "true || tofu apply",
    # deploy commands
    "wrangler deploy",
    "npx wrangler deploy --env production",
    "pnpm exec wrangler versions upload",
    "wrangler versions deploy",
    "wrangler pages deploy out",
    "wrangler rollback",
    "docker push ghcr.io/example/worker:latest",
    "docker image push ghcr.io/example/worker:latest",
    "docker buildx build --push -t ghcr.io/example/worker .",
    "docker compose push",
    "DOCKER_HOST=ssh://deploy@node docker compose up -d",
    "docker -H ssh://deploy@node ps",
    "docker --context tcp://10.0.0.5:2376 compose up -d",
    "pnpm run deploy",
    "npm run deploy:web",
    "mise run tofu:apply",
    "mise run deploy",
    "turbo run deploy",
    "make deploy",
    # SSH to a node
    "ssh deploy@node.example.com",
    "ssh -i key deploy@10.0.0.5 'docker compose ps'",
    "/usr/bin/ssh node",
    "scp deploy/prod.lock deploy@node:/etc/globalens/",
    "sftp deploy@node",
    "mosh deploy@node",
    "sudo -u deploy ssh node",
    "tailscale ssh node-paid",
    "rsync -az deploy/ deploy@node:/srv/globalens/",
    "rsync -e ssh out/ node:/var/www/",
    "git status && ssh node uptime",
]

ALLOWED = [
    "tofu plan",
    "tofu -chdir=infra/live/storage plan -input=false -lock=false",
    "tofu plan -destroy",
    "tofu init -backend=false",
    "tofu fmt -check -recursive infra",
    "tofu validate",
    "mise run tofu:plan",
    "mise run check",
    "mise run test",
    "pnpm install --frozen-lockfile",
    "pnpm deploy --filter @globalens/web out",  # pnpm's own packaging command, local only
    "uv sync --locked",
    "git status",
    "git push origin claude/some-branch",
    'git commit -m "infra: tofu apply now runs only in CI"',
    "git commit -m \"$(cat <<'EOF'\ninfra: plan only\n\ntofu apply and ssh stay in CI.\nEOF\n)\"",
    "cat <<'EOF' > docs/note.md\nNever run tofu apply or ssh to a node from a session.\nEOF",
    'grep -rn "tofu apply" docs',
    "grep -rn ssh docs",
    "ps aux | grep ssh",
    "ls ~/.ssh",
    "ssh-keygen -t ed25519 -f key -N ''",
    "GIT_SSH_COMMAND='ssh -i key' git fetch",
    "docker build -t worker .",
    "docker compose up -d",
    "docker compose -f deploy/compose/node-paid/compose.yaml config",
    "wrangler dev",
    "wrangler --version",
    "rsync -a apps/web/out/ /tmp/preview/",
    "echo 'ssh node'",
    "gh pr create --fill",
]


@pytest.mark.parametrize("command", DENIED)
def test_refuses(command: str) -> None:
    reason = bash(command)
    assert reason is not None, f"allowed: {command}"
    assert "only through CI" in reason


@pytest.mark.parametrize("command", ALLOWED)
def test_allows(command: str) -> None:
    assert bash(command) is None


def test_checks_terminal_tools_from_mcp_servers() -> None:
    assert run_hook("mcp__terminal__run_in_terminal", {"command": "tofu apply"}) is not None
    assert run_hook("mcp__x__start_process", {"command": "ssh node", "timeout_ms": 1}) is not None
    assert run_hook("mcp__terminal__run_in_terminal", {"command": "mise run check"}) is None


def test_ignores_input_it_cannot_read() -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert result.stdout == ""

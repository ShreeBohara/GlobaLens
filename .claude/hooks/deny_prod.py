#!/usr/bin/env python3
"""PreToolUse hook: refuse commands that change production from a Claude Code session.

Production is reached only through CI (master plan section 9, Appendix D). This hook refuses,
in every permission mode:

  1. `tofu apply` and `tofu destroy` (and the same with `terraform`);
  2. deploy commands: `wrangler` deploys, `docker push`, a Docker client pointed at a remote
     host, and task-runner tasks named deploy, apply or destroy;
  3. SSH to a node: `ssh`, `scp`, `sftp`, `mosh`, `autossh`, `sshpass`, `tailscale ssh`, and
     `rsync` to a remote host. No node has an address yet, so every direct SSH command is
     refused. Git's own SSH transport is not affected.

It reads the hook input (JSON) on stdin and, to refuse, prints a PreToolUse `deny` decision.
It errs toward refusing. It is a guard against mistakes, not a security boundary: a session
holds no production credentials, and that is what keeps production safe.

Standard library only, and it runs on the system `python3` (3.9 or later), because a hook
cannot rely on the project's toolchain being installed.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, cast

SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}

# A command that runs its arguments as another command. After one of these, any later word in
# the same simple command may be the real command.
WRAPPERS = {
    "sudo", "doas", "env", "command", "builtin", "exec", "nohup", "time", "nice", "ionice",
    "timeout", "gtimeout", "stdbuf", "xargs", "noglob", "nocorrect", "caffeinate", "setsid",
    "watch", "unbuffer", "npx", "pnpx", "bunx", "uvx", "mise", "pnpm", "npm", "yarn", "bun",
    "uv", "direnv", "devbox", "op", "dotenvx", "docker", "podman",
}  # fmt: skip

SSH_COMMANDS = {"ssh", "scp", "sftp", "mosh", "autossh", "sshpass"}
TOFU_COMMANDS = {"tofu", "terraform"}
TOFU_DENIED = {"apply", "destroy"}
WRANGLER_DENIED_1 = {"deploy", "publish", "rollback", "delete"}
WRANGLER_DENIED_2 = {
    ("versions", "deploy"),
    ("versions", "upload"),
    ("pages", "deploy"),
    ("pages", "publish"),
    ("triggers", "deploy"),
}
SCRIPT_RUNNERS = {"npm", "pnpm", "yarn", "bun"}
DENIED_TASK = re.compile(r"(?:^|[:_-])(?:deploy|apply|destroy)(?:$|[:_-])")
REMOTE_DOCKER = re.compile(r"^(?:ssh|tcp)://", re.IGNORECASE)
REMOTE_PATH = re.compile(r"^(?:[\w.-]+@)?[\w.-]+:(?!\\)")
HEREDOC = re.compile(r"(?<!<)<<-?\s*(?:'(\w+)'|\"(\w+)\"|\\?(\w+))")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DASH_C = re.compile(r"^-[A-Za-z]*c$")
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}

WHY = (
    "Production is reached only through CI: open a pull request and the owner merges it "
    "(CLAUDE.md, Rules). Refused by .claude/hooks/deny_prod.py."
)


def base(word: str) -> str:
    """The command name a word would run: its last path component, lower-cased."""
    return os.path.basename(word.rstrip("/")).lower()


def substitutions(text: str) -> list[str]:
    """The command text inside every `$(...)` and backtick pair in a double-quoted string."""
    found: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("$(", i):
            depth = 1
            j = i + 2
            while j < len(text) and depth > 0:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            found.append(text[i + 2 : j - 1] if depth == 0 else text[i + 2 :])
            i = j
        elif text[i] == "`":
            j = text.find("`", i + 1)
            j = len(text) if j < 0 else j
            found.append(text[i + 1 : j])
            i = j + 1
        else:
            i += 1
    return found


def lex(text: str) -> tuple[list[list[str]], list[str]]:
    """Split shell text into simple commands (lists of words) and nested command texts.

    A small lexer, not a shell parser: it understands quotes, backslashes, the operators that
    end a command, and command substitution. Anything it gets wrong makes the hook refuse more,
    not less, because the rules below look at every word of a command.
    """
    commands: list[list[str]] = []
    nested: list[str] = []
    words: list[str] = []
    current: list[str] = []
    in_word = False

    def end_word() -> None:
        nonlocal current, in_word
        if in_word:
            words.append("".join(current))
        current = []
        in_word = False

    def end_command() -> None:
        nonlocal words
        end_word()
        if words:
            commands.append(words)
        words = []

    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char == "\\" and i + 1 < n:
            if text[i + 1] != "\n":
                current.append(text[i + 1])
                in_word = True
            i += 2
        elif char == "'":
            j = text.find("'", i + 1)
            j = n if j < 0 else j
            current.append(text[i + 1 : j])
            in_word = True
            i = j + 1
        elif char == '"':
            j = i + 1
            quoted: list[str] = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    quoted.append(text[j + 1])
                    j += 2
                else:
                    quoted.append(text[j])
                    j += 1
            content = "".join(quoted)
            nested.extend(substitutions(content))
            current.append(content)
            in_word = True
            i = j + 1
        elif char in " \t":
            end_word()
            i += 1
        elif char in "\n;|&(){}`":
            end_command()
            i += 1
        elif char == "$" and text.startswith("$(", i):
            end_command()
            i += 2
        elif char in "<>":
            end_word()
            i += 1
        else:
            current.append(char)
            in_word = True
            i += 1
    end_command()
    return commands, nested


def strip_heredocs(text: str) -> str:
    """Drop here-document bodies, unless the line that opens one also names a shell.

    `cat <<EOF > notes.md` carries data, so its body is not a command. `bash <<EOF` and
    `cat <<EOF | sh` run their body, so it stays and is checked line by line.
    """
    kept: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        match = HEREDOC.search(line)
        i += 1
        if not match:
            continue
        terminator = match.group(1) or match.group(2) or match.group(3)
        commands, _ = lex(line)
        runs_body = any(
            base(word) in SHELLS or base(word) == "eval" for c in commands for word in c
        )
        while i < len(lines) and lines[i].strip() != terminator:
            if runs_body:
                kept.append(lines[i])
            i += 1
        i += 1  # the terminator line
    return "\n".join(kept)


def after(words: list[str], index: int, count: int) -> list[str]:
    """Up to `count` words after `index` that are not options."""
    return [w.lower() for w in words[index + 1 :] if not w.startswith("-")][:count]


def check_command(words: list[str]) -> str | None:
    """Return why this simple command is refused, or None."""
    for word in words:
        if word.startswith("DOCKER_HOST=") and REMOTE_DOCKER.match(word.split("=", 1)[1]):
            return "a Docker client pointed at a remote host deploys to that host"

    start = 0
    while start < len(words) and ASSIGNMENT.match(words[start]):
        start += 1
    words = words[start:]
    if not words:
        return None

    # Rules that hold wherever the word appears in the command.
    for index, word in enumerate(words):
        name = base(word)
        if name in TOFU_COMMANDS:
            sub = after(words, index, 1)
            if sub and sub[0] in TOFU_DENIED:
                return f"`{name} {sub[0]}` changes production infrastructure"
        elif name == "wrangler":
            sub = after(words, index, 2)
            if (sub and sub[0] in WRANGLER_DENIED_1) or tuple(sub) in WRANGLER_DENIED_2:
                return f"`wrangler {' '.join(sub)}` deploys to Cloudflare"
        elif name in ("docker", "podman"):
            rest = words[index + 1 :]
            if "push" in rest or "--push" in rest:
                return f"`{name} push` publishes an image; images are built and pushed by CI"
            for position, option in enumerate(rest):
                value = ""
                if option in ("-H", "--host", "--context") and position + 1 < len(rest):
                    value = rest[position + 1]
                elif option.startswith(("--host=", "-H=")):
                    value = option.split("=", 1)[1]
                if REMOTE_DOCKER.match(value):
                    return "a Docker client pointed at a remote host deploys to that host"

    # Rules for the command being run: the first word, or any later word after a wrapper.
    first = base(words[0])
    candidates = range(len(words)) if first in WRAPPERS else range(1)
    for index in candidates:
        name = base(words[index])
        if name in SSH_COMMANDS:
            return f"`{name}` opens a session on another machine; no session may SSH to a node"
        if name == "tailscale" and after(words, index, 1) == ["ssh"]:
            return "`tailscale ssh` opens a session on another machine"
        if name == "rsync":
            rest = words[index + 1 :]
            remote = any(REMOTE_PATH.match(w) or w.startswith("rsync://") for w in rest)
            if remote or any(w in ("-e", "--rsh") or w.startswith("--rsh=") for w in rest):
                return "`rsync` to a remote host copies files onto another machine"
        task = ""
        sub = after(words, index, 2)
        if (name in SCRIPT_RUNNERS and sub[:1] == ["run"]) or (
            name == "mise" and sub[:1] in (["run"], ["r"])
        ):
            task = sub[1] if len(sub) > 1 else ""
        elif name == "turbo" and sub:
            task = sub[1] if sub[0] == "run" and len(sub) > 1 else sub[0]
        elif name in ("make", "just") and sub:
            task = sub[0]
        if task and DENIED_TASK.search(task):
            return f"`{name} … {task}` is a deploy, apply or destroy task"
    return None


def find_violation(command: str, depth: int = 0) -> str | None:
    """Return why this command text is refused, or None if it may run."""
    if depth > 8:
        return "the command nests too deeply to check"
    commands, nested = lex(strip_heredocs(command))
    for words in commands:
        # `find … -exec cmd` starts a command of its own.
        parts: list[list[str]] = [[]]
        for word in words:
            if word in FIND_EXEC:
                parts.append([])
            else:
                parts[-1].append(word)
        for part in parts:
            reason = check_command(part)
            if reason:
                return reason
            for index, word in enumerate(part):
                name = base(word)
                if name in SHELLS or name == "su":
                    for position in range(index + 1, len(part) - 1):
                        if DASH_C.match(part[position]):
                            nested.append(part[position + 1])
                            break
                elif name == "eval":
                    nested.append(" ".join(part[index + 1 :]))
    for text in nested:
        reason = find_violation(text, depth + 1)
        if reason:
            return reason
    return None


FALLBACK = re.compile(
    r"\b(?:tofu|terraform)\b[^\n;&|]*\b(?:apply|destroy)\b"
    r"|(?:^|[\s;&|(`'\"/])(?:ssh|scp|sftp|mosh)\s"
    r"|\bwrangler\b[^\n;&|]*\b(?:deploy|publish|rollback)\b"
    r"|\b(?:docker|podman)\b[^\n;&|]*\bpush\b"
)


def strings(value: Any) -> list[str]:
    """Every string inside a JSON value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in cast("dict[str, Any]", value).values() for s in strings(item)]
    if isinstance(value, list):
        return [s for item in cast("list[Any]", value) for s in strings(item)]
    return []


def decide(payload: dict[str, Any]) -> str | None:
    """Return the refusal reason for a PreToolUse payload, or None to let the call through."""
    tool_input: Any = payload.get("tool_input")
    if payload.get("tool_name") == "Bash" and isinstance(tool_input, dict):
        texts = strings(cast("dict[str, Any]", tool_input).get("command"))
    else:
        # A terminal or process tool from an MCP server: check every string it was given.
        texts = strings(tool_input)
    for text in texts:
        try:
            reason = find_violation(text)
        except Exception:  # a bug in the lexer must not let a command through unchecked
            reason = (
                "the command matches a production-change pattern" if FALLBACK.search(text) else None
            )
        if reason:
            return reason
    return None


def main() -> int:
    try:
        payload: Any = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    reason = decide(cast("dict[str, Any]", payload))
    if reason:
        decision = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Refused: {reason}. {WHY}",
            }
        }
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The repository's own rules for its GitHub Actions workflows (P1 task 5, ADR-0011).

zizmor audits the workflows for known weaknesses. These tests hold the rules that are this
repository's choices, so that a later edit cannot quietly drop one:

- `permissions: {}` at the top of every workflow, and each job names the least it needs;
- every action pinned by a full commit SHA with a version comment, one pin per action;
- harden-runner first in every job that runs an action, blocking all egress but an allow-list;
- no `pull_request_target` or `workflow_run` trigger, and no checkout that keeps its token;
- `ci-ok` needs every other job in `ci.yml` and runs even when one of them fails;
- the Claude review skips cleanly when its token is missing.

They read files only, so they run under `mise run check`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
EXPECTED_WORKFLOWS = {"ci.yml", "claude-review.yml", "codeql.yml", "release-please.yml"}

# GitHub's permission scopes for GITHUB_TOKEN, and the only write access any job may hold.
SCOPES = {
    "actions",
    "attestations",
    "checks",
    "contents",
    "deployments",
    "discussions",
    "id-token",
    "issues",
    "models",
    "packages",
    "pages",
    "pull-requests",
    "repository-projects",
    "security-events",
    "statuses",
}
WRITE_ALLOWED = {
    ("codeql.yml", "analyze"): {"security-events"},
    ("release-please.yml", "release-please"): {"contents", "issues", "pull-requests"},
    ("claude-review.yml", "review"): {"pull-requests"},
}

RUNNERS = {"ubuntu-24.04", "ubuntu-24.04-arm"}
SHA_PIN = re.compile(r"^(?P<action>[\w.-]+/[\w.-]+)(?:/[\w./-]+)?@(?P<sha>[0-9a-f]{40})$")
VERSION_COMMENT = re.compile(r"^# (?P<version>v\d+\.\d+\.\d+)$")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<ref>[^\s#]+)\s*(?P<comment>#.*)?$")
ENDPOINT = re.compile(r"^(?:\*\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+:\d{1,5}$")


@dataclass(frozen=True)
class Workflow:
    path: Path
    text: str
    doc: dict[str, object]

    @property
    def name(self) -> str:
        return self.path.name

    def triggers(self) -> dict[str, object]:
        # PyYAML follows YAML 1.1, where a bare `on` key is the boolean True. GitHub reads it as
        # the string "on".
        doc = cast("dict[object, object]", self.doc)
        value = doc.get("on", doc.get(True))
        if isinstance(value, str):
            return {value: None}
        if isinstance(value, list):
            return {str(item): None for item in cast("list[object]", value)}
        return mapping(value, f"{self.name}: on")

    def jobs(self) -> dict[str, dict[str, object]]:
        jobs = mapping(self.doc.get("jobs"), f"{self.name}: jobs")
        return {name: mapping(job, f"{self.name}: jobs.{name}") for name, job in jobs.items()}


def mapping(value: object, where: str) -> dict[str, object]:
    assert isinstance(value, dict), f"{where}: expected a mapping, found {value!r}"
    return cast("dict[str, object]", value)


def sequence(value: object, where: str) -> list[object]:
    assert isinstance(value, list), f"{where}: expected a list, found {value!r}"
    return cast("list[object]", value)


def steps(job: dict[str, object], where: str) -> list[dict[str, object]]:
    return [
        mapping(step, f"{where}.steps[{index}]")
        for index, step in enumerate(sequence(job.get("steps", []), f"{where}.steps"))
    ]


def load(path: Path) -> Workflow:
    text = path.read_text(encoding="utf-8")
    return Workflow(path, text, mapping(yaml.safe_load(text), path.name))


def workflow_paths() -> list[Path]:
    return sorted([*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")])


def workflows() -> list[Workflow]:
    return [load(path) for path in workflow_paths()]


def by_name(name: str) -> Workflow:
    return load(WORKFLOW_DIR / name)


def expression(value: object) -> str:
    """An `if:` value without the optional `${{ }}` wrapper, whitespace collapsed."""
    text = str(value).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    return " ".join(text.split())


def uses_steps(workflow: Workflow) -> list[tuple[str, dict[str, object]]]:
    found: list[tuple[str, dict[str, object]]] = []
    for job_name, job in workflow.jobs().items():
        where = f"{workflow.name}: jobs.{job_name}"
        found.extend((job_name, step) for step in steps(job, where) if "uses" in step)
    return found


def endpoints(step: dict[str, object]) -> list[str]:
    options = mapping(step.get("with", {}), "harden-runner with")
    return str(options.get("allowed-endpoints") or "").split()


WORKFLOW_PARAMS = [pytest.param(path, id=path.name) for path in workflow_paths()]


def test_the_expected_workflows_exist() -> None:
    assert {path.name for path in workflow_paths()} == EXPECTED_WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_top_level_permissions_are_empty(path: Path) -> None:
    workflow = load(path)
    assert workflow.doc.get("permissions") == {}, f"{workflow.name}: needs `permissions: {{}}`"


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_every_job_names_its_own_permissions(path: Path) -> None:
    workflow = load(path)
    for job_name, job in workflow.jobs().items():
        where = f"{workflow.name}: jobs.{job_name}.permissions"
        assert "permissions" in job, f"{where} is missing"
        granted = mapping(job["permissions"], where)
        assert set(granted) <= SCOPES, f"{where}: unknown scope in {sorted(granted)}"
        assert set(map(str, granted.values())) <= {"read", "write", "none"}, where
        writes = {scope for scope, level in granted.items() if level == "write"}
        allowed = WRITE_ALLOWED.get((workflow.name, job_name), set())
        assert writes <= allowed, f"{where}: write access to {sorted(writes - allowed)}"


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_every_action_is_pinned_by_commit_sha_with_a_version_comment(path: Path) -> None:
    workflow = load(path)
    lines = [line for line in workflow.text.splitlines() if USES_LINE.match(line)]
    assert len(lines) == len(uses_steps(workflow)), f"{workflow.name}: a `uses:` the test missed"
    for line in lines:
        match = USES_LINE.match(line)
        assert match is not None
        ref, comment = match["ref"], (match["comment"] or "").strip()
        assert SHA_PIN.match(ref), f"{workflow.name}: `{ref}` is not pinned by a full commit SHA"
        assert VERSION_COMMENT.match(comment), (
            f"{workflow.name}: `{ref}` needs a `# vX.Y.Z` comment"
        )


def test_each_action_has_one_pin_across_workflows() -> None:
    pins: dict[str, set[str]] = {}
    for workflow in workflows():
        for line in workflow.text.splitlines():
            match = USES_LINE.match(line)
            if match is None:
                continue
            pin = SHA_PIN.match(match["ref"])
            assert pin is not None
            pins.setdefault(pin["action"], set()).add(f"{pin['sha']} {match['comment']}")
    split = {action: sorted(found) for action, found in pins.items() if len(found) > 1}
    assert not split, f"actions pinned at more than one commit: {split}"


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_harden_runner_blocks_egress_first_in_every_job_that_runs_an_action(path: Path) -> None:
    workflow = load(path)
    for job_name, job in workflow.jobs().items():
        where = f"{workflow.name}: jobs.{job_name}"
        job_steps = steps(job, where)
        if not any("uses" in step for step in job_steps):
            continue  # shell steps only, nothing fetched: ci-ok
        first = job_steps[0]
        assert str(first.get("uses", "")).startswith("step-security/harden-runner@"), (
            f"{where}: the first step must be harden-runner"
        )
        options = mapping(first.get("with", {}), f"{where}: harden-runner with")
        assert options.get("egress-policy") == "block", f"{where}: egress-policy must be block"
        # The allow-list is the control. Per-lookup and per-connection records stay on the
        # runner (ADR-0011 says what StepSecurity would otherwise receive).
        assert options.get("disable-telemetry") is True, f"{where}: disable-telemetry: true"
        allowed = endpoints(first)
        assert allowed, f"{where}: an empty allow-list"
        assert len(allowed) == len(set(allowed)), f"{where}: an endpoint is listed twice"
        bad = [entry for entry in allowed if not ENDPOINT.match(entry)]
        assert not bad, f"{where}: not host:port: {bad}"


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_no_trigger_runs_untrusted_code_with_secrets(path: Path) -> None:
    workflow = load(path)
    dangerous = {"pull_request_target", "workflow_run"} & set(workflow.triggers())
    assert not dangerous, f"{workflow.name}: triggered by {sorted(dangerous)}"


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_checkout_never_keeps_its_token(path: Path) -> None:
    workflow = load(path)
    for job_name, step in uses_steps(workflow):
        if str(step["uses"]).startswith("actions/checkout@"):
            options = mapping(step.get("with", {}), f"{workflow.name}: {job_name} checkout")
            assert options.get("persist-credentials") is False, (
                f"{workflow.name}: jobs.{job_name}: checkout needs `persist-credentials: false`"
            )


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_jobs_have_timeouts_and_pinned_runners(path: Path) -> None:
    workflow = load(path)
    for job_name, job in workflow.jobs().items():
        where = f"{workflow.name}: jobs.{job_name}"
        timeout = job.get("timeout-minutes")
        assert isinstance(timeout, int) and 0 < timeout <= 60, f"{where}: timeout-minutes"
        runs_on = str(job.get("runs-on"))
        if runs_on.startswith("${{"):
            strategy = mapping(job.get("strategy"), f"{where}.strategy")
            matrix = mapping(strategy.get("matrix"), f"{where}.strategy.matrix")
            labels = {str(label) for label in sequence(matrix.get("runner"), f"{where} runner")}
            assert runs_on == "${{ matrix.runner }}", f"{where}: runs-on"
        else:
            labels = {runs_on}
        assert labels <= RUNNERS, f"{where}: runners {sorted(labels - RUNNERS)} are not pinned"


def test_ci_runs_on_pull_requests_and_in_the_merge_queue() -> None:
    triggers = set(by_name("ci.yml").triggers())
    assert {"pull_request", "merge_group"} <= triggers


def test_ci_ok_needs_every_other_job_and_always_runs() -> None:
    jobs = by_name("ci.yml").jobs()
    ci_ok = jobs["ci-ok"]
    needs = ci_ok.get("needs")
    needed = {str(needs)} if isinstance(needs, str) else set(map(str, sequence(needs, "needs")))
    assert needed == set(jobs) - {"ci-ok"}, "ci-ok must need every other job in ci.yml"
    assert expression(ci_ok.get("if")) == "always()"
    assert ci_ok.get("permissions") == {}


def test_ci_ok_fails_when_a_needed_job_failed_or_was_cancelled() -> None:
    ci_ok = by_name("ci.yml").jobs()["ci-ok"]
    failing = [
        step
        for step in steps(ci_ok, "ci.yml: jobs.ci-ok")
        if "needs.*.result" in expression(step.get("if", ""))
    ]
    assert len(failing) == 1, "ci-ok needs exactly one step that fails on a bad result"
    condition = expression(failing[0]["if"])
    assert "contains(needs.*.result, 'failure')" in condition
    assert "contains(needs.*.result, 'cancelled')" in condition
    assert str(failing[0].get("run", "")).strip().endswith("exit 1")


def test_ci_affected_run_compares_against_the_event_base() -> None:
    check = by_name("ci.yml").jobs()["check"]
    job_steps = steps(check, "ci.yml: jobs.check")
    checkout = next(s for s in job_steps if str(s.get("uses", "")).startswith("actions/checkout@"))
    assert mapping(checkout.get("with"), "checkout with").get("fetch-depth") == 0
    affected = [s for s in job_steps if "--affected" in str(s.get("run", ""))]
    assert len(affected) == 1
    env = mapping(affected[0].get("env"), "affected step env")
    base = expression(env.get("TURBO_SCM_BASE"))
    assert "github.event.pull_request.base.sha" in base
    assert "github.event.merge_group.base_sha" in base


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.lstrip("v").split("."))


def test_ci_uses_the_devcontainer_mise_and_at_least_mise_toml_minimum() -> None:
    env = mapping(by_name("ci.yml").doc.get("env"), "ci.yml env")
    ci_version = str(env.get("MISE_VERSION"))
    dockerfile = (ROOT / ".devcontainer" / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"^ARG MISE_VERSION=v(?P<version>[\d.]+)$", dockerfile, re.MULTILINE)
    assert match is not None, "the devcontainer no longer pins mise with ARG MISE_VERSION"
    assert ci_version == match["version"], "CI and the devcontainer run different mise versions"
    minimum = str(tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))["min_version"])
    assert version_tuple(ci_version) >= version_tuple(minimum)
    for job_name, step in uses_steps(by_name("ci.yml")):
        if str(step["uses"]).startswith("jdx/mise-action@"):
            options = mapping(step.get("with"), f"ci.yml: {job_name} mise-action with")
            assert expression(options.get("version")) == "env.MISE_VERSION", job_name


def test_claude_review_skips_cleanly_without_its_token() -> None:
    workflow = by_name("claude-review.yml")
    review = workflow.jobs()["review"]
    condition = expression(review.get("if"))
    # Never on a fork's pull request (no secrets there), a draft, or a bot's pull request.
    assert "github.event.pull_request.head.repo.full_name == github.repository" in condition
    assert "github.event.pull_request.draft" in condition
    assert "github.event.pull_request.user.type != 'Bot'" in condition
    env = mapping(review.get("env"), "claude-review.yml: jobs.review.env")
    flag = expression(env.get("HAS_CLAUDE_TOKEN"))
    assert flag == "secrets.CLAUDE_CODE_OAUTH_TOKEN != ''"
    job_steps = steps(review, "claude-review.yml: jobs.review")
    action_steps = [s for s in job_steps if str(s.get("uses", "")).startswith("anthropics/")]
    assert action_steps, "the review step is missing"
    for step in action_steps:
        assert expression(step.get("if")) == "env.HAS_CLAUDE_TOKEN == 'true'"
    notices = [
        s for s in job_steps if expression(s.get("if", "")) == "env.HAS_CLAUDE_TOKEN != 'true'"
    ]
    assert notices and "::notice" in str(notices[0].get("run", "")), "no skip notice"
    # An unattended run carries both caps (master plan, Appendix D, "Usage").
    for step in action_steps:
        claude_args = str(mapping(step.get("with"), "review with").get("claude_args", ""))
        assert re.search(r"--max-turns \d+", claude_args), "the review needs --max-turns"
        assert re.search(r"--max-budget-usd \d+", claude_args), "the review needs --max-budget-usd"


@pytest.mark.parametrize("path", WORKFLOW_PARAMS)
def test_secrets_never_reach_a_shell_script(path: Path) -> None:
    workflow = load(path)
    for job_name, job in workflow.jobs().items():
        for step in steps(job, f"{workflow.name}: jobs.{job_name}"):
            assert "secrets." not in str(step.get("run", "")), f"{workflow.name}: {job_name}"


def test_every_osv_exception_names_one_advisory_with_a_reason_and_an_end_date() -> None:
    path = ROOT / ".github" / "osv-scanner.toml"
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    for entry in sequence(config.get("IgnoredVulns", []), "IgnoredVulns"):
        exception = mapping(entry, "IgnoredVulns entry")
        assert re.fullmatch(r"[A-Z]+-[\w-]+", str(exception.get("id", ""))), exception
        assert len(str(exception.get("reason", ""))) >= 80, f"{exception['id']}: explain why"
        assert isinstance(exception.get("effectiveUntil"), date), f"{exception['id']}: no end date"
        assert "ignoreUntil" not in exception, "OSV-Scanner 2 reads effectiveUntil"
    assert '--config "${GITHUB_WORKSPACE}/.github/osv-scanner.toml"' in by_name("ci.yml").text

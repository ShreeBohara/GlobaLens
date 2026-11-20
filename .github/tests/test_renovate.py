"""The Renovate configuration keeps the repository's dependency cooldown (ADR-0001, ADR-0011).

Renovate itself runs as a GitHub App, so nothing here can run it. These tests check what can
be checked from the files: the config is strict JSON, npm, PyPI and the SHA-pinned actions all
wait the same 7 days as pnpm's `minimumReleaseAge`, the pre-registered spike in `lab/` is never
touched, and each version pin outside a manifest Renovate knows (the PostgreSQL image of the SQL
tests, mise in CI and in the devcontainer, the CI tools) is matched by a custom manager.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "renovate.json"
COOLDOWN = "7 days"
COOLDOWN_MINUTES = 7 * 24 * 60


def config() -> dict[str, object]:
    document: object = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


def rules() -> list[dict[str, object]]:
    found = config().get("packageRules", [])
    assert isinstance(found, list)
    return [cast("dict[str, object]", rule) for rule in cast("list[object]", found)]


def custom_managers() -> list[dict[str, object]]:
    found = config().get("customManagers", [])
    assert isinstance(found, list)
    return [cast("dict[str, object]", manager) for manager in cast("list[object]", found)]


def strings(value: object) -> list[str]:
    assert isinstance(value, list)
    return [str(item) for item in cast("list[object]", value)]


def python_regex(pattern: str) -> re.Pattern[str]:
    """Renovate's patterns are JavaScript regexes: `(?<name>...)` is Python's `(?P<name>...)`."""
    return re.compile(re.sub(r"\(\?<(?=[A-Za-z_])", "(?P<", pattern))


def file_pattern(pattern: str) -> re.Pattern[str]:
    assert pattern.startswith("/") and pattern.endswith("/"), f"use regex file patterns: {pattern}"
    return python_regex(pattern[1:-1])


def matches(path: str) -> list[dict[str, str]]:
    """Every dependency the custom managers extract from one repository file."""
    text = (ROOT / path).read_text(encoding="utf-8")
    found: list[dict[str, str]] = []
    for manager in custom_managers():
        if not any(file_pattern(p).search(path) for p in strings(manager["managerFilePatterns"])):
            continue
        for match_string in strings(manager["matchStrings"]):
            for match in python_regex(match_string).finditer(text):
                groups = {k: v for k, v in match.groupdict().items() if v is not None}
                for key in ("datasource", "depName"):
                    template = manager.get(f"{key}Template")
                    if template is not None:
                        groups.setdefault(key, str(template))
                found.append(groups)
    return found


def test_config_is_strict_json_with_the_schema() -> None:
    assert config()["$schema"] == "https://docs.renovatebot.com/renovate-schema.json"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("matchDatasources", "npm"),
        ("matchDatasources", "pypi"),
        ("matchManagers", "github-actions"),
    ],
)
def test_npm_pypi_and_actions_wait_seven_days(key: str, value: str) -> None:
    assert config()["minimumReleaseAge"] == COOLDOWN
    explicit = [
        rule
        for rule in rules()
        if "minimumReleaseAge" in rule and value in strings(rule.get(key, []))
    ]
    assert explicit, f"no cooldown rule for {key}={value}"
    assert all(rule["minimumReleaseAge"] == COOLDOWN for rule in explicit)


def test_the_cooldown_is_pnpms() -> None:
    workspace: object = yaml.safe_load((ROOT / "pnpm-workspace.yaml").read_text(encoding="utf-8"))
    assert isinstance(workspace, dict)
    assert cast("dict[str, object]", workspace)["minimumReleaseAge"] == COOLDOWN_MINUTES


def test_updates_still_in_their_cooldown_get_no_branch() -> None:
    assert config()["internalChecksFilter"] == "strict"
    behaviour = config().get("minimumReleaseAgeBehaviour", "timestamp-required")
    assert behaviour == "timestamp-required"


def test_the_preregistered_spike_is_never_updated() -> None:
    assert "lab/**" in strings(config()["ignorePaths"])


def test_the_sql_tests_postgres_pin_is_tracked() -> None:
    path = "db/tests/pg/test_0001_ingest.py"
    text = (ROOT / path).read_text(encoding="utf-8")
    pinned = re.search(r'"postgres:(?P<tag>[^"@]+)@(?P<digest>sha256:[0-9a-f]{64})"', text)
    assert pinned is not None
    found = matches(path)
    assert found == [
        {
            "depName": "postgres",
            "currentValue": pinned["tag"],
            "currentDigest": pinned["digest"],
            "datasource": "docker",
        }
    ]


def test_mise_is_tracked_in_ci_and_in_the_devcontainer() -> None:
    ci = [m for m in matches(".github/workflows/ci.yml") if m["depName"] == "jdx/mise"]
    assert len(ci) == 1 and ci[0]["datasource"] == "github-releases"
    container = matches(".devcontainer/Dockerfile")
    assert len(container) == 1 and container[0]["depName"] == "jdx/mise"
    assert container[0]["currentValue"] == f"v{ci[0]['currentValue']}"
    groups = [rule for rule in rules() if "jdx/mise" in strings(rule.get("matchDepNames", []))]
    assert groups and groups[-1].get("groupName"), "CI's and the devcontainer's mise move together"


@pytest.mark.parametrize(
    ("dep_name", "datasource"), [("zizmor", "pypi"), ("google/osv-scanner", "github-releases")]
)
def test_ci_tool_versions_are_tracked(dep_name: str, datasource: str) -> None:
    found = [m for m in matches(".github/workflows/ci.yml") if m["depName"] == dep_name]
    assert len(found) == 1, f"{dep_name}: one annotated *_VERSION line in ci.yml"
    assert found[0]["datasource"] == datasource
    assert re.fullmatch(r"\d+\.\d+\.\d+", found[0]["currentValue"])

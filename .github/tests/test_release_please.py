"""release-please tags each phase as `v3.0.0-pN` (master plan, Appendix D; ADR-0011).

The version is set by `release-as`, one phase at a time, so the release pull request always
proposes the current phase's tag whatever the commit types say. These tests read the files only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "release-please-config.json"
MANIFEST = ROOT / ".github" / "release-please-manifest.json"
WORKFLOW = ROOT / ".github" / "workflows" / "release-please.yml"


def load(path: Path) -> dict[str, object]:
    document: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return cast("dict[str, object]", document)


def test_the_root_package_is_released_as_the_current_phase() -> None:
    config = load(CONFIG)
    packages = config["packages"]
    assert isinstance(packages, dict)
    root = cast("dict[str, object]", packages)["."]
    assert isinstance(root, dict)
    package = cast("dict[str, object]", root)
    assert package["release-type"] == "simple"
    assert re.fullmatch(r"3\.0\.0-p([1-9]|10)", str(package["release-as"]))
    assert package["include-component-in-tag"] is False
    assert re.fullmatch(r"[0-9a-f]{40}", str(config["bootstrap-sha"]))


def test_the_manifest_has_the_root_package_and_the_workflow_names_both_files() -> None:
    assert set(load(MANIFEST)) == {"."}
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "config-file: .github/release-please-config.json" in workflow
    assert "manifest-file: .github/release-please-manifest.json" in workflow

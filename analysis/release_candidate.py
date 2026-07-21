from __future__ import annotations

from pathlib import Path
from typing import Any

from analysis.release_readiness import (
    build_release_readiness_report,
    load_release_manifest,
    validate_release_manifest,
)
from analysis.scientific_scope import load_scientific_scope, validate_scientific_scope


REQUIRED_RELEASE_FILES = (
    "VERSION",
    "CHANGELOG.md",
    "README.md",
    "PROJECT_STATUS.md",
    "ROADMAP.md",
    "docs/V1_RELEASE_CHECKLIST.md",
    "docs/V1_SCIENTIFIC_SCOPE.md",
    "release/v1.0.0.json",
    "release/v1_scientific_scope.json",
    ".github/workflows/ci.yml",
)


def validate_v1_release_candidate(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    missing = [path for path in REQUIRED_RELEASE_FILES if not (root / path).is_file()]
    if missing:
        raise ValueError(f"Release candidate is missing required files: {missing}")

    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if version != "1.0.0":
        raise ValueError(f"VERSION must be 1.0.0; found {version!r}.")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if "## [1.0.0] - 2026-07-21" not in changelog:
        raise ValueError("CHANGELOG is missing the v1.0.0 release entry.")
    required_scope_phrases = (
        "Quantitative seeding response",
        "external observational calibration",
        "field efficacy",
    )
    missing_scope_phrases = [
        phrase for phrase in required_scope_phrases if phrase not in changelog
    ]
    if missing_scope_phrases:
        raise ValueError(
            "CHANGELOG is missing scientific-scope boundaries: "
            f"{missing_scope_phrases}"
        )

    release_manifest_path = root / "release" / "v1.0.0.json"
    release_manifest = load_release_manifest(release_manifest_path)
    validate_release_manifest(release_manifest, project_root=root)
    release_report = build_release_readiness_report(release_manifest)
    if not release_report["ready"]:
        raise ValueError(
            "Release manifest is valid but not ready; next gate: "
            f"{release_report['next_gate']}"
        )

    scientific_scope = load_scientific_scope(
        root / "release" / "v1_scientific_scope.json"
    )
    validate_scientific_scope(scientific_scope, project_root=root)

    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    required_ci_markers = (
        "windows-latest",
        "ubuntu-latest",
        "Real PySDM integration",
        "tests.test_release_candidate",
        "check_scientific_scope.py",
        "check_release_readiness.py",
    )
    missing_ci_markers = [marker for marker in required_ci_markers if marker not in workflow]
    if missing_ci_markers:
        raise ValueError(f"CI is missing release-candidate markers: {missing_ci_markers}")

    return {
        "release": "v1.0.0",
        "version": version,
        "ready": True,
        "required_file_count": len(REQUIRED_RELEASE_FILES),
        "required_ci_markers": list(required_ci_markers),
        "blog_checkpoint": release_report["merge_policy"]["blog_checkpoint"],
        "merge_source": release_report["merge_policy"]["source_branch"],
        "merge_target": release_report["merge_policy"]["target_branch"],
    }

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from analysis.release_readiness import (
    build_release_readiness_report,
    load_release_manifest,
    validate_release_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "release" / "v1.0.0.json"


class ReleaseReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_release_manifest(MANIFEST_PATH)

    def test_repository_manifest_has_only_release_candidate_open(self) -> None:
        validate_release_manifest(self.manifest, project_root=PROJECT_ROOT)
        report = build_release_readiness_report(self.manifest)

        self.assertFalse(report["ready"])
        self.assertEqual(report["completed_gate_count"], 4)
        self.assertEqual(report["blocked_gates"], [])
        self.assertEqual(report["next_gate"], "release_candidate")
        self.assertEqual(
            report["merge_policy"]["blog_checkpoint"],
            "before_merge",
        )

    def test_ready_status_requires_all_required_gates_complete(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["overall_status"] = "ready"

        with self.assertRaisesRegex(ValueError, "required gate is open"):
            validate_release_manifest(invalid, project_root=PROJECT_ROOT)

    def test_completed_gate_requires_existing_evidence(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["gates"][0]["evidence"] = ["docs/does-not-exist.md"]

        with self.assertRaisesRegex(ValueError, "missing evidence"):
            validate_release_manifest(invalid, project_root=PROJECT_ROOT)

    def test_completed_gate_cannot_skip_incomplete_dependency(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["gates"][2]["status"] = "pending"
        invalid["gates"][3]["status"] = "complete"
        invalid["gates"][3]["evidence"] = ["PROJECT_STATUS.md"]

        with self.assertRaisesRegex(ValueError, "incomplete dependencies"):
            validate_release_manifest(invalid, project_root=PROJECT_ROOT)

    def test_dependency_must_appear_before_dependent_gate(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["gates"][0]["depends_on"] = ["release_candidate"]

        with self.assertRaisesRegex(ValueError, "must appear earlier"):
            validate_release_manifest(invalid, project_root=PROJECT_ROOT)

    def test_blocked_overall_status_requires_blocked_gate(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["overall_status"] = "blocked"

        with self.assertRaisesRegex(ValueError, "requires a blocked"):
            validate_release_manifest(invalid, project_root=PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()

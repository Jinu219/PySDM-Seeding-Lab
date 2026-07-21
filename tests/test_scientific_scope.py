from __future__ import annotations

import copy
import unittest
from pathlib import Path

from analysis.scientific_scope import (
    load_scientific_scope,
    summarize_scientific_scope,
    validate_scientific_scope,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCOPE_PATH = PROJECT_ROOT / "release" / "v1_scientific_scope.json"


class ScientificScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = load_scientific_scope(SCOPE_PATH)

    def test_repository_scope_preserves_conservative_claim_boundary(self) -> None:
        validate_scientific_scope(self.scope, project_root=PROJECT_ROOT)
        summary = summarize_scientific_scope(self.scope)
        self.assertEqual(summary["claim_count"], 6)
        self.assertEqual(summary["status_counts"]["supported"], 1)
        self.assertEqual(summary["status_counts"]["unsupported"], 3)
        self.assertIn(
            "external_observation_calibration",
            summary["unsupported_claim_ids"],
        )
        self.assertIn("field_efficacy", summary["unsupported_claim_ids"])

    def test_supported_claim_requires_scope(self) -> None:
        invalid = copy.deepcopy(self.scope)
        invalid["claims"][0].pop("scope")
        with self.assertRaisesRegex(ValueError, "explicit scope"):
            validate_scientific_scope(invalid, project_root=PROJECT_ROOT)

    def test_unsupported_claim_requires_limitation(self) -> None:
        invalid = copy.deepcopy(self.scope)
        invalid["claims"][1].pop("limitation")
        with self.assertRaisesRegex(ValueError, "explicit limitation"):
            validate_scientific_scope(invalid, project_root=PROJECT_ROOT)

    def test_claim_evidence_must_exist(self) -> None:
        invalid = copy.deepcopy(self.scope)
        invalid["claims"][0]["evidence"] = ["docs/missing-evidence.md"]
        with self.assertRaisesRegex(ValueError, "missing evidence"):
            validate_scientific_scope(invalid, project_root=PROJECT_ROOT)

    def test_release_classification_cannot_be_promoted(self) -> None:
        invalid = copy.deepcopy(self.scope)
        invalid["release_classification"] = "validated_field_science"
        with self.assertRaisesRegex(ValueError, "research workflow"):
            validate_scientific_scope(invalid, project_root=PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()

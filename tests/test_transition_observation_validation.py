from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.transition_observation_validation import (
    build_transition_observation_validation,
    normalize_observation_events,
    score_transition_candidates,
    summarize_transition_observation_validation,
)
from scripts.validate_transition_observations import run_validation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "transition_observations_synthetic.csv"
)


def _transition_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "activation_factor": 1.0,
                "rain_factor": 1.0,
                "activation_threshold_um": 25.0,
                "rain_threshold_um": 40.0,
                "rain_volume_fraction_threshold": 0.01,
                "control_transition_onset_s": 11.0,
                "seeding_transition_onset_s": 9.0,
            },
            {
                "activation_factor": 1.0,
                "rain_factor": 1.0,
                "activation_threshold_um": 30.0,
                "rain_threshold_um": 40.0,
                "rain_volume_fraction_threshold": 0.02,
                "control_transition_onset_s": 20.0,
                "seeding_transition_onset_s": 18.0,
            },
        ]
    )


class TransitionObservationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observations = pd.read_csv(FIXTURE_PATH)
        self.candidates = _transition_candidates()

    def test_candidate_scores_preserve_synthetic_evidence_boundary(self) -> None:
        validation = build_transition_observation_validation(
            self.candidates,
            self.observations,
        )
        scores = score_transition_candidates(validation)
        summary = summarize_transition_observation_validation(
            self.observations,
            validation,
            scores,
        )

        self.assertEqual(len(validation), 4)
        self.assertEqual(len(scores), 2)
        self.assertAlmostEqual(scores.iloc[0]["mean_absolute_error_s"], 1.0)
        self.assertAlmostEqual(
            scores.iloc[0]["within_observed_uncertainty_fraction"],
            1.0,
        )
        self.assertEqual(summary["status"], "synthetic_workflow_only")
        self.assertEqual(summary["n_resolved_comparisons"], 4)
        self.assertEqual(
            summary["lowest_mae_candidate"]["activation_threshold_um"],
            25.0,
        )
        self.assertEqual(
            summary["lowest_mae_candidate"]["rain_volume_fraction_threshold"],
            0.01,
        )

    def test_observational_rows_are_reported_separately(self) -> None:
        observations = self.observations.assign(
            evidence_class="observation",
            mapping_status="direct_temporal",
        )
        validation = build_transition_observation_validation(
            self.candidates,
            observations,
        )
        scores = score_transition_candidates(validation)
        summary = summarize_transition_observation_validation(
            observations,
            validation,
            scores,
        )

        self.assertEqual(summary["status"], "observational_comparison_available")
        self.assertEqual(summary["evidence_classes"], ["observation"])
        self.assertEqual(summary["mapping_statuses"], ["direct_temporal"])

        proxy_observations = observations.assign(
            mapping_status="spatiotemporal_proxy"
        )
        proxy_validation = build_transition_observation_validation(
            self.candidates,
            proxy_observations,
        )
        proxy_summary = summarize_transition_observation_validation(
            proxy_observations,
            proxy_validation,
            score_transition_candidates(proxy_validation),
        )
        self.assertEqual(
            proxy_summary["status"],
            "observational_mapping_review_required",
        )

    def test_invalid_contract_is_rejected(self) -> None:
        invalid = self.observations.drop(columns=["source_id"])
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            normalize_observation_events(invalid)

        invalid = self.observations.assign(evidence_class="inferred")
        with self.assertRaisesRegex(ValueError, "observation or synthetic"):
            normalize_observation_events(invalid)

        invalid_mapping = self.observations.assign(mapping_status="direct_temporal")
        with self.assertRaisesRegex(ValueError, "Synthetic evidence rows"):
            normalize_observation_events(invalid_mapping)

        missing_provenance = self.observations.copy()
        missing_provenance.loc[0, "source_id"] = pd.NA
        with self.assertRaisesRegex(ValueError, "source_id cannot contain blanks"):
            normalize_observation_events(missing_provenance)

        duplicate = pd.concat([self.observations, self.observations.iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "must be unique"):
            normalize_observation_events(duplicate)

    def test_cli_package_records_inputs_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result_dir = root / "comparison_result"
            result_dir.mkdir()
            self.candidates.to_csv(
                result_dir / "spectrum_transition_onset_robustness.csv",
                index=False,
            )
            output_dir = root / "validation_package"

            created = run_validation(
                result_dir=result_dir,
                observations_path=FIXTURE_PATH,
                output_dir=output_dir,
            )

            expected_files = {
                "observation_events.csv",
                "transition_observation_validation.csv",
                "transition_observation_candidate_scores.csv",
                "transition_observation_summary.json",
                "report.md",
                "observation_validation_manifest.json",
            }
            self.assertEqual({path.name for path in created.iterdir()}, expected_files)
            manifest = json.loads(
                (created / "observation_validation_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            summary = json.loads(
                (created / "transition_observation_summary.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["artifact_schema_version"], 2)
            self.assertEqual(manifest["evidence_classes"], ["synthetic"])
            self.assertEqual(len(manifest["observation_source_sha256"]), 64)
            self.assertEqual(len(manifest["source_transition_table_sha256"]), 64)
            self.assertEqual(summary["status"], "synthetic_workflow_only")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

"""Build a standalone observational transition-validation artifact package."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.transition_observation_validation import (
    TRANSITION_OBSERVATION_VALIDATION_BUILD_ID,
    build_transition_observation_validation,
    normalize_observation_events,
    score_transition_candidates,
    summarize_transition_observation_validation,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _markdown_report(summary: Dict[str, Any], source_result: Path) -> str:
    best = summary.get("lowest_mae_candidate") or {}
    lines = [
        "# Transition observation validation",
        "",
        f"- Build: `{summary['build_id']}`",
        f"- Source result: `{source_result}`",
        f"- Status: `{summary['status']}`",
        f"- Event/case rows: {summary['n_event_case_rows']}",
        f"- Candidate definitions: {summary['n_candidate_definitions']}",
        f"- Resolved comparisons: {summary['n_resolved_comparisons']} / {summary['n_comparisons']}",
        f"- Within observed uncertainty: {summary['n_within_observed_uncertainty']}",
        "",
        "## Lowest-MAE candidate (descriptive)",
        "",
    ]
    if best:
        for key, value in best.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("No resolved candidate was available.")
    lines.extend(["", "## Interpretation", "", str(summary["interpretation"]), ""])
    return "\n".join(lines)


def run_validation(
    *,
    result_dir: Path,
    observations_path: Path,
    output_dir: Path,
) -> Path:
    result_dir = Path(result_dir).resolve()
    observations_path = Path(observations_path).resolve()
    robustness_path = result_dir / "spectrum_transition_onset_robustness.csv"
    if not robustness_path.exists():
        raise FileNotFoundError(
            "Comparison result is missing spectrum_transition_onset_robustness.csv: "
            f"{result_dir}"
        )
    observations = normalize_observation_events(pd.read_csv(observations_path))
    robustness = pd.read_csv(robustness_path)
    validation = build_transition_observation_validation(robustness, observations)
    candidates = score_transition_candidates(validation)
    summary = summarize_transition_observation_validation(
        observations,
        validation,
        candidates,
    )

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    observations.to_csv(output_dir / "observation_events.csv", index=False)
    validation.to_csv(
        output_dir / "transition_observation_validation.csv", index=False
    )
    candidates.to_csv(output_dir / "transition_observation_candidate_scores.csv", index=False)
    _write_json(output_dir / "transition_observation_summary.json", summary)
    (output_dir / "report.md").write_text(
        _markdown_report(summary, result_dir), encoding="utf-8"
    )
    manifest = {
        "artifact_schema_version": 2,
        "build_id": TRANSITION_OBSERVATION_VALIDATION_BUILD_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_result_dir": str(result_dir),
        "source_transition_table": robustness_path.name,
        "source_transition_table_sha256": _sha256(robustness_path),
        "observation_source_file": observations_path.name,
        "observation_source_sha256": _sha256(observations_path),
        "evidence_classes": summary["evidence_classes"],
        "mapping_statuses": summary["mapping_statuses"],
        "files": {
            "observation_events": "observation_events.csv",
            "validation": "transition_observation_validation.csv",
            "candidate_scores": "transition_observation_candidate_scores.csv",
            "summary": "transition_observation_summary.json",
            "report": "report.md",
        },
    }
    _write_json(output_dir / "observation_validation_manifest.json", manifest)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare observed drizzle-onset events with model transition candidates."
    )
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = (
            PROJECT_ROOT
            / "artifacts"
            / "transition_observation_validation"
            / f"{timestamp}_{args.result_dir.name}"
        )
    result = run_validation(
        result_dir=args.result_dir,
        observations_path=args.observations,
        output_dir=output_dir,
    )
    summary = json.loads(
        (result / "transition_observation_summary.json").read_text(encoding="utf-8")
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Observation validation directory: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

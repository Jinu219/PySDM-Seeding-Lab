from __future__ import annotations

"""Extract an auditable fixed-column proxy from a local ARM ENA KAZR NetCDF."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.arm_ena_observations import (  # noqa: E402
    ARM_ENA_KAZR_DATASET_DOI,
    ARM_ENA_MAPPING_STATUS,
    ARM_ENA_OBSERVATION_BUILD_ID,
    build_arm_ena_observation_event,
    build_arm_ena_threshold_sensitivity,
    load_arm_kazr_netcdf,
)
from analysis.transition_observation_validation import (  # noqa: E402
    normalize_observation_events,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_extraction(
    *,
    netcdf_path: Path,
    output_dir: Path,
    event_id: str,
    case: str,
    window_start_s: float,
    window_end_s: float,
    observed_uncertainty_s: float,
    model_time_offset_s: float,
    reflectivity_threshold_dbz: float,
    minimum_height_m: float,
    maximum_height_m: float,
    minimum_drizzle_gates: int,
    minimum_persistence_s: float,
    allow_missing_quality: bool = False,
    source_id: str = ARM_ENA_KAZR_DATASET_DOI,
) -> Path:
    source_path = Path(netcdf_path).resolve()
    data, metadata = load_arm_kazr_netcdf(
        source_path,
        allow_missing_quality=allow_missing_quality,
    )
    event, audit = build_arm_ena_observation_event(
        data,
        metadata,
        event_id=event_id,
        case=case,
        source_id=source_id,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        observed_uncertainty_s=observed_uncertainty_s,
        model_time_offset_s=model_time_offset_s,
        reflectivity_threshold_dbz=reflectivity_threshold_dbz,
        minimum_height_m=minimum_height_m,
        maximum_height_m=maximum_height_m,
        minimum_drizzle_gates=minimum_drizzle_gates,
        minimum_persistence_s=minimum_persistence_s,
    )
    sensitivity = build_arm_ena_threshold_sensitivity(
        data,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        minimum_height_m=minimum_height_m,
        maximum_height_m=maximum_height_m,
        minimum_drizzle_gates=minimum_drizzle_gates,
        minimum_persistence_s=minimum_persistence_s,
    )
    audit["threshold_sensitivity"] = sensitivity.to_dict(orient="records")
    normalized_event = normalize_observation_events(event)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    normalized_event.to_csv(destination / "observation_events.csv", index=False)
    sensitivity.to_csv(destination / "arm_ena_threshold_sensitivity.csv", index=False)
    _write_json(destination / "mapping_audit.json", audit)
    manifest = {
        "artifact_schema_version": 1,
        "build_id": ARM_ENA_OBSERVATION_BUILD_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_id": source_id,
        "source_file": source_path.name,
        "source_sha256": _sha256(source_path),
        "source_metadata": metadata,
        "evidence_class": "observation",
        "mapping_status": ARM_ENA_MAPPING_STATUS,
        "files": {
            "observation_events": "observation_events.csv",
            "mapping_audit": "mapping_audit.json",
            "threshold_sensitivity": "arm_ena_threshold_sensitivity.csv",
        },
    }
    _write_json(destination / "arm_ena_observation_manifest.json", manifest)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract a persistent ARM ENA KAZR reflectivity event. Output remains "
            "a fixed-column spatiotemporal proxy."
        )
    )
    parser.add_argument("--netcdf", required=True, type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--case", required=True, choices=("control", "seeding"))
    parser.add_argument("--window-start-s", required=True, type=float)
    parser.add_argument("--window-end-s", required=True, type=float)
    parser.add_argument("--observed-uncertainty-s", required=True, type=float)
    parser.add_argument("--model-time-offset-s", required=True, type=float)
    parser.add_argument("--reflectivity-threshold-dbz", type=float, default=-17.0)
    parser.add_argument("--minimum-height-m", type=float, default=100.0)
    parser.add_argument("--maximum-height-m", type=float, default=2000.0)
    parser.add_argument("--minimum-drizzle-gates", type=int, default=1)
    parser.add_argument("--minimum-persistence-s", type=float, default=10.0)
    parser.add_argument("--allow-missing-quality", action="store_true")
    parser.add_argument("--source-id", default=ARM_ENA_KAZR_DATASET_DOI)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = (
            PROJECT_ROOT
            / "artifacts"
            / "arm_ena_observations"
            / f"{timestamp}_{args.event_id}"
        )
    result = run_extraction(
        netcdf_path=args.netcdf,
        output_dir=output_dir,
        event_id=args.event_id,
        case=args.case,
        window_start_s=args.window_start_s,
        window_end_s=args.window_end_s,
        observed_uncertainty_s=args.observed_uncertainty_s,
        model_time_offset_s=args.model_time_offset_s,
        reflectivity_threshold_dbz=args.reflectivity_threshold_dbz,
        minimum_height_m=args.minimum_height_m,
        maximum_height_m=args.maximum_height_m,
        minimum_drizzle_gates=args.minimum_drizzle_gates,
        minimum_persistence_s=args.minimum_persistence_s,
        allow_missing_quality=args.allow_missing_quality,
        source_id=args.source_id,
    )
    print(f"ARM ENA observation package: {result}")
    print(f"Mapping status: {ARM_ENA_MAPPING_STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

"""Extract an auditable observation-contract row from a local BASTALIAS NetCDF."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.bastalias_observations import (
    BASTALIAS_DATASET_DOI,
    BASTALIAS_OBSERVATION_BUILD_ID,
    BASTALIAS_THRESHOLD_VARIABLES,
    build_bastalias_observation_event,
    build_bastalias_threshold_sensitivity,
    load_bastalias_netcdf,
)
from analysis.transition_observation_validation import normalize_observation_events


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
    cloud_threshold_dbz: int,
    minimum_drizzle_pixels: int,
    minimum_persistence_s: float,
    source_id: str = BASTALIAS_DATASET_DOI,
) -> Path:
    source_path = Path(netcdf_path).resolve()
    threshold_timeseries = {}
    threshold_metadata = {}
    for threshold in BASTALIAS_THRESHOLD_VARIABLES:
        threshold_timeseries[threshold], threshold_metadata[threshold] = (
            load_bastalias_netcdf(
                source_path,
                cloud_threshold_dbz=threshold,
            )
        )
    timeseries = threshold_timeseries[int(cloud_threshold_dbz)]
    metadata = threshold_metadata[int(cloud_threshold_dbz)]
    event, audit = build_bastalias_observation_event(
        timeseries,
        event_id=event_id,
        case=case,
        source_id=source_id,
        time_units=metadata["time_units"],
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        observed_uncertainty_s=observed_uncertainty_s,
        model_time_offset_s=model_time_offset_s,
        cloud_threshold_dbz=cloud_threshold_dbz,
        minimum_drizzle_pixels=minimum_drizzle_pixels,
        minimum_persistence_s=minimum_persistence_s,
        source_file=source_path.name,
    )
    threshold_sensitivity = build_bastalias_threshold_sensitivity(
        threshold_timeseries,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
        minimum_drizzle_pixels=minimum_drizzle_pixels,
        minimum_persistence_s=minimum_persistence_s,
    )
    audit["threshold_sensitivity"] = threshold_sensitivity.to_dict(orient="records")
    normalized_event = normalize_observation_events(event)
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    normalized_event.to_csv(destination / "observation_events.csv", index=False)
    threshold_sensitivity.to_csv(
        destination / "bastalias_threshold_sensitivity.csv",
        index=False,
    )
    _write_json(destination / "mapping_audit.json", audit)
    manifest = {
        "artifact_schema_version": 1,
        "build_id": BASTALIAS_OBSERVATION_BUILD_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_id": source_id,
        "source_file": source_path.name,
        "source_sha256": _sha256(source_path),
        "source_metadata": metadata,
        "evidence_class": "observation",
        "mapping_status": "spatiotemporal_proxy",
        "files": {
            "observation_events": "observation_events.csv",
            "mapping_audit": "mapping_audit.json",
            "threshold_sensitivity": "bastalias_threshold_sensitivity.csv",
        },
    }
    _write_json(destination / "bastalias_observation_manifest.json", manifest)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract a quality-checked drizzle event from local EUREC4A BASTALIAS L2 "
            "NetCDF data. Output remains a spatiotemporal proxy."
        )
    )
    parser.add_argument("--netcdf", required=True, type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--case", required=True, choices=("control", "seeding"))
    parser.add_argument("--window-start-s", required=True, type=float)
    parser.add_argument("--window-end-s", required=True, type=float)
    parser.add_argument("--observed-uncertainty-s", required=True, type=float)
    parser.add_argument("--model-time-offset-s", required=True, type=float)
    parser.add_argument(
        "--cloud-threshold-dbz",
        type=int,
        choices=(-15, -17, -20),
        default=-20,
    )
    parser.add_argument("--minimum-drizzle-pixels", type=int, default=1)
    parser.add_argument("--minimum-persistence-s", type=float, default=3.0)
    parser.add_argument("--source-id", default=BASTALIAS_DATASET_DOI)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = (
            PROJECT_ROOT
            / "artifacts"
            / "bastalias_observations"
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
        cloud_threshold_dbz=args.cloud_threshold_dbz,
        minimum_drizzle_pixels=args.minimum_drizzle_pixels,
        minimum_persistence_s=args.minimum_persistence_s,
        source_id=args.source_id,
    )
    print(f"BASTALIAS observation package: {result}")
    print("Mapping status: spatiotemporal_proxy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

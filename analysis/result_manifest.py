from __future__ import annotations

"""Versioned result manifests and backward-compatible result inspection."""

import json
from pathlib import Path
from typing import Any, Dict


RESULT_SCHEMA_VERSION = 2
MINIMUM_READER_VERSION = 1
RESULT_READER_VERSION = 2
MINIMUM_SUPPORTED_SCHEMA_VERSION = 1


def build_result_manifest(
    *,
    result_type: str,
    primary_data: str,
    result_files: Dict[str, str],
    run_id: str,
) -> Dict[str, Any]:
    """Build the canonical manifest written by current result producers."""
    return {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "minimum_reader_version": MINIMUM_READER_VERSION,
        "result_type": str(result_type),
        "primary_data": str(primary_data),
        "run_id": str(run_id),
        "files": dict(result_files),
    }


def _infer_legacy_result_type(path: Path) -> tuple[str, str]:
    if path.is_file() and path.suffix.lower() == ".csv":
        return "legacy_csv", path.name
    if (path / "ensemble_statistics.csv").exists():
        return "ensemble", "ensemble_statistics.csv"
    if (path / "sweep_summary.csv").exists():
        return "parameter_sweep", "sweep_summary.csv"
    if (path / "comparison.csv").exists():
        return "comparison", "comparison.csv"
    if (path / "timeseries.csv").exists():
        return "single", "timeseries.csv"
    return "unknown", ""


def inspect_result_compatibility(path: Path) -> Dict[str, Any]:
    """Read a current manifest or infer a readable legacy result without one."""
    if path.is_file():
        result_type, primary = _infer_legacy_result_type(path)
        return {
            "status": "legacy_without_manifest",
            "readable": result_type != "unknown",
            "result_schema_version": 1,
            "result_type": result_type,
            "primary_data": primary,
            "message": "Legacy CSV result inferred from its filename.",
        }

    manifest_path = path / "result_manifest.json"
    if not manifest_path.exists():
        result_type, primary = _infer_legacy_result_type(path)
        return {
            "status": "legacy_without_manifest",
            "readable": result_type != "unknown",
            "result_schema_version": 1,
            "result_type": result_type,
            "primary_data": primary,
            "message": (
                "This result predates result_manifest.json; type and primary data were inferred "
                "from known files."
            ),
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid_manifest",
            "readable": False,
            "result_schema_version": None,
            "result_type": "unknown",
            "primary_data": "",
            "message": f"Could not parse result_manifest.json: {exc}",
        }

    version = manifest.get("result_schema_version")
    minimum_reader = manifest.get("minimum_reader_version", 1)
    if not isinstance(version, int) or isinstance(version, bool):
        return {
            "status": "invalid_manifest",
            "readable": False,
            "result_schema_version": version,
            "result_type": manifest.get("result_type", "unknown"),
            "primary_data": manifest.get("primary_data", ""),
            "message": "Manifest result_schema_version must be an integer.",
        }
    if (
        not isinstance(minimum_reader, int)
        or isinstance(minimum_reader, bool)
        or minimum_reader < 1
    ):
        return {
            "status": "invalid_manifest",
            "readable": False,
            "result_schema_version": version,
            "result_type": manifest.get("result_type", "unknown"),
            "primary_data": manifest.get("primary_data", ""),
            "message": "Manifest minimum_reader_version must be a positive integer.",
        }

    primary = str(manifest.get("primary_data", ""))
    primary_exists = bool(primary) and (path / primary).exists()
    if minimum_reader > RESULT_READER_VERSION:
        status = "requires_newer_reader"
        message = (
            f"Result requires reader {minimum_reader}, but this reader is "
            f"{RESULT_READER_VERSION}."
        )
    elif version > RESULT_SCHEMA_VERSION:
        status = "future_schema"
        message = (
            f"Result schema {version} is newer than reader {RESULT_SCHEMA_VERSION}; "
            "only known files may be readable."
        )
    elif version < MINIMUM_SUPPORTED_SCHEMA_VERSION:
        status = "unsupported_older_schema"
        message = (
            f"Result schema {version} is older than the minimum supported schema "
            f"{MINIMUM_SUPPORTED_SCHEMA_VERSION}."
        )
    elif not primary_exists:
        status = "missing_primary_data"
        message = f"Manifest primary data file is missing: {primary or '<empty>'}."
    elif version < RESULT_SCHEMA_VERSION:
        status = "supported_older_schema"
        message = f"Result schema {version} is supported by reader {RESULT_SCHEMA_VERSION}."
    else:
        status = "current"
        message = f"Result schema {version} matches the current reader."

    return {
        "status": status,
        "readable": (
            primary_exists
            and MINIMUM_SUPPORTED_SCHEMA_VERSION <= version <= RESULT_SCHEMA_VERSION
            and minimum_reader <= RESULT_READER_VERSION
        ),
        "result_schema_version": version,
        "reader_schema_version": RESULT_READER_VERSION,
        "minimum_reader_version": minimum_reader,
        "result_type": manifest.get("result_type", "unknown"),
        "primary_data": primary,
        "message": message,
        "manifest": manifest,
    }

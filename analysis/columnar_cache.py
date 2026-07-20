from __future__ import annotations

import importlib.util
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


COLUMNAR_CACHE_BUILD_ID = "csv-parquet-cache-v1-20260716"
CACHE_DIRECTORY_NAME = ".columnar_cache"
CACHE_SCHEMA_VERSION = 1
CACHE_ENVIRONMENT_VARIABLE = "PYSDM_COLUMNAR_CACHE"


@dataclass(frozen=True)
class ColumnarCachePaths:
    directory: Path
    parquet: Path
    metadata: Path


def columnar_cache_available() -> bool:
    """Return whether the optional Parquet engine is installed and enabled."""
    setting = os.environ.get(CACHE_ENVIRONMENT_VARIABLE, "1").strip().lower()
    if setting in {"0", "false", "no", "off"}:
        return False
    return importlib.util.find_spec("pyarrow") is not None


def columnar_cache_paths(csv_path: Path | str) -> ColumnarCachePaths:
    source = Path(csv_path)
    directory = source.parent / CACHE_DIRECTORY_NAME
    cache_name = f"{source.name}.parquet"
    return ColumnarCachePaths(
        directory=directory,
        parquet=directory / cache_name,
        metadata=directory / f"{cache_name}.json",
    )


def _source_fingerprint(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {
        "size_bytes": int(stat.st_size),
        "modified_time_ns": int(stat.st_mtime_ns),
    }


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _cache_matches_source(metadata: dict[str, Any], fingerprint: dict[str, int]) -> bool:
    return (
        metadata.get("cache_schema_version") == CACHE_SCHEMA_VERSION
        and metadata.get("build_id") == COLUMNAR_CACHE_BUILD_ID
        and metadata.get("source") == fingerprint
    )


def _atomic_write_text(path: Path, text: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def _write_columnar_cache(
    source: Path,
    dataframe: pd.DataFrame,
    fingerprint: dict[str, int],
) -> None:
    paths = columnar_cache_paths(source)
    paths.directory.mkdir(parents=True, exist_ok=True)
    temp_parquet = paths.parquet.with_name(
        f"{paths.parquet.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        dataframe.to_parquet(temp_parquet, engine="pyarrow", index=False)
        os.replace(temp_parquet, paths.parquet)
        metadata = {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "build_id": COLUMNAR_CACHE_BUILD_ID,
            "source_csv": source.name,
            "source": fingerprint,
            "row_count": int(len(dataframe)),
            "columns": [str(column) for column in dataframe.columns],
            "pandas_version": pd.__version__,
            "format": "parquet",
            "engine": "pyarrow",
        }
        _atomic_write_text(
            paths.metadata,
            json.dumps(metadata, ensure_ascii=False, indent=2),
        )
    finally:
        try:
            temp_parquet.unlink(missing_ok=True)
        except OSError:
            pass


def read_csv_with_columnar_cache(path: Path | str) -> pd.DataFrame:
    """
    Read CSV source data, using a validated Parquet cache when available.

    CSV remains the source of truth. Cache failures never prevent a CSV read, and
    a cache is written only when the source fingerprint is stable for the entire
    CSV parsing operation.
    """
    source = Path(path)
    if not columnar_cache_available():
        return pd.read_csv(source)

    try:
        fingerprint_before = _source_fingerprint(source)
    except OSError:
        return pd.read_csv(source)

    paths = columnar_cache_paths(source)
    metadata = _read_metadata(paths.metadata)
    if paths.parquet.is_file() and _cache_matches_source(metadata, fingerprint_before):
        try:
            return pd.read_parquet(paths.parquet, engine="pyarrow")
        except Exception:
            # Corrupt or incompatible cache: fall through to the source CSV.
            pass

    dataframe = pd.read_csv(source)
    try:
        fingerprint_after = _source_fingerprint(source)
        if fingerprint_before == fingerprint_after:
            _write_columnar_cache(source, dataframe, fingerprint_after)
    except Exception:
        # The cache is an optional performance artifact and must not affect results.
        pass
    return dataframe

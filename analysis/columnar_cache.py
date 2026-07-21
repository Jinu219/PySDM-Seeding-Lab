from __future__ import annotations

import importlib.util
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


COLUMNAR_CACHE_BUILD_ID = "csv-arrow-ipc-cache-v2-20260720"
CACHE_DIRECTORY_NAME = ".columnar_cache"
CACHE_SCHEMA_VERSION = 2
CACHE_ENVIRONMENT_VARIABLE = "PYSDM_COLUMNAR_CACHE"
CACHE_MINIMUM_CELLS_ENVIRONMENT_VARIABLE = "PYSDM_COLUMNAR_CACHE_MIN_CELLS"
DEFAULT_MINIMUM_CACHE_CELLS = 25_000


@dataclass(frozen=True)
class ColumnarCachePaths:
    directory: Path
    arrow: Path
    metadata: Path


def columnar_cache_available() -> bool:
    """Return whether the optional Arrow IPC engine is installed and enabled."""
    setting = os.environ.get(CACHE_ENVIRONMENT_VARIABLE, "1").strip().lower()
    if setting in {"0", "false", "no", "off"}:
        return False
    return importlib.util.find_spec("pyarrow") is not None


def minimum_cache_cells() -> int:
    """Return the minimum DataFrame cell count eligible for automatic caching."""
    raw = os.environ.get(
        CACHE_MINIMUM_CELLS_ENVIRONMENT_VARIABLE,
        str(DEFAULT_MINIMUM_CACHE_CELLS),
    )
    try:
        return max(int(raw), 0)
    except ValueError:
        return DEFAULT_MINIMUM_CACHE_CELLS


def columnar_cache_paths(csv_path: Path | str) -> ColumnarCachePaths:
    source = Path(csv_path)
    directory = source.parent / CACHE_DIRECTORY_NAME
    cache_name = f"{source.name}.arrow"
    return ColumnarCachePaths(
        directory=directory,
        arrow=directory / cache_name,
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


def _cached_cell_count(metadata: dict[str, Any]) -> int | None:
    if "cell_count" not in metadata:
        return None
    try:
        return max(int(metadata["cell_count"]), 0)
    except (TypeError, ValueError):
        return None


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
    temp_arrow = paths.arrow.with_name(
        f"{paths.arrow.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc

        table = pa.Table.from_pandas(dataframe, preserve_index=False)
        with pa.OSFile(str(temp_arrow), "wb") as sink:
            with ipc.new_file(sink, table.schema) as writer:
                writer.write_table(table)
        os.replace(temp_arrow, paths.arrow)
        metadata = {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "build_id": COLUMNAR_CACHE_BUILD_ID,
            "source_csv": source.name,
            "source": fingerprint,
            "row_count": int(len(dataframe)),
            "cell_count": int(dataframe.size),
            "columns": [str(column) for column in dataframe.columns],
            "pandas_version": pd.__version__,
            "format": "arrow_ipc_file",
            "engine": "pyarrow",
        }
        _atomic_write_text(
            paths.metadata,
            json.dumps(metadata, ensure_ascii=False, indent=2),
        )
        # Remove the short-lived v1 Parquet prototype after a successful Arrow
        # cache migration. These are disposable cache artifacts only.
        for legacy_path in (
            paths.directory / f"{source.name}.parquet",
            paths.directory / f"{source.name}.parquet.json",
        ):
            try:
                legacy_path.unlink(missing_ok=True)
            except OSError:
                pass
    finally:
        try:
            temp_arrow.unlink(missing_ok=True)
        except OSError:
            pass


def read_csv_with_columnar_cache(
    path: Path | str,
    *,
    force_cache: bool = False,
) -> pd.DataFrame:
    """
    Read CSV source data, using a validated Arrow IPC cache when available.

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
    cached_cell_count = _cached_cell_count(metadata)
    cache_is_eligible = (
        force_cache
        or (
            cached_cell_count is not None
            and cached_cell_count >= minimum_cache_cells()
        )
    )
    if (
        paths.arrow.is_file()
        and cache_is_eligible
        and _cache_matches_source(metadata, fingerprint_before)
    ):
        try:
            import pyarrow as pa
            import pyarrow.ipc as ipc

            with pa.memory_map(str(paths.arrow), "r") as source_file:
                return ipc.open_file(source_file).read_all().to_pandas()
        except Exception:
            # Corrupt or incompatible cache: fall through to the source CSV.
            pass

    dataframe = pd.read_csv(source)
    try:
        fingerprint_after = _source_fingerprint(source)
        if fingerprint_before == fingerprint_after and (
            force_cache or dataframe.size >= minimum_cache_cells()
        ):
            _write_columnar_cache(source, dataframe, fingerprint_after)
    except Exception:
        # The cache is an optional performance artifact and must not affect results.
        pass
    return dataframe

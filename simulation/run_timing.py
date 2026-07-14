from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


TIMING_HISTORY_FILENAME = ".run_timing_history.json"
MAX_HISTORY_ENTRIES = 300
MAX_ENTRIES_USED_FOR_ESTIMATE = 30

# Fallback per-run duration (seconds) used only when no local history exists yet
# for a given adapter. These are intentionally conservative "first guess" values;
# they are replaced by real measurements as soon as a few runs have completed.
DEFAULT_SECONDS_PER_RUN = {
    "placeholder_warm_cloud": 0.5,
    "pysdm_parcel": 12.0,
}
DEFAULT_FALLBACK_SECONDS_PER_RUN = 5.0


@dataclass(frozen=True)
class TimingEstimate:
    seconds_per_run: float
    total_seconds: float
    sample_size: int
    basis: str
    is_measured: bool


def _history_path(results_dir: Path) -> Path:
    return results_dir / TIMING_HISTORY_FILENAME


def _load_history(results_dir: Path) -> List[Dict[str, Any]]:
    path = _history_path(results_dir)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        # A corrupted or partially written history file must never break a run.
        return []


def record_run_timing(
    results_dir: Path,
    *,
    adapter: str,
    mode: str,
    elapsed_seconds: float,
    n_sd_total: Optional[int] = None,
) -> None:
    """
    Append one measured model-run duration to the local timing history.

    This is intentionally lightweight (a capped JSON list, not a database) since
    it only needs to support rough runtime estimation before large sweep/ensemble
    runs, not precise performance analysis.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    history = _load_history(results_dir)

    history.append(
        {
            "adapter": str(adapter),
            "mode": str(mode),
            "elapsed_seconds": float(elapsed_seconds),
            "n_sd_total": int(n_sd_total) if n_sd_total is not None else None,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
        }
    )

    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]

    try:
        with _history_path(results_dir).open("w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except OSError:
        # Timing history is a best-effort convenience feature; never fail a run
        # over a filesystem write issue here.
        pass


def estimate_seconds_per_run(results_dir: Path, adapter: str) -> TimingEstimate:
    """
    Estimate how long a single model run takes for the given adapter.

    Uses the median of the most recent locally recorded runs for this adapter
    when available, otherwise falls back to a conservative built-in default.
    """
    history = _load_history(results_dir)
    matching = [
        entry["elapsed_seconds"]
        for entry in history
        if entry.get("adapter") == adapter and isinstance(entry.get("elapsed_seconds"), (int, float))
    ]
    matching = matching[-MAX_ENTRIES_USED_FOR_ESTIMATE:]

    if matching:
        seconds_per_run = float(statistics.median(matching))
        basis = f"최근 동일 adapter({adapter}) 실행 {len(matching)}건의 중앙값 실측 시간"
        return TimingEstimate(
            seconds_per_run=seconds_per_run,
            total_seconds=seconds_per_run,
            sample_size=len(matching),
            basis=basis,
            is_measured=True,
        )

    fallback = DEFAULT_SECONDS_PER_RUN.get(adapter, DEFAULT_FALLBACK_SECONDS_PER_RUN)
    basis = (
        f"'{adapter}' adapter에 대한 실측 이력이 아직 없어 기본 추정값을 사용합니다. "
        "실행을 몇 번 완료하면 이후부터는 실측 중앙값으로 대체됩니다."
    )
    return TimingEstimate(
        seconds_per_run=float(fallback),
        total_seconds=float(fallback),
        sample_size=0,
        basis=basis,
        is_measured=False,
    )


def format_seconds(total_seconds: float) -> str:
    """Format a duration in seconds as a short human-readable string."""
    total_seconds = max(float(total_seconds), 0.0)
    if total_seconds < 60:
        return f"{total_seconds:.0f}초"

    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}분 {int(seconds)}초"

    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}시간 {int(minutes)}분"

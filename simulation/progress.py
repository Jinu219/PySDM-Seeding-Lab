from __future__ import annotations

from typing import Callable, Optional


ProgressCallback = Optional[Callable[[str, int, int, str], None]]


def emit_progress(
    callback: ProgressCallback,
    stage: str,
    current: int,
    total: int,
    message: str,
) -> None:
    """Emit progress if a callback is available."""
    if callback is None:
        return

    safe_total = max(int(total), 1)
    safe_current = max(0, min(int(current), safe_total))
    callback(stage, safe_current, safe_total, message)


class StdoutProgressReporter:
    """Small CLI progress reporter."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    def __call__(self, stage: str, current: int, total: int, message: str) -> None:
        if not self.enabled:
            return

        pct = current / max(total, 1) * 100.0
        print(f"[{current:02d}/{total:02d} | {pct:6.2f}%] {stage}: {message}", flush=True)

from __future__ import annotations

"""Lightweight sampled process-RSS monitoring for bounded benchmark sections."""

import threading
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in minimal installations
    psutil = None


@dataclass
class ProcessRSSMonitor:
    """Sample current-process RSS in a background thread."""

    sample_interval_seconds: float = 0.02
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _process: Any = field(default=None, init=False)
    _rss_before: int | None = field(default=None, init=False)
    _rss_after: int | None = field(default=None, init=False)
    _peak_rss: int | None = field(default=None, init=False)
    _samples: int = field(default=0, init=False)
    _started_at: float | None = field(default=None, init=False)
    _elapsed_seconds: float = field(default=0.0, init=False)

    def __enter__(self) -> "ProcessRSSMonitor":
        self._stop_event.clear()
        self._started_at = perf_counter()
        if psutil is None:
            return self
        self._process = psutil.Process()
        self._rss_before = int(self._process.memory_info().rss)
        self._peak_rss = self._rss_before
        self._samples = 1
        self._thread = threading.Thread(
            target=self._sample_loop,
            name="ensemble-rss-monitor",
            daemon=True,
        )
        self._thread.start()
        return self

    def _sample_loop(self) -> None:
        while not self._stop_event.wait(max(float(self.sample_interval_seconds), 0.001)):
            try:
                rss = int(self._process.memory_info().rss)
            except (OSError, RuntimeError):
                break
            self._peak_rss = max(int(self._peak_rss or 0), rss)
            self._samples += 1

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(0.1, self.sample_interval_seconds * 4))
        if self._process is not None:
            try:
                self._rss_after = int(self._process.memory_info().rss)
                self._peak_rss = max(int(self._peak_rss or 0), self._rss_after)
                self._samples += 1
            except (OSError, RuntimeError):
                pass
        if self._started_at is not None:
            self._elapsed_seconds = perf_counter() - self._started_at

    def summary(self) -> Dict[str, Any]:
        available = self._rss_before is not None and self._peak_rss is not None
        return {
            "available": available,
            "backend": "psutil" if available else "unavailable",
            "sample_interval_seconds": float(self.sample_interval_seconds),
            "n_samples": int(self._samples),
            "elapsed_seconds": float(self._elapsed_seconds),
            "rss_before_bytes": self._rss_before,
            "rss_after_bytes": self._rss_after,
            "peak_rss_bytes": self._peak_rss,
            "peak_rss_increase_bytes": (
                int(self._peak_rss - self._rss_before) if available else None
            ),
            "scope": (
                "Sampled resident set size for the whole Python process during the monitored context. "
                "The peak may fall between samples."
            ),
        }

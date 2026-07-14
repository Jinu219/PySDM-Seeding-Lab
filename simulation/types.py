from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import pandas as pd


@dataclass(frozen=True)
class SimulationRunSpec:
    """Normalized run specification passed from runner to adapter."""

    run_id: str
    experiment_name: str
    experiment_mode: str
    adapter_name: str
    case_name: str
    config: Dict[str, Any]
    settings: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResult:
    """Standard return object from any simulation adapter."""

    timeseries: pd.DataFrame
    metadata: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    tables: Dict[str, pd.DataFrame] = field(default_factory=dict)

    def require_timeseries(self) -> pd.DataFrame:
        """Return timeseries after checking the required time column."""
        if "time_s" not in self.timeseries.columns:
            raise ValueError("AdapterResult.timeseries must contain a 'time_s' column.")
        return self.timeseries

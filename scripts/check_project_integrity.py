from __future__ import annotations

import importlib
import py_compile
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_DASHBOARD_FUNCTIONS = [
    "discover_results",
    "load_result",
    "flatten_summary",
    "format_metric_value",
    "available_numeric_columns",
    "recommended_column_groups",
    "comparison_base_variables",
    "plot_time_series",
    "plot_selected_variable",
    "plot_control_vs_seeding",
    "plot_difference",
    "plot_sweep_ranking",
    "sweep_base_variables",
    "build_sweep_overlay_dataframe",
    "plot_sweep_overlay",
    "compute_overlay_spread",
    "sweep_param_columns",
    "plot_sweep_heatmap",
]


def main() -> None:
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "dashboard.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "pages" / "06_results.py"), doraise=True)

    dashboard = importlib.import_module("analysis.dashboard")

    missing = [name for name in REQUIRED_DASHBOARD_FUNCTIONS if not hasattr(dashboard, name)]
    if missing:
        raise RuntimeError(
            "Missing dashboard exports:\n" + "\n".join(f"- {name}" for name in missing)
        )

    print("Project integrity check passed.")
    print("Dashboard exports are complete.")


if __name__ == "__main__":
    main()

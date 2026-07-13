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
    "build_overlay_legend_table",
]



def check_page_files() -> None:
    expected = {
        "00_experiment_scenarios.py",
        "01_environment.py",
        "02_aerosol.py",
        "03_seeding.py",
        "04_dynamics.py",
        "05_parameter_sweep.py",
        "06_run.py",
        "07_results.py",
    }
    forbidden = {
        "05_run.py",
        "06_results.py",
        "07_parameter_sweep.py",
    }

    page_dir = PROJECT_ROOT / "pages"
    existing = {path.name for path in page_dir.glob("*.py")}

    bad = sorted(existing.intersection(forbidden))
    if bad:
        raise RuntimeError(
            "Old page files still exist and can cause duplicate Streamlit URL pathnames:\\n"
            + "\\n".join(f"- pages/{name}" for name in bad)
            + "\\nRun: python scripts/cleanup_old_pages.py"
        )

    missing_pages = sorted(expected - existing)
    if missing_pages:
        raise RuntimeError(
            "Expected page files are missing:\\n"
            + "\\n".join(f"- pages/{name}" for name in missing_pages)
        )



def check_safe_read_csv_no_recursion() -> None:
    dashboard_path = PROJECT_ROOT / "analysis" / "dashboard.py"
    text = dashboard_path.read_text(encoding="utf-8")
    start = text.find("def safe_read_csv")
    end = text.find("def flatten_summary", start)
    if start == -1 or end == -1:
        raise RuntimeError("Could not locate safe_read_csv block in analysis/dashboard.py")

    block = text[start:end]
    if "return safe_read_csv(path)" in block:
        raise RuntimeError(
            "safe_read_csv is recursively calling itself. "
            "Run: python scripts/fix_dashboard_recursion.py"
        )
    if "return pd.read_csv(path)" not in block:
        raise RuntimeError("safe_read_csv does not call pd.read_csv(path).")


def main() -> None:
    check_safe_read_csv_no_recursion()
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "dashboard.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "pages" / "07_results.py"), doraise=True)

    dashboard = importlib.import_module("analysis.dashboard")

    missing = [name for name in REQUIRED_DASHBOARD_FUNCTIONS if not hasattr(dashboard, name)]
    if missing:
        raise RuntimeError(
            "Missing dashboard exports:\n" + "\n".join(f"- {name}" for name in missing)
        )

    print("Project integrity check passed.")
    print("Dashboard exports are complete.")
    print(f"Dashboard build: {getattr(dashboard, 'DASHBOARD_BUILD_ID', 'unknown')}")


if __name__ == "__main__":
    main()

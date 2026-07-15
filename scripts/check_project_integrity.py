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
    "sweep_execution_status_table",
    "build_sweep_overlay_dataframe",
    "plot_sweep_overlay",
    "compute_overlay_spread",
    "sweep_param_columns",
    "plot_sweep_heatmap",
    "build_overlay_legend_table",
    "growth_pathway_all_variables",
    "growth_pathway_variable_groups",
    "diagnostic_provenance_dataframe",
    "diagnostic_provenance_summary_counts",
    "result_file_roles_dataframe",
    "filter_sweep_dataframe",
    "build_sweep_overlay_dataframe_relative_time",
    "sweep_case_metrics_table",
    "varying_sweep_parameters",
    "plot_parameter_sensitivity",
    "add_kappa_koehler_collapse_variable",
    "plot_collapse_variable_response",
    "plot_response_surface_heatmap",
    "plot_ensemble_uncertainty",
    "ensemble_available_bases",
    "load_sweep_case_publication_data",
    "sweep_case_display_label",
    "matched_collision_cases",
    "plot_growth_pathway_four_panel",
    "plot_ensemble_uncertainty_panel",
    "plot_one_factor_sensitivity_panel",
    "plot_collision_off_on_panel",
    "plot_wet_radius_spectrum",
    "plot_threshold_robustness",
    "plot_wet_radius_spectrum_difference",
    "plot_threshold_robustness_difference",
    "spectrum_checkpoint_times",
    "threshold_robustness_metrics",
    "plot_water_budget",
    "plot_numerical_convergence",
    "plot_spectrum_transition",
    "convergence_metrics",
    "figure_to_svg_bytes",
    "figure_to_pdf_bytes",
    "apply_publication_style",
    "publication_parameter_label",
    "publication_variable_label",
    "comparison_seeding_intervals",
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


def check_sweep_catalog() -> None:
    from simulation.schema import default_config
    from simulation.sweep import generate_sweep_cases
    from simulation.sweep_catalog import COMMON_SWEEP_PARAMETERS, SENSITIVITY_PRESETS

    names = [spec.name for spec in COMMON_SWEEP_PARAMETERS]
    if len(names) != len(set(names)):
        raise RuntimeError("Common sweep catalog contains duplicate parameter names.")
    if len(names) < 15:
        raise RuntimeError("Common sweep catalog unexpectedly lost parameter coverage.")

    for preset_name, preset in SENSITIVITY_PRESETS.items():
        parameters = preset.get("parameters", {})
        if preset_name == "Custom":
            continue
        unknown = sorted(set(parameters) - set(names))
        if unknown:
            raise RuntimeError(f"Preset {preset_name!r} uses unknown parameters: {unknown}")
        case_count = 1
        for raw_values in parameters.values():
            case_count *= len([item for item in str(raw_values).split(",") if item.strip()])
        if case_count > 100:
            raise RuntimeError(f"Preset {preset_name!r} exceeds the default 100-case safety limit.")

    cfg = default_config()
    cfg["experiment"]["mode"] = "parameter_sweep"
    cfg["sweep"]["max_runs"] = 10
    cfg["sweep"]["parameters"] = [
        {"name": "seeding.injection_start", "values": [100, 200]},
        {"name": "seeding.injection_duration", "values": [30]},
    ]
    cases = generate_sweep_cases(cfg)
    expected_ends = [130, 230]
    actual_ends = [case.config["seeding"]["injection_end"] for case in cases]
    if actual_ends != expected_ends:
        raise RuntimeError(
            f"Derived injection_end values are wrong: expected {expected_ends}, got {actual_ends}"
        )


def check_native_diagnostic_contract() -> None:
    import numpy as np

    from analysis.growth_pathway_diagnostics import diagnostic_provenance_rows
    from simulation.builder import build_run_spec
    from simulation.pysdm_parcel_adapter import _output_to_dataframe
    from simulation.schema import default_config, diagnostic_radius_thresholds
    from simulation.validation import validate_config_detailed

    cfg = default_config()
    activation_radius, rain_radius = diagnostic_radius_thresholds(cfg)
    if not 0 < activation_radius < rain_radius:
        raise RuntimeError("Default diagnostic radius thresholds are invalid.")

    products = {"time": np.array([0.0, 15.0])}
    for index, name in enumerate(
        (
            "temperature_K",
            "pressure_Pa",
            "water_vapour_mixing_ratio",
            "relative_humidity",
            "unactivated_water_mixing_ratio",
            "cloud_water_mixing_ratio",
            "rain_water_mixing_ratio",
            "total_liquid_water_mixing_ratio",
            "cloud_droplet_concentration",
            "rain_droplet_concentration",
            "effective_radius_cloud_um",
            "effective_radius_rain_um",
            "effective_radius_all_um",
            "superdroplet_count",
        ),
        start=1,
    ):
        products[name] = np.full(2, index * 0.01)

    df = _output_to_dataframe({"products": products}, build_run_spec(cfg))
    provenance = diagnostic_provenance_rows(list(df.columns), cfg)
    proxies = [row["variable"] for row in provenance if row["provenance"] == "proxy"]
    if proxies:
        raise RuntimeError(f"Native diagnostic contract regressed to proxy: {proxies}")

    invalid = default_config()
    invalid["diagnostics"]["activation_radius_threshold"] = 30.0e-6
    invalid["diagnostics"]["rain_radius_threshold"] = 25.0e-6
    errors = [
        issue
        for issue in validate_config_detailed(invalid)
        if issue.severity == "error"
    ]
    if not any(issue.field == "diagnostics.rain_radius_threshold" for issue in errors):
        raise RuntimeError("Invalid diagnostic threshold ordering is not rejected.")


def check_result_path_policy() -> None:
    from simulation.path_policy import (
        COMPARISON_RESULT_DESCENDANT_RESERVE,
        ENSEMBLE_RESULT_DESCENDANT_RESERVE,
        SWEEP_RESULT_DESCENDANT_RESERVE,
        WINDOWS_PORTABLE_PATH_LIMIT,
        path_character_count,
        resolve_result_directory,
    )

    sweep_dir = resolve_result_directory(
        PROJECT_ROOT / "results",
        "very_long_scenario_name_" * 20,
        descendant_reserve=SWEEP_RESULT_DESCENDANT_RESERVE,
    )
    case_dir = resolve_result_directory(
        sweep_dir / "cases",
        "case_001",
        directory_name="case_001",
        descendant_reserve=ENSEMBLE_RESULT_DESCENDANT_RESERVE,
    )
    comparison_dir = resolve_result_directory(
        case_dir / "members" / "member_001",
        "comparison",
        directory_name="comparison",
        descendant_reserve=COMPARISON_RESULT_DESCENDANT_RESERVE,
    )
    representative_artifact = (
        comparison_dir / "seeding" / "diagnostic_provenance.json"
    )
    if path_character_count(representative_artifact) > WINDOWS_PORTABLE_PATH_LIMIT:
        raise RuntimeError("Compact nested sweep path exceeds the portable path limit.")


def check_rain_qualification_contract() -> None:
    from scripts.run_numerical_qualification import (
        build_qualification_config,
        qualification_plan,
    )
    from simulation.schema import default_config

    config = build_qualification_config(
        default_config(),
        profile="rain_standard",
        adapter="pysdm_parcel",
    )
    plan = qualification_plan(config, profile="rain_standard")
    if plan["case_count"] != 7 or plan["model_execution_count"] != 14:
        raise RuntimeError("Rain qualification lost its seven-case OFAT design.")
    if not config["microphysics"]["collision"] or not plan["rain_signal_required"]:
        raise RuntimeError("Rain qualification no longer enforces collision and rain signal.")


def check_ensemble_memory_comparison_contract() -> None:
    from analysis.resource_monitor import compare_ensemble_memory_benchmarks

    baseline = {
        "profile": "pilot",
        "workload": {"n_members": 3},
        "collect_garbage_between_members": False,
        "full_run_elapsed_seconds": 10.0,
        "full_process_rss": {"peak_rss_increase_bytes": 100},
        "memory_checkpoint_summary": {
            "member_boundary_rss_increase_bytes": 50,
            "member_boundary_rss_slope_bytes_per_member": 25.0,
        },
    }
    explicit_gc = {
        "profile": "pilot",
        "workload": {"n_members": 3},
        "collect_garbage_between_members": True,
        "full_run_elapsed_seconds": 11.0,
        "full_process_rss": {"peak_rss_increase_bytes": 105},
        "memory_checkpoint_summary": {
            "member_boundary_rss_increase_bytes": 55,
            "member_boundary_rss_slope_bytes_per_member": 27.5,
            "gc_reclaimed_rss_total_bytes": 20,
        },
    }
    comparison = compare_ensemble_memory_benchmarks(baseline, explicit_gc)
    if comparison["recommend_collect_garbage_between_members_default"]:
        raise RuntimeError("Memory comparison incorrectly recommends a regressive GC run.")


def main() -> None:
    check_page_files()
    check_safe_read_csv_no_recursion()
    check_sweep_catalog()
    check_native_diagnostic_contract()
    check_result_path_policy()
    check_rain_qualification_contract()
    check_ensemble_memory_comparison_contract()
    py_compile.compile(str(PROJECT_ROOT / "app.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "ui_helpers.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "sweep_catalog.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "sweep.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "path_policy.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "native_parcel_simulation.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "pysdm_parcel_adapter.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "simulation" / "wet_radius_spectrum.py"), doraise=True)
    for page_path in sorted((PROJECT_ROOT / "pages").glob("*.py")):
        py_compile.compile(str(page_path), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "publication_plots.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "ensemble_statistics.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "resource_monitor.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "wet_radius_plots.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "water_budget.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "numerical_convergence.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "case_diagnostic_comparison.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "spectrum_transition.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "qualification_evidence.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "reporting.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "result_manifest.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "analysis" / "dashboard.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "pages" / "07_results.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "scripts" / "run_numerical_qualification.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "scripts" / "run_ensemble_benchmark.py"), doraise=True)
    py_compile.compile(str(PROJECT_ROOT / "scripts" / "compare_ensemble_memory_benchmarks.py"), doraise=True)

    dashboard = importlib.import_module("analysis.dashboard")

    missing = [name for name in REQUIRED_DASHBOARD_FUNCTIONS if not hasattr(dashboard, name)]
    if missing:
        raise RuntimeError(
            "Missing dashboard exports:\n" + "\n".join(f"- {name}" for name in missing)
        )

    print("Project integrity check passed.")
    print("Dashboard exports are complete.")
    print("Native diagnostic contract is complete (proxy-free synthetic mapping).")
    print("Portable result-path budget check passed.")
    print("Collision-ON rain qualification contract passed.")
    print("Ensemble retained-memory A/B comparison contract passed.")
    print(f"Dashboard build: {getattr(dashboard, 'DASHBOARD_BUILD_ID', 'unknown')}")


if __name__ == "__main__":
    main()

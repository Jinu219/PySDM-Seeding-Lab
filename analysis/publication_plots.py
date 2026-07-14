from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PUBLICATION_PLOTS_BUILD_ID = "publication-diagnostic-panels-20260714"


VARIABLE_METADATA: Dict[str, Dict[str, str]] = {
    "water_vapour_mixing_ratio": {
        "label": "Water-vapour mixing ratio",
        "unit": "kg kg⁻¹",
    },
    "supersaturation_percent": {
        "label": "Supersaturation",
        "unit": "%",
        "difference_unit": "percentage points",
    },
    "relative_humidity_percent": {
        "label": "Relative humidity",
        "unit": "%",
        "difference_unit": "percentage points",
    },
    "temperature_K": {
        "label": "Temperature",
        "unit": "K",
    },
    "cloud_water_mixing_ratio": {
        "label": "Cloud-water mixing ratio",
        "unit": "kg kg⁻¹",
    },
    "rain_water_mixing_ratio": {
        "label": "Rain-water mixing ratio",
        "unit": "kg kg⁻¹",
    },
    "all_activated_water_mixing_ratio": {
        "label": "Activated-water mixing ratio",
        "unit": "kg kg⁻¹",
    },
    "cloud_droplet_concentration": {
        "label": "Cloud-droplet concentration",
        "unit": "cm⁻³",
    },
    "rain_droplet_concentration": {
        "label": "Rain-droplet concentration",
        "unit": "cm⁻³",
    },
    "all_activated_concentration": {
        "label": "Activated-particle concentration",
        "unit": "cm⁻³",
    },
    "effective_radius_cloud_um": {
        "label": "Cloud effective radius",
        "unit": "µm",
    },
    "effective_radius_rain_um": {
        "label": "Rain effective radius",
        "unit": "µm",
    },
    "effective_radius_all_um": {
        "label": "Activated-particle effective radius",
        "unit": "µm",
    },
}


DEFAULT_PATHWAY_VARIABLES: Dict[str, str] = {
    "Thermodynamic pathway": "supersaturation_percent",
    "Water mass pathway": "all_activated_water_mixing_ratio",
    "Number concentration pathway": "all_activated_concentration",
    "Size growth pathway": "effective_radius_all_um",
}


PROVENANCE_CODES = {
    "native": "N",
    "derived": "D",
    "proxy": "P",
}

CONTROL_COLOR = "#3B6FB6"
SEEDING_COLOR = "#D66A3A"
BAND_COLOR = "#4C78A8"
GRID_COLOR = "#B8B8B8"
SEEDING_WINDOW_COLOR = "#9A9A9A"
CURVE_COLORS = [
    "#0072B2",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#E69F00",
    "#56B4E9",
    "#000000",
]


def _base_variable(variable: str) -> str:
    for suffix in (
        "_relative_change_percent",
        "_control",
        "_seeding",
        "_diff",
        "_mean",
        "_median",
        "_q25",
        "_q75",
        "_std",
    ):
        if variable.endswith(suffix):
            return variable[: -len(suffix)]
    return variable


def publication_variable_label(variable: str, *, difference: bool = False) -> str:
    """Return a readable axis label with an explicit unit."""
    base = _base_variable(variable)
    meta = VARIABLE_METADATA.get(base, {})
    label = meta.get("label", base.replace("_", " "))
    unit = meta.get("difference_unit" if difference else "unit", "adapter units")
    prefix = "Δ " if difference else ""
    return f"{prefix}{label} [{unit}]"


def publication_parameter_label(parameter: str) -> str:
    short = parameter.replace("param.", "")
    if parameter.endswith("dry_radius"):
        prefix = "Background aerosol" if "background_aerosol" in parameter else "Seeding"
        return f"{prefix} dry radius [µm]"
    if parameter.endswith("kappa"):
        prefix = "Background aerosol" if "background_aerosol" in parameter else "Seeding"
        return f"{prefix} hygroscopicity κ [–]"
    if parameter.endswith("injection_start"):
        return "Injection start [s]"
    if parameter.endswith("injection_duration"):
        return "Injection duration [s]"
    if parameter.endswith("updraft_velocity"):
        return "Updraft velocity [m s⁻¹]"
    if parameter.endswith("temperature"):
        return "Initial temperature [K]"
    if parameter.endswith("pressure"):
        return "Initial pressure [Pa]"
    if parameter.endswith("water_vapour_mixing_ratio"):
        return "Initial water-vapour mixing ratio [kg kg⁻¹]"
    if parameter.endswith("timestep"):
        return "Model timestep [s]"
    if parameter.endswith("number_concentration"):
        prefix = "Background" if "background_aerosol" in parameter else "Seeding"
        return f"{prefix} number concentration [cm⁻³]"
    if parameter.endswith("number_superdroplets"):
        prefix = "Background" if "background_aerosol" in parameter else "Seeding"
        return f"{prefix} super-droplet count [–]"
    if parameter.endswith("geometric_sigma"):
        prefix = "Background" if "background_aerosol" in parameter else "Seeding"
        return f"{prefix} geometric σ [–]"
    if parameter.endswith("collision"):
        return "Collision–coalescence"
    return short


def _parameter_values(series: pd.Series, parameter: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if parameter.endswith("dry_radius"):
        return values * 1.0e6
    return values


def _provenance_lookup(provenance_rows: Sequence[Mapping[str, Any]] | None) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for row in provenance_rows or []:
        variable = str(row.get("variable", ""))
        provenance = str(row.get("provenance", ""))
        if variable:
            lookup[variable] = provenance
    return lookup


def _provenance_code(variable: str, provenance_rows: Sequence[Mapping[str, Any]] | None) -> str:
    provenance = _provenance_lookup(provenance_rows).get(_base_variable(variable))
    return PROVENANCE_CODES.get(provenance, "?")


def publication_provenance_note(
    variables: Iterable[str],
    provenance_rows: Sequence[Mapping[str, Any]] | None,
) -> str:
    """Build the compact provenance footer used on exported figures."""
    seen = []
    for variable in variables:
        base = _base_variable(variable)
        if base not in seen:
            seen.append(base)
    entries = [
        f"{VARIABLE_METADATA.get(var, {}).get('label', var)} [{_provenance_code(var, provenance_rows)}]"
        for var in seen
    ]
    return (
        "Diagnostic provenance — "
        + "; ".join(entries)
        + ".  N: native, D: derived, P: proxy, ?: unavailable."
    )


def _style_axis(ax, *, difference: bool = False) -> None:
    ax.grid(True, color=GRID_COLOR, alpha=0.35, linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if difference:
        ax.axhline(0.0, color="#4A4A4A", linewidth=0.8, alpha=0.7, zorder=0)


def _shade_intervals(ax, intervals: Sequence[tuple[float, float]] | None) -> None:
    for start, end in intervals or []:
        ax.axvspan(start, end, color=SEEDING_WINDOW_COLOR, alpha=0.14, linewidth=0)


def _finalize_panel_figure(
    fig,
    *,
    variables: Sequence[str],
    provenance_rows: Sequence[Mapping[str, Any]] | None,
    bottom: float = 0.12,
) -> None:
    fig.text(
        0.01,
        0.018,
        publication_provenance_note(variables, provenance_rows),
        ha="left",
        va="bottom",
        fontsize=7.2,
        color="#3F3F3F",
    )
    fig.subplots_adjust(left=0.09, right=0.98, top=0.90, bottom=bottom, hspace=0.38, wspace=0.28)


def plot_growth_pathway_four_panel(
    comparison_df: pd.DataFrame,
    *,
    variables_by_group: Mapping[str, str],
    mode: str = "diff",
    provenance_rows: Sequence[Mapping[str, Any]] | None = None,
    seeding_intervals: Sequence[tuple[float, float]] | None = None,
):
    """Create a 2×2 growth-pathway figure for one control/seeding comparison."""
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex=True)
    axes_flat = axes.ravel()
    selected = list(variables_by_group.items())[:4]
    panel_letters = "abcd"

    fig.suptitle("Warm-cloud seeding growth pathway", fontsize=13, fontweight="semibold")

    for idx, ax in enumerate(axes_flat):
        if idx >= len(selected):
            ax.set_visible(False)
            continue

        group, variable = selected[idx]
        code = _provenance_code(variable, provenance_rows)
        title = f"({panel_letters[idx]}) {group.replace(' pathway', '')} · {VARIABLE_METADATA.get(variable, {}).get('label', variable)} [{code}]"
        ax.set_title(title, fontsize=9.5, loc="left")
        _shade_intervals(ax, seeding_intervals)

        if comparison_df.empty or "time_s" not in comparison_df.columns:
            ax.text(0.5, 0.5, "No comparison data", ha="center", va="center", transform=ax.transAxes)
            _style_axis(ax)
            continue

        x = pd.to_numeric(comparison_df["time_s"], errors="coerce")
        if mode == "control_vs_seeding":
            control_col = f"{variable}_control"
            seeding_col = f"{variable}_seeding"
            if control_col in comparison_df.columns:
                ax.plot(x, comparison_df[control_col], color=CONTROL_COLOR, linestyle="--", linewidth=1.7, label="Control")
            if seeding_col in comparison_df.columns:
                ax.plot(x, comparison_df[seeding_col], color=SEEDING_COLOR, linewidth=1.8, label="Seeding")
            ax.set_ylabel(publication_variable_label(variable))
            if control_col in comparison_df.columns or seeding_col in comparison_df.columns:
                ax.legend(frameon=False, fontsize=8, loc="best")
            else:
                ax.text(0.5, 0.5, f"Missing: {variable}", ha="center", va="center", transform=ax.transAxes)
            _style_axis(ax)
        else:
            diff_col = f"{variable}_diff"
            if diff_col in comparison_df.columns:
                ax.plot(x, comparison_df[diff_col], color=SEEDING_COLOR, linewidth=1.8, label="Seeding − control")
            else:
                ax.text(0.5, 0.5, f"Missing: {diff_col}", ha="center", va="center", transform=ax.transAxes)
            ax.set_ylabel(publication_variable_label(variable, difference=True))
            _style_axis(ax, difference=True)

        if idx >= 2:
            ax.set_xlabel("Time [s]")

    _finalize_panel_figure(
        fig,
        variables=[variable for _, variable in selected],
        provenance_rows=provenance_rows,
    )
    return fig


def plot_ensemble_uncertainty_panel(
    stats_df: pd.DataFrame,
    *,
    base_variables: Sequence[str],
    mode: str = "mean_std",
    provenance_rows: Sequence[Mapping[str, Any]] | None = None,
):
    """Create a publication-style 2×2 ensemble uncertainty figure."""
    variables = list(base_variables)[:4]
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex=True)
    axes_flat = axes.ravel()
    panel_letters = "abcd"
    title_mode = "Mean ± 1 standard deviation" if mode == "mean_std" else "Median and interquartile range"
    fig.suptitle(f"Warm-cloud seeding ensemble · {title_mode}", fontsize=13, fontweight="semibold")

    for idx, ax in enumerate(axes_flat):
        if idx >= len(variables):
            ax.set_visible(False)
            continue

        variable = variables[idx]
        base = _base_variable(variable)
        difference = variable.endswith("_diff")
        code = _provenance_code(variable, provenance_rows)
        ax.set_title(
            f"({panel_letters[idx]}) {VARIABLE_METADATA.get(base, {}).get('label', base)} [{code}]",
            fontsize=9.5,
            loc="left",
        )

        if stats_df.empty or "time_s" not in stats_df.columns:
            ax.text(0.5, 0.5, "No ensemble data", ha="center", va="center", transform=ax.transAxes)
            _style_axis(ax, difference=difference)
            continue

        x = pd.to_numeric(stats_df["time_s"], errors="coerce").to_numpy(dtype=float)
        if mode == "median_iqr":
            center_col = f"{variable}_median"
            low_col = f"{variable}_q25"
            high_col = f"{variable}_q75"
            center_label = "Median"
            band_label = "IQR"
        else:
            center_col = f"{variable}_mean"
            std_col = f"{variable}_std"
            low_col = high_col = ""
            center_label = "Mean"
            band_label = "±1 std"

        if center_col not in stats_df.columns:
            ax.text(0.5, 0.5, f"Missing: {center_col}", ha="center", va="center", transform=ax.transAxes)
            _style_axis(ax, difference=difference)
            continue

        center = pd.to_numeric(stats_df[center_col], errors="coerce").to_numpy(dtype=float)
        if mode == "median_iqr" and low_col in stats_df.columns and high_col in stats_df.columns:
            low = pd.to_numeric(stats_df[low_col], errors="coerce").to_numpy(dtype=float)
            high = pd.to_numeric(stats_df[high_col], errors="coerce").to_numpy(dtype=float)
        elif mode == "mean_std" and std_col in stats_df.columns:
            spread = pd.to_numeric(stats_df[std_col], errors="coerce").fillna(0).to_numpy(dtype=float)
            low = center - spread
            high = center + spread
        else:
            low = center
            high = center

        ax.fill_between(x, low, high, color=BAND_COLOR, alpha=0.22, linewidth=0, label=band_label)
        ax.plot(x, center, color=BAND_COLOR, linewidth=1.9, label=center_label)
        ax.set_ylabel(publication_variable_label(variable, difference=difference))
        ax.legend(frameon=False, fontsize=8, loc="best")
        _style_axis(ax, difference=difference)
        if idx >= 2:
            ax.set_xlabel("Time [s]")

    _finalize_panel_figure(fig, variables=variables, provenance_rows=provenance_rows)
    return fig


def _same_value(series: pd.Series, value: Any) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series == bool(value)
    numeric = pd.to_numeric(series, errors="coerce")
    try:
        target = float(value)
    except (TypeError, ValueError):
        return series.astype(str) == str(value)
    if numeric.notna().any():
        return pd.Series(np.isclose(numeric.to_numpy(dtype=float), target, rtol=1.0e-9, atol=1.0e-15), index=series.index)
    return series.astype(str) == str(value)


def one_factor_sensitivity_slices(
    metrics_df: pd.DataFrame,
    *,
    parameters: Sequence[str],
    reference_values: Mapping[str, Any],
    all_parameter_columns: Sequence[str],
) -> Dict[str, pd.DataFrame]:
    """Condition every non-x parameter at a reference value for each OFAT panel."""
    slices: Dict[str, pd.DataFrame] = {}
    for x_parameter in parameters:
        subset = metrics_df.copy()
        for parameter in all_parameter_columns:
            if parameter == x_parameter or parameter not in subset.columns:
                continue
            if parameter not in reference_values:
                continue
            subset = subset[_same_value(subset[parameter], reference_values[parameter])]
        slices[x_parameter] = subset.reset_index(drop=True)
    return slices


def plot_one_factor_sensitivity_panel(
    metrics_df: pd.DataFrame,
    *,
    parameters: Sequence[str],
    all_parameter_columns: Sequence[str],
    reference_values: Mapping[str, Any],
    statistic: str,
    variable: str,
    provenance_rows: Sequence[Mapping[str, Any]] | None = None,
):
    """Plot up to three one-factor-at-a-time sensitivity slices."""
    parameters = list(parameters)[:3]
    n_panels = max(len(parameters), 1)
    fig, axes = plt.subplots(1, n_panels, figsize=(4.1 * n_panels, 4.2), squeeze=False, sharey=True)
    axes_flat = axes.ravel()
    slices = one_factor_sensitivity_slices(
        metrics_df,
        parameters=parameters,
        reference_values=reference_values,
        all_parameter_columns=all_parameter_columns,
    )
    fig.suptitle("One-factor-at-a-time seeding sensitivity", fontsize=12.5, fontweight="semibold")

    for idx, (ax, parameter) in enumerate(zip(axes_flat, parameters)):
        subset = slices[parameter]
        if subset.empty or parameter not in subset.columns or statistic not in subset.columns:
            ax.text(0.5, 0.5, "No conditioned cases", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(f"({chr(97 + idx)}) {publication_parameter_label(parameter)}", fontsize=9.5, loc="left")
            _style_axis(ax, difference=variable.endswith("_diff"))
            continue

        plot_df = subset.dropna(subset=[parameter, statistic]).copy()
        plot_df["_x"] = _parameter_values(plot_df[parameter], parameter)
        plot_df = plot_df.sort_values("_x")
        ax.plot(plot_df["_x"], plot_df[statistic], color=CURVE_COLORS[idx], marker="o", linewidth=1.7, markersize=4.5)
        ax.set_title(f"({chr(97 + idx)}) {parameter.replace('param.', '')}", fontsize=9.5, loc="left")
        ax.set_xlabel(publication_parameter_label(parameter))
        if idx == 0:
            ax.set_ylabel(publication_variable_label(variable, difference=variable.endswith("_diff")) + f" · {statistic}")
        _style_axis(ax, difference=variable.endswith("_diff"))

    reference_parts = []
    for parameter in all_parameter_columns:
        if parameter in reference_values:
            reference_parts.append(f"{parameter.replace('param.', '')}={reference_values[parameter]}")
    fig.text(
        0.01,
        0.050,
        "Reference condition: " + ", ".join(reference_parts) + ". Each panel varies only its x-axis parameter.",
        ha="left",
        va="bottom",
        fontsize=7.2,
        color="#3F3F3F",
    )
    _finalize_panel_figure(
        fig,
        variables=[variable],
        provenance_rows=provenance_rows,
        bottom=0.18,
    )
    return fig


def _condition_label(label: str) -> str:
    parts = [part.strip() for part in str(label).split(",")]
    kept = []
    for part in parts:
        if re.fullmatch(r"c\d+", part):
            continue
        if part.startswith("coll="):
            continue
        kept.append(part)
    return ", ".join(kept) or "reference condition"


def plot_collision_off_on_panel(
    off_overlay_df: pd.DataFrame,
    on_overlay_df: pd.DataFrame,
    *,
    variable: str,
    provenance_rows: Sequence[Mapping[str, Any]] | None = None,
    shaded_intervals: Sequence[tuple[float, float]] | None = None,
):
    """Plot matched collision-OFF and collision-ON sweep curves on shared y limits."""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), sharex=True, sharey=True)
    frames = [("Collision OFF", off_overlay_df), ("Collision ON", on_overlay_df)]
    all_labels = []
    for _, frame in frames:
        all_labels.extend(_condition_label(col) for col in frame.columns if col != "time_s")
    unique_labels = list(dict.fromkeys(all_labels))
    color_map = {label: CURVE_COLORS[idx % len(CURVE_COLORS)] for idx, label in enumerate(unique_labels)}

    handles_by_label: Dict[str, Any] = {}
    for idx, (title, frame) in enumerate(frames):
        ax = axes[idx]
        ax.set_title(f"({chr(97 + idx)}) {title}", fontsize=10, loc="left")
        _shade_intervals(ax, shaded_intervals)
        if frame.empty or "time_s" not in frame.columns:
            ax.text(0.5, 0.5, "No matched cases", ha="center", va="center", transform=ax.transAxes)
        else:
            x = pd.to_numeric(frame["time_s"], errors="coerce")
            for column in frame.columns:
                if column == "time_s":
                    continue
                label = _condition_label(column)
                (line,) = ax.plot(x, frame[column], color=color_map[label], linewidth=1.7, label=label)
                handles_by_label.setdefault(label, line)
        ax.set_xlabel("Time [s]")
        if idx == 0:
            ax.set_ylabel(publication_variable_label(variable, difference=variable.endswith("_diff")))
        _style_axis(ax, difference=variable.endswith("_diff"))

    if handles_by_label:
        fig.legend(
            list(handles_by_label.values()),
            list(handles_by_label.keys()),
            loc="lower center",
            bbox_to_anchor=(0.5, 0.095),
            ncol=min(3, len(handles_by_label)),
            frameon=False,
            fontsize=7.5,
        )
    fig.suptitle("Collision–coalescence sensitivity", fontsize=12.5, fontweight="semibold")
    _finalize_panel_figure(
        fig,
        variables=[variable],
        provenance_rows=provenance_rows,
        bottom=0.22 if handles_by_label else 0.15,
    )
    return fig


def _coerce_collision(value: Any) -> bool | None:
    if pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def matched_collision_cases(
    sweep_df: pd.DataFrame,
    *,
    collision_column: str = "param.microphysics.collision",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only parameter conditions that contain both collision OFF and ON cases."""
    if sweep_df.empty or collision_column not in sweep_df.columns:
        return pd.DataFrame(), pd.DataFrame()

    work = sweep_df.copy()
    work["_collision_state"] = work[collision_column].map(_coerce_collision)
    condition_columns = [
        col for col in work.columns if col.startswith("param.") and col != collision_column
    ]
    if condition_columns:
        grouped = work.groupby(condition_columns, dropna=False, sort=False)
    else:
        grouped = [((), work)]

    matched_indices: List[Any] = []
    summary_rows: List[Dict[str, Any]] = []
    for key, group in grouped:
        states = set(group["_collision_state"].dropna().tolist())
        matched = False in states and True in states
        if matched:
            matched_indices.extend(group.index.tolist())
        key_values = key if isinstance(key, tuple) else (key,)
        row = {col: value for col, value in zip(condition_columns, key_values)}
        row.update(
            {
                "has_collision_off": False in states,
                "has_collision_on": True in states,
                "matched": matched,
            }
        )
        summary_rows.append(row)

    matched_df = work.loc[matched_indices].drop(columns=["_collision_state"]).reset_index(drop=True)
    return matched_df, pd.DataFrame(summary_rows)

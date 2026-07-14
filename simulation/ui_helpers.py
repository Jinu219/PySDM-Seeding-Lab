from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st

from simulation.config import load_config, reset_config, save_config
from simulation.experiment_manager import scenario_options, update_scenario_config
from simulation.schema import FIELD_UNITS, schema_summary


CONFIG_PATH = Path("configs/default.yaml")


def load_working_config() -> Dict[str, Any]:
    """Load the working config used by the Streamlit app."""
    return load_config(CONFIG_PATH)


def save_working_config(config: Dict[str, Any]) -> None:
    """Save the working config used by the Streamlit app."""
    save_config(config, CONFIG_PATH)


def reset_working_config() -> Dict[str, Any]:
    """Reset the working config to the canonical default schema."""
    return reset_config(CONFIG_PATH)


def unit_label(section: str, field: str) -> str:
    """Return a readable unit suffix for a config field."""
    unit = FIELD_UNITS.get(section, {}).get(field, "")
    return f" [{unit}]" if unit else ""


def page_header(title: str, description: str | None = None) -> None:
    """Draw a consistent page header."""
    inject_responsive_css()
    st.title(title)
    if description:
        st.caption(description)


def config_actions(config: Dict[str, Any], save_label: str = "Save Settings") -> None:
    """
    Draw Save and Reset buttons.

    Settings can be saved either to the current working config or directly
    into a saved experiment scenario.
    """
    st.markdown("#### Save settings")
    options = scenario_options(include_working_config=True)
    labels = [item["label"] for item in options]
    target_col, note_col = st.columns([1.6, 1])
    with target_col:
        selected_label = st.selectbox(
            "Save target",
            labels,
            key=f"save_target_{save_label}",
        )
    with note_col:
        st.caption(
            "Current working config는 즉시 실행할 설정이며, scenario를 선택하면 해당 YAML에 이 페이지만 반영합니다."
        )
    selected = options[labels.index(selected_label)]

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button(save_label, use_container_width=True):
            if selected.get("is_working_config", False):
                save_working_config(config)
                st.success("Settings saved to configs/default.yaml")
            else:
                update_scenario_config(selected["path"], config=config)
                st.success(f"Settings saved to scenario: {selected['name']}")

    with col2:
        if st.button("Reset to Default", use_container_width=True):
            reset_working_config()
            st.warning("Configuration reset to default. Refresh the page to see reset values.")


def schema_expander() -> None:
    """Show the current schema summary in an expander."""
    with st.expander("Current configuration schema"):
        st.dataframe(schema_summary(), use_container_width=True)


def scenario_loader() -> Dict[str, str]:
    """Return available scenario config files."""
    return {
        "Current working config": "configs/default.yaml",
        "Marine clean cloud": "configs/marine.yaml",
        "Urban polluted cloud": "configs/urban.yaml",
    }


def inject_responsive_css() -> None:
    """Apply the shared compact research-dashboard visual system."""
    st.markdown(
        """
        <style>
        :root {
            --lab-ink: #17324d;
            --lab-muted: #607286;
            --lab-blue: #2563a7;
            --lab-border: rgba(71, 94, 119, 0.18);
            --lab-panel: rgba(248, 250, 252, 0.72);
        }

        .block-container {
            max-width: 80rem;
            padding-top: 1.35rem;
            padding-bottom: 3rem;
            padding-left: 1.6rem;
            padding-right: 1.6rem;
        }

        h1, h2, h3 {
            color: var(--lab-ink);
            letter-spacing: -0.018em;
        }
        h1 { margin-bottom: 0.25rem; }

        div[data-testid="stMetric"] {
            background: var(--lab-panel);
            border: 1px solid var(--lab-border);
            border-radius: 0.8rem;
            padding: 0.8rem 0.95rem;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.45rem;
            color: var(--lab-ink);
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--lab-border);
            border-radius: 0.85rem;
            background: var(--lab-panel);
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.65rem;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] {
            border-radius: 0.55rem !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input {
            min-height: 2.25rem;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
            border-radius: 0.58rem;
            min-height: 2.35rem;
            font-weight: 500;
        }

        div[data-testid="stAlert"] {
            border-radius: 0.7rem;
            padding-top: 0.65rem;
            padding-bottom: 0.65rem;
        }

        details[data-testid="stExpander"] {
            border: 1px solid var(--lab-border);
            border-radius: 0.7rem;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
            flex-wrap: wrap;
            border-bottom: 1px solid var(--lab-border);
        }
        .stTabs [data-baseweb="tab"] {
            white-space: nowrap;
            border-radius: 0.55rem 0.55rem 0 0;
            padding-left: 0.9rem;
            padding-right: 0.9rem;
        }

        .lab-hero {
            border: 1px solid var(--lab-border);
            border-radius: 1rem;
            padding: 1.5rem 1.65rem;
            margin: 0.55rem 0 1.15rem 0;
            background: linear-gradient(135deg, rgba(37,99,167,0.10), rgba(52,168,166,0.06));
        }
        .lab-hero h2 {
            margin: 0 0 0.45rem 0;
            font-size: 1.45rem;
        }
        .lab-hero p {
            margin: 0;
            color: var(--lab-muted);
            max-width: 58rem;
        }
        .lab-kicker {
            color: var(--lab-blue);
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .lab-step {
            border-left: 3px solid var(--lab-blue);
            padding: 0.35rem 0 0.35rem 0.75rem;
            margin: 0.3rem 0 0.75rem 0;
        }
        .lab-step strong { color: var(--lab-ink); }
        .lab-step span { color: var(--lab-muted); font-size: 0.9rem; }
        .lab-parameter-note {
            color: var(--lab-muted);
            font-size: 0.82rem;
            line-height: 1.35;
            margin-top: -0.25rem;
            margin-bottom: 0.45rem;
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --lab-ink: #e7eef7;
                --lab-muted: #a8b7c7;
                --lab-blue: #7ab5f0;
                --lab-border: rgba(198, 216, 235, 0.18);
                --lab-panel: rgba(27, 38, 50, 0.65);
            }
        }

        @media (max-width: 900px) {
            .block-container {
                padding-top: 0.8rem;
                padding-left: 0.9rem;
                padding-right: 0.9rem;
            }
            div[data-testid="stMetricValue"] { font-size: 1.2rem; }
            .lab-hero { padding: 1.05rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_badge(label: str, value: str) -> None:
    """Render a compact build/version badge."""
    st.caption(f"{label}: `{value}`")

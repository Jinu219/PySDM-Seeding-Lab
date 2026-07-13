from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st

from simulation.config import load_config, reset_config, save_config
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
    st.title(title)
    if description:
        st.caption(description)


def config_actions(config: Dict[str, Any], save_label: str = "Save Settings") -> None:
    """Draw Save and Reset buttons in a consistent layout."""
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button(save_label, use_container_width=True):
            save_working_config(config)
            st.success("Settings saved to configs/default.yaml")

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

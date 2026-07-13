from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

from simulation.config import load_config, save_config


SCENARIO_DIR = Path("experiments/scenarios")


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9가-힣_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "scenario"


def scenario_path(name: str) -> Path:
    """Return the YAML path for a scenario name."""
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)
    return SCENARIO_DIR / f"{_slugify(name)}.yaml"


def save_scenario(
    *,
    name: str,
    memo: str,
    config: Dict[str, Any],
    overwrite: bool = False,
) -> Path:
    """Save a configuration snapshot as a named experiment scenario."""
    path = scenario_path(name)

    if path.exists() and not overwrite:
        raise FileExistsError(f"Scenario already exists: {path}")

    payload = {
        "metadata": {
            "name": name.strip(),
            "slug": path.stem,
            "memo": memo.strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
        "config": config,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    return path


def list_scenarios() -> List[Dict[str, Any]]:
    """List saved scenarios."""
    SCENARIO_DIR.mkdir(parents=True, exist_ok=True)

    scenarios: List[Dict[str, Any]] = []
    for path in sorted(SCENARIO_DIR.glob("*.yaml")):
        payload = read_scenario(path)
        metadata = payload.get("metadata", {})
        scenarios.append(
            {
                "name": metadata.get("name", path.stem),
                "slug": metadata.get("slug", path.stem),
                "memo": metadata.get("memo", ""),
                "created_at": metadata.get("created_at", ""),
                "path": str(path),
            }
        )

    return scenarios


def read_scenario(path: str | Path) -> Dict[str, Any]:
    """Read a saved scenario YAML."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    payload.setdefault("metadata", {"name": path.stem, "slug": path.stem, "memo": ""})
    payload.setdefault("config", {})
    return payload


def load_scenario_config(path: str | Path) -> Dict[str, Any]:
    """Load only the config section from a scenario file."""
    return read_scenario(path).get("config", {})


def apply_scenario_to_working_config(path: str | Path, working_config_path: str | Path = "configs/default.yaml") -> Dict[str, Any]:
    """Apply a scenario config to configs/default.yaml."""
    cfg = load_scenario_config(path)
    save_config(cfg, working_config_path)
    return cfg


def scenario_table_rows() -> List[Dict[str, Any]]:
    """Return compact rows for Streamlit tables."""
    return list_scenarios()


def load_working_config(path: str | Path = "configs/default.yaml") -> Dict[str, Any]:
    """Small wrapper used by scenario pages."""
    return load_config(path)



def update_scenario_config(
    path: str | Path,
    *,
    config: Dict[str, Any],
    memo: str | None = None,
) -> Dict[str, Any]:
    """Update the config section of an existing scenario while preserving metadata."""
    path = Path(path)
    payload = read_scenario(path)
    metadata = payload.get("metadata", {})

    metadata["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if memo is not None:
        metadata["memo"] = memo.strip()

    payload["metadata"] = metadata
    payload["config"] = config

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    return payload


def scenario_options(include_working_config: bool = True) -> List[Dict[str, Any]]:
    """Return options for UI selectors."""
    options: List[Dict[str, Any]] = []
    if include_working_config:
        options.append(
            {
                "label": "Current working config",
                "name": "Current working config",
                "path": "",
                "memo": "",
                "is_working_config": True,
            }
        )

    for item in list_scenarios():
        label = f"{item['name']} · {item.get('created_at', '')}"
        memo = item.get("memo", "")
        if memo:
            label += f" · {memo[:42]}"
        options.append(
            {
                **item,
                "label": label,
                "is_working_config": False,
            }
        )

    return options



def scenario_slug_from_path(path: str | Path) -> str:
    """Return scenario slug from a scenario YAML path."""
    payload = read_scenario(path)
    metadata = payload.get("metadata", {})
    return str(metadata.get("slug") or Path(path).stem)


def scenario_name_from_path(path: str | Path) -> str:
    """Return human-readable scenario name from a scenario YAML path."""
    payload = read_scenario(path)
    metadata = payload.get("metadata", {})
    return str(metadata.get("name") or Path(path).stem)


def apply_scenario_identity(config: Dict[str, Any], path: str | Path) -> Dict[str, Any]:
    """
    Return a config copy whose experiment identity is tied to the scenario.

    This makes result directories and dashboard labels use the scenario name
    instead of the generic default experiment name.
    """
    cfg = dict(config)
    cfg = yaml.safe_load(yaml.safe_dump(config, sort_keys=False, allow_unicode=True)) or {}

    payload = read_scenario(path)
    metadata = payload.get("metadata", {})
    slug = str(metadata.get("slug") or Path(path).stem)
    name = str(metadata.get("name") or slug)
    memo = str(metadata.get("memo") or "")

    cfg.setdefault("experiment", {})
    cfg["experiment"]["name"] = slug
    cfg["experiment"]["scenario_name"] = name
    cfg["experiment"]["scenario_slug"] = slug
    cfg["experiment"]["scenario_memo"] = memo

    cfg.setdefault("metadata", {})
    cfg["metadata"]["scenario_name"] = name
    cfg["metadata"]["scenario_slug"] = slug
    cfg["metadata"]["scenario_path"] = str(path)
    cfg["metadata"]["scenario_memo"] = memo

    return cfg

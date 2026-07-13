from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from simulation.schema import default_config, normalize_config


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load a YAML config and fill missing fields from the canonical schema."""
    path = Path(path)

    if not path.exists():
        return default_config()

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return normalize_config(data or {})


def save_config(config: Dict[str, Any], path: str | Path) -> None:
    """Save a config dictionary to YAML after applying schema defaults."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized = normalize_config(config)

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            normalized,
            f,
            sort_keys=False,
            allow_unicode=True,
        )


def reset_config(path: str | Path) -> Dict[str, Any]:
    """Reset a config file to the canonical default schema."""
    cfg = default_config()
    save_config(cfg, path)
    return cfg


def get_nested(config: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    """Read a nested value using a dotted key such as 'seeding.kappa'."""
    current: Any = config
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def set_nested(config: Dict[str, Any], dotted_key: str, value: Any) -> Dict[str, Any]:
    """Set a nested value using a dotted key and return the modified config."""
    current = config
    parts = dotted_key.split(".")

    for part in parts[:-1]:
        current = current.setdefault(part, {})

    current[parts[-1]] = value
    return config

from __future__ import annotations

"""Filesystem-safe naming rules for deeply nested simulation results."""

import hashlib
from pathlib import Path


WINDOWS_LEGACY_PATH_LIMIT = 260
DEFAULT_TOKEN_LENGTH = 48
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def filesystem_token(value: object, *, max_length: int = DEFAULT_TOKEN_LENGTH) -> str:
    """Return a stable path component, truncating long values with a hash suffix."""
    raw = str(value)
    cleaned = "".join(
        character if character.isalnum() or character in {"_", "-", "."} else "_"
        for character in raw
    ).strip(" .")
    cleaned = cleaned or "result"
    # Windows also reserves device names when an extension is present
    # (for example, ``CON.txt``), so inspect the portion before the first dot.
    if cleaned.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    if len(cleaned) <= max_length:
        return cleaned
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    prefix_length = max(1, max_length - len(digest) - 1)
    return f"{cleaned[:prefix_length]}_{digest}"


def resolve_result_directory(
    output_dir: Path,
    run_id: str,
    directory_name: str | None = None,
) -> Path:
    """Resolve a result directory while keeping optional nested names compact."""
    name = filesystem_token(directory_name if directory_name is not None else run_id, max_length=72)
    return Path(output_dir) / name


def path_character_count(path: Path) -> int:
    """Return the absolute path character count used by legacy Windows path checks."""
    return len(str(Path(path).resolve()))

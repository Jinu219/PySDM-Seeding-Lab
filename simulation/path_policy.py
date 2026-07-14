from __future__ import annotations

"""Filesystem-safe naming rules for deeply nested simulation results."""

import hashlib
from pathlib import Path


WINDOWS_LEGACY_PATH_LIMIT = 260
WINDOWS_PORTABLE_PATH_LIMIT = 240
DEFAULT_TOKEN_LENGTH = 48
MIN_HASHED_TOKEN_LENGTH = 10

# Keep enough space below each result directory for the deepest artifact written by
# that workflow.  The 240-character ceiling is intentionally stricter than MAX_PATH
# so results remain portable to Windows tools that still reserve characters for
# separators or a terminating null byte.
SINGLE_RESULT_DESCENDANT_RESERVE = 40
COMPARISON_RESULT_DESCENDANT_RESERVE = 56
ENSEMBLE_RESULT_DESCENDANT_RESERVE = 88
SWEEP_RESULT_DESCENDANT_RESERVE = 104
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class ResultPathBudgetError(ValueError):
    """Raised before execution when a portable result path cannot be constructed."""


def filesystem_token(value: object, *, max_length: int = DEFAULT_TOKEN_LENGTH) -> str:
    """Return a stable path component, truncating long values with a hash suffix."""
    if max_length < 1:
        raise ValueError("max_length must be positive")
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
    if max_length < MIN_HASHED_TOKEN_LENGTH:
        raise ValueError(
            f"max_length must be at least {MIN_HASHED_TOKEN_LENGTH} when a token "
            "needs a stable hash suffix"
        )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    prefix_length = max(1, max_length - len(digest) - 1)
    return f"{cleaned[:prefix_length]}_{digest}"


def resolve_result_directory(
    output_dir: Path,
    run_id: str,
    directory_name: str | None = None,
    *,
    descendant_reserve: int = SINGLE_RESULT_DESCENDANT_RESERVE,
) -> Path:
    """Resolve a portable result directory using an absolute-path length budget.

    ``descendant_reserve`` represents the longest relative artifact path that the
    workflow may create below the returned directory.  Long scenario/run names are
    shortened with a stable hash.  If the output root itself is already too deep,
    fail before a model run starts instead of producing an empty/partial result.
    """
    output_dir = Path(output_dir)
    if descendant_reserve < 0:
        raise ValueError("descendant_reserve must be non-negative")

    parent_length = path_character_count(output_dir)
    available_length = (
        WINDOWS_PORTABLE_PATH_LIMIT
        - parent_length
        - 1  # separator before the new component
        - descendant_reserve
    )
    if available_length < 1:
        raise ResultPathBudgetError(
            "The selected output directory is too deep for a portable PySDM result: "
            f"{output_dir.resolve()} ({parent_length} characters). The workflow needs "
            f"at least {descendant_reserve} characters for nested artifacts under the "
            f"{WINDOWS_PORTABLE_PATH_LIMIT}-character safety limit. Choose a shorter "
            "output root such as C:\\pysdm_results."
        )

    requested_name = directory_name if directory_name is not None else run_id
    try:
        name = filesystem_token(requested_name, max_length=min(72, available_length))
    except ValueError as exc:
        raise ResultPathBudgetError(
            "The selected output directory leaves too little room to shorten the "
            f"requested result name safely ({available_length} characters available). "
            "Choose a shorter output root such as C:\\pysdm_results."
        ) from exc
    result_dir = output_dir / name
    projected_length = path_character_count(result_dir) + descendant_reserve
    if projected_length > WINDOWS_PORTABLE_PATH_LIMIT:
        raise ResultPathBudgetError(
            f"Result path budget exceeded unexpectedly: projected length "
            f"{projected_length} > {WINDOWS_PORTABLE_PATH_LIMIT}."
        )
    return result_dir


def path_character_count(path: Path) -> int:
    """Return the absolute path character count used by legacy Windows path checks."""
    return len(str(Path(path).resolve()))

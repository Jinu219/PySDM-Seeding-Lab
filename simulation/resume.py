from __future__ import annotations

"""Stable configuration identity for safe in-place experiment resumption."""

import copy
import hashlib
import json
from typing import Any, Dict

from simulation.schema import normalize_config


RESUME_BUILD_ID = "qualification-resume-v1-20260720"


class ResumeConfigurationError(ValueError):
    """Raised before execution when a stored result does not match the request."""


def execution_config_payload(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return the normalized model-execution contract used for resume checks.

    ``qualification`` contains timestamps, runtime estimates, evidence summaries,
    and resume history.  Those fields may change without changing a model run, so
    they are intentionally excluded.  The actual model, sweep, ensemble, seed,
    diagnostic, and worker settings remain part of the fingerprint.
    """

    payload = copy.deepcopy(normalize_config(config))
    payload.pop("qualification", None)
    return payload


def execution_config_fingerprint(config: Dict[str, Any]) -> str:
    """Return a deterministic SHA-256 identity for a normalized run contract."""

    canonical = json.dumps(
        execution_config_payload(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assert_resume_config_matches(
    stored_config: Dict[str, Any],
    requested_config: Dict[str, Any],
) -> str:
    """Reject an in-place resume unless both execution contracts are identical."""

    stored_fingerprint = execution_config_fingerprint(stored_config)
    requested_fingerprint = execution_config_fingerprint(requested_config)
    if stored_fingerprint != requested_fingerprint:
        raise ResumeConfigurationError(
            "Resume configuration does not match the stored experiment. "
            f"stored={stored_fingerprint[:12]} requested={requested_fingerprint[:12]}. "
            "Use the original configuration or start a new qualification result."
        )
    return requested_fingerprint

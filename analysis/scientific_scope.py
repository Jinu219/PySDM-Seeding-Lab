from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_CLAIM_STATUSES = {
    "supported",
    "descriptive_only",
    "operational_only",
    "unsupported",
}


def load_scientific_scope(path: str | Path) -> dict[str, Any]:
    scope_path = Path(path)
    try:
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid scientific-scope JSON: {exc}") from exc
    if not isinstance(scope, dict):
        raise ValueError("Scientific scope must contain a JSON object.")
    return scope


def validate_scientific_scope(
    scope: dict[str, Any],
    *,
    project_root: str | Path,
) -> None:
    root = Path(project_root)
    if scope.get("schema_version") != 1:
        raise ValueError("Scientific scope schema_version must be 1.")
    if scope.get("release") != "v1.0.0":
        raise ValueError("Scientific scope must target v1.0.0.")
    if scope.get("release_classification") != "research_workflow_release":
        raise ValueError("v1.0 must remain classified as a research workflow release.")
    claims = scope.get("claims")
    if not isinstance(claims, list) or not claims:
        raise ValueError("Scientific scope requires claims.")
    if not all(isinstance(claim, dict) for claim in claims):
        raise ValueError("Every scientific claim must be an object.")
    claim_ids = [str(claim.get("id", "")) for claim in claims]
    if any(not claim_id for claim_id in claim_ids):
        raise ValueError("Every scientific claim requires a non-empty id.")
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("Scientific claim ids must be unique.")
    if scope.get("required_claim_order") != claim_ids:
        raise ValueError("required_claim_order must exactly match the claims.")

    for claim in claims:
        claim_id = claim["id"]
        status = claim.get("status")
        if status not in ALLOWED_CLAIM_STATUSES:
            raise ValueError(f"Claim {claim_id!r} has unsupported status {status!r}.")
        if not str(claim.get("statement", "")).strip():
            raise ValueError(f"Claim {claim_id!r} requires a statement.")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"Claim {claim_id!r} requires evidence paths.")
        missing_evidence = [path for path in evidence if not (root / path).is_file()]
        if missing_evidence:
            raise ValueError(
                f"Claim {claim_id!r} references missing evidence: {missing_evidence}"
            )
        if status == "supported" and not str(claim.get("scope", "")).strip():
            raise ValueError(f"Supported claim {claim_id!r} requires an explicit scope.")
        if status in {"unsupported", "descriptive_only"} and not str(
            claim.get("limitation", "")
        ).strip():
            raise ValueError(f"Claim {claim_id!r} requires an explicit limitation.")
        if status == "operational_only" and not str(
            claim.get("sensitivity", "")
        ).strip():
            raise ValueError(
                f"Operational-only claim {claim_id!r} requires sensitivity text."
            )


def summarize_scientific_scope(scope: dict[str, Any]) -> dict[str, Any]:
    counts = {status: 0 for status in sorted(ALLOWED_CLAIM_STATUSES)}
    for claim in scope["claims"]:
        counts[claim["status"]] += 1
    return {
        "release": scope["release"],
        "release_classification": scope["release_classification"],
        "claim_count": len(scope["claims"]),
        "status_counts": counts,
        "supported_claim_ids": [
            claim["id"] for claim in scope["claims"] if claim["status"] == "supported"
        ],
        "unsupported_claim_ids": [
            claim["id"]
            for claim in scope["claims"]
            if claim["status"] == "unsupported"
        ],
    }

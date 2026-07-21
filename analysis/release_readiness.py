from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_GATE_STATUSES = {"complete", "pending", "blocked"}
ALLOWED_OVERALL_STATUSES = {"blocked", "in_progress", "ready"}


def load_release_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid release manifest JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Release manifest must contain a JSON object.")
    return manifest


def validate_release_manifest(
    manifest: dict[str, Any],
    *,
    project_root: str | Path,
) -> None:
    root = Path(project_root)
    if manifest.get("schema_version") != 1:
        raise ValueError("Release manifest schema_version must be 1.")
    if not str(manifest.get("release", "")).startswith("v"):
        raise ValueError("Release manifest release must be a v-prefixed version.")

    overall_status = manifest.get("overall_status")
    if overall_status not in ALLOWED_OVERALL_STATUSES:
        raise ValueError(f"Unsupported overall_status: {overall_status!r}")

    merge_policy = manifest.get("merge_policy")
    if not isinstance(merge_policy, dict):
        raise ValueError("Release manifest requires merge_policy.")
    required_merge_policy = {
        "source_branch",
        "target_branch",
        "blog_checkpoint",
        "tag_after_merge",
    }
    missing_policy = sorted(required_merge_policy - set(merge_policy))
    if missing_policy:
        raise ValueError(f"merge_policy is missing fields: {missing_policy}")
    if merge_policy["blog_checkpoint"] != "before_merge":
        raise ValueError("The release blog checkpoint must remain before_merge.")

    gates = manifest.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ValueError("Release manifest requires at least one gate.")
    if not all(isinstance(gate, dict) for gate in gates):
        raise ValueError("Every release gate must be an object.")

    gate_ids = [str(gate.get("id", "")) for gate in gates]
    if any(not gate_id for gate_id in gate_ids):
        raise ValueError("Every release gate requires a non-empty id.")
    if len(gate_ids) != len(set(gate_ids)):
        raise ValueError("Release gate ids must be unique.")

    required_order = manifest.get("required_gate_order")
    required_ids = [
        gate["id"] for gate in gates if gate.get("required") is True
    ]
    if required_order != required_ids:
        raise ValueError(
            "required_gate_order must exactly match required gates in execution order."
        )

    gates_by_id = {gate["id"]: gate for gate in gates}
    gate_positions = {gate_id: index for index, gate_id in enumerate(gate_ids)}
    for gate in gates:
        status = gate.get("status")
        if status not in ALLOWED_GATE_STATUSES:
            raise ValueError(
                f"Gate {gate['id']!r} has unsupported status {status!r}."
            )
        dependencies = gate.get("depends_on")
        if not isinstance(dependencies, list):
            raise ValueError(f"Gate {gate['id']!r} requires depends_on list.")
        unknown_dependencies = sorted(set(dependencies) - set(gate_ids))
        if unknown_dependencies:
            raise ValueError(
                f"Gate {gate['id']!r} has unknown dependencies: "
                f"{unknown_dependencies}"
            )
        if gate["id"] in dependencies:
            raise ValueError(f"Gate {gate['id']!r} cannot depend on itself.")
        out_of_order_dependencies = [
            dependency
            for dependency in dependencies
            if gate_positions[dependency] >= gate_positions[gate["id"]]
        ]
        if out_of_order_dependencies:
            raise ValueError(
                f"Gate {gate['id']!r} dependencies must appear earlier: "
                f"{out_of_order_dependencies}"
            )
        if status == "blocked" and not str(gate.get("blocker", "")).strip():
            raise ValueError(f"Blocked gate {gate['id']!r} requires blocker text.")
        if status == "complete":
            incomplete_dependencies = [
                dependency
                for dependency in dependencies
                if gates_by_id[dependency].get("status") != "complete"
            ]
            if incomplete_dependencies:
                raise ValueError(
                    f"Complete gate {gate['id']!r} has incomplete dependencies: "
                    f"{incomplete_dependencies}"
                )
            evidence = gate.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(
                    f"Complete gate {gate['id']!r} requires evidence paths."
                )
            missing_evidence = [
                path for path in evidence if not (root / path).is_file()
            ]
            if missing_evidence:
                raise ValueError(
                    f"Gate {gate['id']!r} references missing evidence: "
                    f"{missing_evidence}"
                )

    required_complete = all(
        gates_by_id[gate_id]["status"] == "complete"
        for gate_id in required_order
    )
    if overall_status == "ready" and not required_complete:
        raise ValueError("overall_status cannot be ready while a required gate is open.")
    if overall_status != "ready" and required_complete:
        raise ValueError("overall_status must be ready when every required gate is complete.")
    blocked_required = any(
        gates_by_id[gate_id]["status"] == "blocked" for gate_id in required_order
    )
    if overall_status == "blocked" and not blocked_required:
        raise ValueError("overall_status blocked requires a blocked required gate.")
    if overall_status == "in_progress" and blocked_required:
        raise ValueError("overall_status in_progress cannot contain a blocked required gate.")


def build_release_readiness_report(manifest: dict[str, Any]) -> dict[str, Any]:
    gates = manifest["gates"]
    required = [gate for gate in gates if gate["required"]]
    completed = [gate["id"] for gate in required if gate["status"] == "complete"]
    blocked = [gate["id"] for gate in required if gate["status"] == "blocked"]
    pending = [gate["id"] for gate in required if gate["status"] == "pending"]
    ready = len(completed) == len(required)
    next_gate = next(
        (gate["id"] for gate in required if gate["status"] != "complete"),
        None,
    )
    return {
        "release": manifest["release"],
        "ready": ready,
        "overall_status": manifest["overall_status"],
        "required_gate_count": len(required),
        "completed_gate_count": len(completed),
        "completed_gates": completed,
        "blocked_gates": blocked,
        "pending_gates": pending,
        "next_gate": next_gate,
        "merge_policy": manifest["merge_policy"],
    }

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.release_readiness import (  # noqa: E402
    build_release_readiness_report,
    load_release_manifest,
    validate_release_manifest,
)


DEFAULT_MANIFEST = PROJECT_ROOT / "release" / "v1.0.0.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and report the finite v1 release gate."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Release manifest path (default: release/v1.0.0.json).",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Return success for a valid but not-yet-ready release manifest.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the readiness report as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_release_manifest(args.manifest)
    validate_release_manifest(manifest, project_root=PROJECT_ROOT)
    report = build_release_readiness_report(manifest)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"{report['release']} readiness: "
            f"{report['completed_gate_count']}/{report['required_gate_count']} "
            "required gates complete"
        )
        print(f"Overall status: {report['overall_status']}")
        if report["next_gate"]:
            print(f"Next gate: {report['next_gate']}")
        if report["blocked_gates"]:
            print("Blocked gates: " + ", ".join(report["blocked_gates"]))
        policy = report["merge_policy"]
        print(
            "Merge checkpoint: "
            f"{policy['source_branch']} -> {policy['target_branch']} "
            f"({policy['blog_checkpoint'].replace('_', ' ')})"
        )

    if report["ready"] or args.allow_incomplete:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

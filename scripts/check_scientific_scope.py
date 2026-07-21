from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.scientific_scope import (  # noqa: E402
    load_scientific_scope,
    summarize_scientific_scope,
    validate_scientific_scope,
)


DEFAULT_SCOPE = PROJECT_ROOT / "release" / "v1_scientific_scope.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the evidence-bounded v1.0 scientific claim scope."
    )
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    scope = load_scientific_scope(args.scope)
    validate_scientific_scope(scope, project_root=PROJECT_ROOT)
    summary = summarize_scientific_scope(scope)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        counts = summary["status_counts"]
        print(
            f"{summary['release']} scientific scope: {summary['claim_count']} claims; "
            f"{counts['supported']} supported, {counts['descriptive_only']} "
            f"descriptive only, {counts['operational_only']} operational only, "
            f"{counts['unsupported']} unsupported"
        )
        print(f"Release classification: {summary['release_classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

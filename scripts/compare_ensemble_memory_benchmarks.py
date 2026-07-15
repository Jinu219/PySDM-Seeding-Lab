from __future__ import annotations

"""Build compact, machine-readable A/B evidence from two ensemble benchmarks."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.resource_monitor import compare_ensemble_memory_benchmarks


def _read_evidence(path: Path) -> Dict[str, Any]:
    evidence_path = path / "ensemble_benchmark.json" if path.is_dir() else path
    return json.loads(evidence_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare matched ensemble benchmark results without and with explicit GC."
    )
    parser.add_argument("--baseline", required=True, help="Baseline result directory or JSON")
    parser.add_argument(
        "--explicit-gc",
        required=True,
        help="Explicit-GC result directory or ensemble_benchmark.json",
    )
    parser.add_argument("--output", required=True, help="Destination comparison JSON")
    args = parser.parse_args()

    baseline_path = Path(args.baseline).resolve()
    gc_path = Path(args.explicit_gc).resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    comparison = compare_ensemble_memory_benchmarks(
        _read_evidence(baseline_path),
        _read_evidence(gc_path),
    )
    comparison["source_results"] = {
        "baseline": baseline_path.name,
        "explicit_gc": gc_path.name,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

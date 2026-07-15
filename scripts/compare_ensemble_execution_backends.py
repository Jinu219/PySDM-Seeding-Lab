from __future__ import annotations

"""Build compact A/B evidence for in-process versus subprocess ensembles."""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.resource_monitor import compare_ensemble_execution_backends


def _load_evidence(path_or_result: str) -> dict:
    path = Path(path_or_result)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if path.is_dir():
        path = path / "ensemble_benchmark.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare matched in-process and subprocess ensemble benchmarks."
    )
    parser.add_argument("--in-process", required=True)
    parser.add_argument("--subprocess", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    comparison = compare_ensemble_execution_backends(
        _load_evidence(args.in_process),
        _load_evidence(args.subprocess),
    )
    rendered = json.dumps(comparison, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

from __future__ import annotations

"""Query or download ARM NetCDF files without putting credentials in arguments."""

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.arm_live import download_arm_files, query_arm_file_names  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query ARM Live and optionally download matching NetCDF files."
    )
    parser.add_argument("--datastream", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "arm_ena_observations" / "source",
    )
    args = parser.parse_args()
    user_id = os.environ.get("ARM_USER_ID", "")
    access_token = os.environ.get("ARM_ACCESS_TOKEN", "")
    if not user_id or not access_token:
        parser.error(
            "Set ARM_USER_ID and ARM_ACCESS_TOKEN environment variables. "
            "Credentials are intentionally not accepted as command-line arguments."
        )
    files = query_arm_file_names(
        user_id=user_id,
        access_token=access_token,
        datastream=args.datastream,
        start=args.start,
        end=args.end,
    )
    print(json.dumps({"file_count": len(files), "files": files}, indent=2))
    if args.download:
        records = download_arm_files(
            files,
            user_id=user_id,
            access_token=access_token,
            output_dir=args.output_dir,
        )
        print(json.dumps({"downloaded": records}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

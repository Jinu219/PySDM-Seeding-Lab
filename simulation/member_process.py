from __future__ import annotations

"""Run one ensemble member in an isolated Python process.

The parent ensemble runner uses this module as both a subprocess launcher and a
``python -m`` entry point.  Keeping the child process contract here makes the
isolation boundary explicit and leaves durable config/log/status artifacts for
failed members.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml


MEMBER_PROCESS_BUILD_ID = "ensemble-member-process-v1-20260715"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    import psutil
except ImportError:  # pragma: no cover - only minimal installations lack psutil
    psutil = None


class MemberProcessExecutionError(RuntimeError):
    """Raised when an isolated member exits without a usable result."""

    def __init__(
        self,
        message: str,
        *,
        telemetry: Dict[str, Any],
        status: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.telemetry = dict(telemetry)
        self.status = dict(status or {})


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _process_tree_rss(process: Any) -> int | None:
    if process is None:
        return None
    try:
        processes = [process, *process.children(recursive=True)]
    except Exception:
        processes = [process]

    total = 0
    sampled = 0
    for item in processes:
        try:
            total += int(item.memory_info().rss)
            sampled += 1
        except Exception:
            continue
    return int(total) if sampled else None


def run_member_subprocess(
    member_config: Dict[str, Any],
    member_parent: Path,
    *,
    mode: str,
    sample_interval_seconds: float = 0.05,
) -> tuple[Path, Dict[str, Any]]:
    """Execute one normalized, ensemble-disabled config in a child process."""
    member_parent = Path(member_parent).resolve()
    member_parent.mkdir(parents=True, exist_ok=True)
    result_dir_name = "comparison" if mode == "control_vs_seeding" else "single"
    config_path = member_parent / "isolated_member_config.yaml"
    stdout_path = member_parent / "isolated_member_stdout.log"
    stderr_path = member_parent / "isolated_member_stderr.log"
    status_path = member_parent / "isolated_member_status.json"
    config_path.write_text(
        yaml.safe_dump(member_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    command = [
        sys.executable,
        "-m",
        "simulation.member_process",
        "--config",
        str(config_path),
        "--output-dir",
        str(member_parent),
        "--result-dir-name",
        result_dir_name,
        "--status-file",
        str(status_path),
    ]
    creationflags = (
        int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    )
    started = time.perf_counter()
    peak_tree_rss = None
    sample_count = 0
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        child = subprocess.Popen(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
        )
        monitored_process = psutil.Process(child.pid) if psutil is not None else None
        while True:
            rss = _process_tree_rss(monitored_process)
            if rss is not None:
                peak_tree_rss = max(int(peak_tree_rss or 0), int(rss))
                sample_count += 1
            return_code = child.poll()
            if return_code is not None:
                break
            time.sleep(max(0.005, float(sample_interval_seconds)))

    elapsed_seconds = time.perf_counter() - started
    status: Dict[str, Any] = {}
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            status = {}

    telemetry = {
        "member_process_build_id": MEMBER_PROCESS_BUILD_ID,
        "member_process_elapsed_seconds": float(elapsed_seconds),
        "member_process_peak_tree_rss_bytes": peak_tree_rss,
        "member_process_rss_samples": int(sample_count),
        "member_process_return_code": int(return_code),
        "member_process_config": config_path.name,
        "member_process_stdout": stdout_path.name,
        "member_process_stderr": stderr_path.name,
        "member_process_status": status_path.name,
    }

    result_dir_text = status.get("result_dir")
    result_dir = (
        Path(result_dir_text)
        if result_dir_text
        else member_parent / result_dir_name
    )
    if return_code == 0 and status.get("success") is True and result_dir.exists():
        return result_dir, telemetry

    stderr_tail = ""
    try:
        stderr_tail = stderr_path.read_text(encoding="utf-8")[-2000:].strip()
    except OSError:
        pass
    status_error = str(status.get("error_message") or status.get("error") or "").strip()
    detail = status_error or stderr_tail or "child exited without a success status"
    raise MemberProcessExecutionError(
        f"Isolated ensemble member failed with exit code {return_code}: {detail}",
        telemetry=telemetry,
        status=status,
    )


def _child_main(args: argparse.Namespace) -> int:
    status_path = Path(args.status_file).resolve()
    try:
        config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
        if config.get("ensemble", {}).get("enabled", False):
            raise ValueError("Isolated member config must have ensemble.enabled=false.")

        # Imported only in the child entry point to avoid a runner/module cycle.
        from simulation.runner import run_experiment

        result_dir = run_experiment(
            config,
            Path(args.output_dir),
            result_dir_name=str(args.result_dir_name),
        )
        _write_json(
            status_path,
            {
                "build_id": MEMBER_PROCESS_BUILD_ID,
                "success": True,
                "result_dir": str(result_dir.resolve()),
            },
        )
        return 0
    except Exception as exc:
        result_dir = getattr(exc, "result_dir", None)
        _write_json(
            status_path,
            {
                "build_id": MEMBER_PROCESS_BUILD_ID,
                "success": False,
                "result_dir": str(Path(result_dir).resolve()) if result_dir else "",
                "error": repr(exc),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "error_errno": getattr(exc, "errno", None),
                "error_winerror": getattr(exc, "winerror", None),
            },
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one isolated ensemble member.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--result-dir-name", choices=["single", "comparison"], required=True)
    parser.add_argument("--status-file", required=True)
    return _child_main(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

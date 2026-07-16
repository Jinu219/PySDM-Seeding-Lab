from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from simulation.run_plan import estimate_run_plan
from simulation.schema import normalize_config


JOB_SCHEMA_VERSION = 1
DEFAULT_JOBS_DIRECTORY = Path(".runtime") / "jobs"
TERMINAL_JOB_STATES = {"succeeded", "failed"}
_LOCAL_PROCESSES: Dict[int, subprocess.Popen] = {}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def jobs_root(project_root: Path | str = ".") -> Path:
    return Path(project_root).resolve() / DEFAULT_JOBS_DIRECTORY


def job_status_path(job_dir: Path | str) -> Path:
    return Path(job_dir) / "status.json"


def read_background_job(job_dir: Path | str) -> Dict[str, Any]:
    path = job_status_path(job_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    pid = payload.get("pid")
    if payload.get("state") in TERMINAL_JOB_STATES and isinstance(pid, int):
        process = _LOCAL_PROCESSES.get(pid)
        if process is not None:
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
            if process.poll() is not None:
                _LOCAL_PROCESSES.pop(pid, None)
    return payload


def _update_background_job(job_dir: Path, **updates: Any) -> Dict[str, Any]:
    payload = read_background_job(job_dir)
    payload.update(updates)
    _atomic_write_json(job_status_path(job_dir), payload)
    return payload


def list_background_jobs(
    project_root: Path | str = ".",
    *,
    limit: int = 50,
) -> list[Dict[str, Any]]:
    root = jobs_root(project_root)
    if not root.exists():
        return []
    records = []
    for directory in sorted(root.iterdir(), reverse=True):
        if not directory.is_dir():
            continue
        record = read_background_job(directory)
        if record:
            record["job_dir"] = str(directory)
            records.append(record)
        if len(records) >= max(int(limit), 1):
            break
    return records


def _job_id(experiment_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = "".join(
        char.lower() if char.isalnum() else "_" for char in experiment_name
    ).strip("_")[:32]
    safe_name = safe_name or "experiment"
    return f"{timestamp}_{safe_name}_{uuid.uuid4().hex[:8]}"


def submit_background_job(
    config: Dict[str, Any],
    *,
    project_root: Path | str = ".",
) -> Dict[str, Any]:
    """Snapshot a config and launch a detached worker independent of Streamlit."""
    root = Path(project_root).resolve()
    cfg = normalize_config(config)
    experiment_name = str(cfg.get("experiment", {}).get("name", "experiment"))
    job_id = _job_id(experiment_name)
    job_dir = jobs_root(root) / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    config_path = job_dir / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log_path = job_dir / "worker.log"
    plan = estimate_run_plan(cfg, results_dir=root / "results")
    record: Dict[str, Any] = {
        "schema_version": JOB_SCHEMA_VERSION,
        "job_id": job_id,
        "state": "queued",
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "pid": None,
        "project_root": str(root),
        "config_path": str(config_path),
        "log_path": str(log_path),
        "experiment_name": experiment_name,
        "experiment_mode": str(cfg.get("experiment", {}).get("mode", "single")),
        "adapter": str(cfg.get("simulation", {}).get("adapter", "unknown")),
        "configured_workers": int(cfg.get("execution", {}).get("max_workers", 1)),
        "total_model_runs": int(plan.total_model_runs),
        "completed_model_runs": 0,
        "stage": "queued",
        "stage_current": 0,
        "stage_total": 1,
        "message": "Waiting for worker process",
        "result_dir": None,
        "error": None,
    }
    _atomic_write_json(job_status_path(job_dir), record)

    command = [
        sys.executable,
        "-m",
        "simulation.server_job_worker",
        "--job-dir",
        str(job_dir),
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    popen_kwargs: Dict[str, Any] = {
        "cwd": str(root),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        with log_path.open("ab", buffering=0) as log_file:
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                **popen_kwargs,
            )
        _LOCAL_PROCESSES[int(process.pid)] = process
        return _update_background_job(job_dir, pid=int(process.pid))
    except Exception as exc:
        return _update_background_job(
            job_dir,
            state="failed",
            finished_at=_now(),
            stage="launch_failed",
            message="Background worker could not be launched",
            error=repr(exc),
        )


def run_background_job(job_dir: Path | str) -> int:
    """Worker entry point. Return a process exit code after persisting status."""
    from simulation.config import load_config
    from simulation.runner import ExperimentExecutionError, run_experiment

    directory = Path(job_dir).resolve()
    record = read_background_job(directory)
    project_root = Path(record.get("project_root", ".")).resolve()
    config_path = Path(record.get("config_path", directory / "config.yaml"))
    config = load_config(config_path)
    output_dir = Path(config.get("output", {}).get("base_dir", "results"))
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    completed_model_runs = int(record.get("completed_model_runs", 0))

    def report_progress(stage: str, current: int, total: int, message: str) -> None:
        nonlocal completed_model_runs
        if stage == "model_run_complete":
            completed_model_runs += 1
        _update_background_job(
            directory,
            state="running",
            stage=stage,
            stage_current=int(current),
            stage_total=int(total),
            message=str(message),
            completed_model_runs=completed_model_runs,
        )

    _update_background_job(
        directory,
        state="running",
        started_at=_now(),
        pid=os.getpid(),
        stage="starting",
        message="Loading experiment configuration",
    )

    try:
        result_dir = run_experiment(
            config,
            output_dir=output_dir,
            progress_callback=report_progress,
        )
    except ExperimentExecutionError as exc:
        _update_background_job(
            directory,
            state="failed",
            finished_at=_now(),
            stage="failed",
            message="Experiment failed; diagnostic artifacts were preserved",
            result_dir=str(exc.result_dir),
            error=str(exc),
        )
        traceback.print_exc()
        return 1
    except Exception as exc:
        _update_background_job(
            directory,
            state="failed",
            finished_at=_now(),
            stage="failed",
            message="Experiment worker failed",
            error=repr(exc),
        )
        traceback.print_exc()
        return 1

    total_runs = int(record.get("total_model_runs", completed_model_runs))
    _update_background_job(
        directory,
        state="succeeded",
        finished_at=_now(),
        stage="finished",
        stage_current=1,
        stage_total=1,
        message="Experiment completed",
        completed_model_runs=max(completed_model_runs, total_runs),
        result_dir=str(result_dir),
        error=None,
    )
    return 0


def job_table_rows(records: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    rows = []
    for record in records:
        total = max(int(record.get("total_model_runs", 0)), 0)
        completed = max(int(record.get("completed_model_runs", 0)), 0)
        progress = 100.0 if record.get("state") == "succeeded" else (
            100.0 * min(completed, total) / total if total else 0.0
        )
        rows.append(
            {
                "job_id": record.get("job_id"),
                "state": record.get("state"),
                "experiment": record.get("experiment_name"),
                "adapter": record.get("adapter"),
                "workers": record.get("configured_workers", 1),
                "progress_percent": round(progress, 1),
                "model_runs": f"{completed}/{total}",
                "stage": record.get("stage"),
                "created_at": record.get("created_at"),
                "result_dir": record.get("result_dir"),
            }
        )
    return rows

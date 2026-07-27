from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from simulation.run_plan import estimate_run_plan
from simulation.schema import normalize_config


JOB_SCHEMA_VERSION = 1
DEFAULT_JOBS_DIRECTORY = Path(".runtime") / "jobs"
TERMINAL_JOB_STATES = {"succeeded", "failed", "cancelled"}
CONTROLLABLE_JOB_STATES = {"queued", "running", "paused"}
_LOCAL_PROCESSES: Dict[int, subprocess.Popen] = {}
ATOMIC_WRITE_MAX_ATTEMPTS = 8
ATOMIC_WRITE_RETRY_SECONDS = 0.025
LINUX_SIGSTOP = getattr(signal, "SIGSTOP", 19)
LINUX_SIGCONT = getattr(signal, "SIGCONT", 18)
PROGRESS_SAMPLE_LIMIT = 30


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _format_remaining_seconds(seconds: float) -> str:
    total_seconds = max(int(round(seconds)), 0)
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, remaining_seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"
    hours, remaining_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {remaining_minutes}m"
    days, remaining_hours = divmod(hours, 24)
    return f"{days}d {remaining_hours}h"


def estimate_job_remaining(
    record: Dict[str, Any],
    *,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Estimate wall-clock time remaining from recent aggregate job throughput."""
    state = str(record.get("state", "unknown"))
    terminal_labels = {
        "succeeded": "Done",
        "failed": "Failed",
        "cancelled": "Cancelled",
    }
    if state in terminal_labels:
        return {
            "label": terminal_labels[state],
            "seconds": 0.0 if state == "succeeded" else None,
            "finish_at": None,
            "basis": "terminal job state",
        }
    if state == "paused":
        return {
            "label": "Paused",
            "seconds": None,
            "finish_at": None,
            "basis": "ETA resumes after the job continues",
        }

    total = max(int(record.get("total_model_runs", 0)), 0)
    completed = max(int(record.get("completed_model_runs", 0)), 0)
    remaining_runs = max(total - completed, 0)
    if not total:
        return {
            "label": "Calculating…",
            "seconds": None,
            "finish_at": None,
            "basis": "total model-run count is unavailable",
        }
    if remaining_runs == 0:
        return {
            "label": "Finishing…",
            "seconds": 0.0,
            "finish_at": None,
            "basis": "all model runs are complete; final artifacts are being written",
        }

    current_time = now or datetime.now()
    current_epoch = current_time.timestamp()
    sample_points: list[tuple[float, int]] = []
    for sample in record.get("progress_samples", []):
        if not isinstance(sample, dict):
            continue
        sample_time = _parse_timestamp(sample.get("at"))
        sample_completed = sample.get("completed")
        if sample_time is None or not isinstance(sample_completed, int):
            continue
        sample_points.append((sample_time.timestamp(), sample_completed))

    seconds_per_run: float | None = None
    basis = ""
    if len(sample_points) >= 2:
        first_epoch, first_completed = sample_points[0]
        last_epoch, last_completed = sample_points[-1]
        elapsed = last_epoch - first_epoch
        completed_delta = last_completed - first_completed
        if elapsed > 0 and completed_delta > 0:
            seconds_per_run = elapsed / completed_delta
            basis = f"recent throughput over {completed_delta} completed model runs"

    if seconds_per_run is None:
        baseline_time = _parse_timestamp(record.get("eta_baseline_at"))
        baseline_completed = int(record.get("eta_baseline_completed", 0) or 0)
        if baseline_time is None:
            baseline_time = _parse_timestamp(record.get("started_at"))
            baseline_completed = 0
        if baseline_time is not None:
            elapsed = current_epoch - baseline_time.timestamp()
            if record.get("eta_baseline_at") is None:
                paused_at = _parse_timestamp(record.get("paused_at"))
                resumed_at = _parse_timestamp(record.get("resumed_at"))
                if paused_at is not None and resumed_at is not None:
                    elapsed -= max(
                        resumed_at.timestamp() - paused_at.timestamp(),
                        0.0,
                    )
            completed_delta = completed - baseline_completed
            if elapsed > 0 and completed_delta > 0:
                seconds_per_run = elapsed / completed_delta
                basis = (
                    f"average throughput over {completed_delta} completed model runs"
                )

    if seconds_per_run is None:
        return {
            "label": "Calculating…",
            "seconds": None,
            "finish_at": None,
            "basis": "waiting for completed model runs",
        }

    remaining_seconds = seconds_per_run * remaining_runs
    finish_at = current_time + timedelta(seconds=remaining_seconds)
    return {
        "label": f"≈ {_format_remaining_seconds(remaining_seconds)}",
        "seconds": remaining_seconds,
        "finish_at": finish_at.isoformat(timespec="minutes"),
        "basis": basis,
    }


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        for attempt in range(ATOMIC_WRITE_MAX_ATTEMPTS):
            try:
                os.replace(temp_path, path)
                return
            except PermissionError:
                if attempt + 1 == ATOMIC_WRITE_MAX_ATTEMPTS:
                    raise
                time.sleep(
                    min(ATOMIC_WRITE_RETRY_SECONDS * (2**attempt), 0.25)
                )
    finally:
        temp_path.unlink(missing_ok=True)


def jobs_root(project_root: Path | str = ".") -> Path:
    return Path(project_root).resolve() / DEFAULT_JOBS_DIRECTORY


def job_status_path(job_dir: Path | str) -> Path:
    return Path(job_dir) / "status.json"


class BackgroundJobControlError(RuntimeError):
    """Raised when a detached job cannot be controlled safely."""


def _linux_process_state(pid: int) -> str | None:
    if not sys.platform.startswith("linux"):
        return None
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    closing_parenthesis = stat.rfind(")")
    if closing_parenthesis < 0:
        return None
    fields = stat[closing_parenthesis + 1 :].strip().split()
    return fields[0] if fields else None


def _job_process_group(job_dir: Path, record: Dict[str, Any]) -> tuple[int, int]:
    if not sys.platform.startswith("linux"):
        raise BackgroundJobControlError(
            "Background job controls are currently supported on Linux servers only."
        )

    pid = record.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        raise BackgroundJobControlError("This job does not have a valid worker PID.")

    proc_dir = Path("/proc") / str(pid)
    try:
        command = (proc_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", errors="replace"
        )
        process_group = os.getpgid(pid)
        session_id = os.getsid(pid)
    except (OSError, ProcessLookupError) as exc:
        raise BackgroundJobControlError(
            "The worker process is no longer running."
        ) from exc

    expected_dir = str(job_dir.resolve())
    if "simulation.server_job_worker" not in command or expected_dir not in command:
        raise BackgroundJobControlError(
            "The recorded PID no longer belongs to this job; no signal was sent."
        )
    if process_group != pid or session_id != pid:
        raise BackgroundJobControlError(
            "The worker is not the isolated process-group leader; no signal was sent."
        )
    return pid, process_group


def _signal_process_group(process_group: int, signal_number: int) -> None:
    try:
        kill_process_group = os.killpg
    except AttributeError as exc:
        raise BackgroundJobControlError(
            "Process-group signalling is not available on this operating system."
        ) from exc
    kill_process_group(process_group, signal_number)


def read_background_job(job_dir: Path | str) -> Dict[str, Any]:
    directory = Path(job_dir)
    path = job_status_path(directory)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    pid = payload.get("pid")
    if (
        payload.get("state") in CONTROLLABLE_JOB_STATES
        and isinstance(pid, int)
        and _linux_process_state(pid) in {"T", "t"}
    ):
        payload["state"] = "paused"
        payload["message"] = "Experiment process group is paused"
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


def control_background_job(
    job_dir: Path | str,
    action: str,
) -> Dict[str, Any]:
    """Pause, resume, or cancel an isolated Linux background job."""
    directory = Path(job_dir).resolve()
    requested_action = str(action).strip().lower()
    if requested_action not in {"pause", "resume", "cancel"}:
        raise ValueError(f"Unsupported background job action: {action!r}")

    record = read_background_job(directory)
    if not record:
        raise BackgroundJobControlError("The selected job record could not be read.")
    state = str(record.get("state", "unknown"))
    if state in TERMINAL_JOB_STATES:
        raise BackgroundJobControlError(
            f"The job is already in terminal state {state!r}."
        )

    _, process_group = _job_process_group(directory, record)
    if requested_action == "pause":
        if state == "paused":
            return record
        _signal_process_group(process_group, LINUX_SIGSTOP)
        return _update_background_job(
            directory,
            state="paused",
            paused_at=_now(),
            stage="paused",
            message="Experiment paused by user",
        )

    if requested_action == "resume":
        if state != "paused":
            raise BackgroundJobControlError(
                f"Only a paused job can be resumed; current state is {state!r}."
            )
        _signal_process_group(process_group, LINUX_SIGCONT)
        resumed_at = _now()
        return _update_background_job(
            directory,
            state="running",
            resumed_at=resumed_at,
            eta_baseline_at=resumed_at,
            eta_baseline_completed=int(record.get("completed_model_runs", 0)),
            progress_samples=[],
            stage="resuming",
            message="Experiment resumed by user",
        )

    _update_background_job(
        directory,
        state="cancelling",
        stage="cancelling",
        message="Cancellation signal is being sent",
    )
    try:
        _signal_process_group(process_group, signal.SIGTERM)
        if state == "paused":
            # SIGTERM remains pending for a stopped process until it is continued.
            _signal_process_group(process_group, LINUX_SIGCONT)
    except (OSError, ProcessLookupError):
        _update_background_job(
            directory,
            state=state,
            stage=record.get("stage", state),
            message=record.get("message", ""),
        )
        raise
    return _update_background_job(
        directory,
        state="cancelled",
        cancelled_at=_now(),
        finished_at=_now(),
        stage="cancelled",
        message="Experiment cancelled by user; partial artifacts were preserved",
    )


def _update_background_job(job_dir: Path, **updates: Any) -> Dict[str, Any]:
    payload = read_background_job(job_dir)
    payload.update(updates)
    payload["updated_at"] = _now()
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
        "updated_at": _now(),
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
        "progress_samples": [],
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
        progress_samples = None
        if stage == "model_run_complete":
            completed_model_runs += 1
            current_record = read_background_job(directory)
            progress_samples = [
                sample
                for sample in current_record.get("progress_samples", [])
                if isinstance(sample, dict)
            ]
            progress_samples.append(
                {
                    "at": _now(),
                    "completed": completed_model_runs,
                }
            )
            progress_samples = progress_samples[-PROGRESS_SAMPLE_LIMIT:]
        progress_updates = (
            {"progress_samples": progress_samples}
            if progress_samples is not None
            else {}
        )
        _update_background_job(
            directory,
            state="running",
            stage=stage,
            stage_current=int(current),
            stage_total=int(total),
            message=str(message),
            completed_model_runs=completed_model_runs,
            **progress_updates,
        )

    started_at = _now()
    _update_background_job(
        directory,
        state="running",
        started_at=started_at,
        eta_baseline_at=started_at,
        eta_baseline_completed=completed_model_runs,
        progress_samples=[],
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
        remaining = estimate_job_remaining(record)
        rows.append(
            {
                "job_id": record.get("job_id"),
                "state": record.get("state"),
                "experiment": record.get("experiment_name"),
                "adapter": record.get("adapter"),
                "workers": record.get("configured_workers", 1),
                "progress_percent": round(progress, 1),
                "model_runs": f"{completed}/{total}",
                "remaining": remaining["label"],
                "stage": record.get("stage"),
                "created_at": record.get("created_at"),
                "result_dir": record.get("result_dir"),
            }
        )
    return rows

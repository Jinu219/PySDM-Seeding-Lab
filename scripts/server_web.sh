#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${PROJECT_ROOT}/.runtime/server"
PID_FILE="${RUNTIME_DIR}/streamlit.pid"
LOG_FILE="${RUNTIME_DIR}/streamlit.log"
HOST="${PYSDM_SERVER_HOST:-127.0.0.1}"
PORT="${PYSDM_SERVER_PORT:-8501}"

find_python() {
  if [[ -n "${PYSDM_PYTHON:-}" ]]; then
    printf '%s\n' "${PYSDM_PYTHON}"
  elif [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    printf '%s\n' "${PROJECT_ROOT}/.venv/bin/python"
  elif [[ -x "${PROJECT_ROOT}/.conda/bin/python" ]]; then
    printf '%s\n' "${PROJECT_ROOT}/.conda/bin/python"
  else
    command -v python3
  fi
}

read_pid() {
  if [[ -f "${PID_FILE}" ]]; then
    tr -dc '0-9' < "${PID_FILE}"
  fi
}

is_running() {
  local pid
  pid="$(read_pid)"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

start_server() {
  mkdir -p "${RUNTIME_DIR}"
  chmod 700 "${RUNTIME_DIR}"
  if is_running; then
    echo "PySDM Seeding Lab is already running (PID $(read_pid))."
    exit 0
  fi

  local python_bin
  python_bin="$(find_python)"
  if [[ -z "${python_bin}" ]]; then
    echo "Python was not found. Set PYSDM_PYTHON to the virtual-environment interpreter." >&2
    exit 1
  fi

  cd "${PROJECT_ROOT}"
  umask 077
  PYSDM_LAB_SERVER_MODE=1 nohup "${python_bin}" -m streamlit run app.py \
    --server.headless=true \
    --server.address="${HOST}" \
    --server.port="${PORT}" \
    --browser.gatherUsageStats=false \
    >> "${LOG_FILE}" 2>&1 &
  local pid=$!
  printf '%s\n' "${pid}" > "${PID_FILE}"
  sleep 1

  if ! kill -0 "${pid}" 2>/dev/null; then
    echo "Streamlit exited during startup. Inspect ${LOG_FILE}." >&2
    exit 1
  fi

  echo "PySDM Seeding Lab started (PID ${pid})."
  echo "Listening on ${HOST}:${PORT}"
  echo "Log: ${LOG_FILE}"
  if [[ "${HOST}" == "127.0.0.1" || "${HOST}" == "localhost" ]]; then
    echo "From your PC: ssh -N -L ${PORT}:127.0.0.1:${PORT} USER@SERVER"
    echo "Then open: http://localhost:${PORT}"
  fi
}

stop_server() {
  if ! is_running; then
    echo "PySDM Seeding Lab is not running."
    rm -f "${PID_FILE}"
    exit 0
  fi
  local pid
  pid="$(read_pid)"
  kill "${pid}"
  for _ in {1..20}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      rm -f "${PID_FILE}"
      echo "PySDM Seeding Lab stopped."
      exit 0
    fi
    sleep 0.25
  done
  echo "PID ${pid} did not stop within 5 seconds; inspect it before using a force signal." >&2
  exit 1
}

status_server() {
  if is_running; then
    echo "running (PID $(read_pid), ${HOST}:${PORT})"
    exit 0
  fi
  echo "stopped"
  exit 1
}

case "${1:-start}" in
  start) start_server ;;
  stop) stop_server ;;
  restart) stop_server; start_server ;;
  status) status_server ;;
  *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac

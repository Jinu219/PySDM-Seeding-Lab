#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${PROJECT_ROOT}/.runtime/server"
PID_FILE="${RUNTIME_DIR}/streamlit.pid"
LOG_FILE="${RUNTIME_DIR}/streamlit.log"
HOST="${PYSDM_SERVER_HOST:-127.0.0.1}"
PORT="${PYSDM_SERVER_PORT:-8501}"
SYSTEMD_UNIT_NAME="${PYSDM_SYSTEMD_UNIT_NAME:-pysdm-seeding-lab.service}"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SYSTEMD_UNIT_PATH="${SYSTEMD_USER_DIR}/${SYSTEMD_UNIT_NAME}"

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

user_systemd_available() {
  command -v systemctl >/dev/null 2>&1 &&
    systemctl --user show-environment >/dev/null 2>&1
}

systemd_service_running() {
  user_systemd_available &&
    systemctl --user is-active --quiet "${SYSTEMD_UNIT_NAME}"
}

systemd_main_pid() {
  systemctl --user show "${SYSTEMD_UNIT_NAME}" \
    --property=MainPID --value 2>/dev/null || true
}

write_systemd_unit() {
  local python_bin="$1"
  mkdir -p "${SYSTEMD_USER_DIR}"
  chmod 700 "${SYSTEMD_USER_DIR}"
  cat > "${SYSTEMD_UNIT_PATH}" <<EOF
[Unit]
Description=PySDM Seeding Lab Streamlit server

[Service]
Type=simple
WorkingDirectory=${PROJECT_ROOT}
Environment=PYSDM_LAB_SERVER_MODE=1
Environment=PYSDM_SERVER_HOST=${HOST}
Environment=PYSDM_SERVER_PORT=${PORT}
Environment=PYSDM_PYTHON=${python_bin}
ExecStart=/bin/bash ${PROJECT_ROOT}/scripts/server_web.sh run-process
Restart=on-failure
RestartSec=2
KillMode=control-group
TimeoutStopSec=10
UMask=0077

[Install]
WantedBy=default.target
EOF
  chmod 600 "${SYSTEMD_UNIT_PATH}"
  systemctl --user daemon-reload
}

run_server_process() {
  mkdir -p "${RUNTIME_DIR}"
  chmod 700 "${RUNTIME_DIR}"
  local python_bin
  python_bin="$(find_python)"
  cd "${PROJECT_ROOT}"
  umask 077
  exec env PYSDM_LAB_SERVER_MODE=1 "${python_bin}" -m streamlit run app.py \
    --server.headless=true \
    --server.address="${HOST}" \
    --server.port="${PORT}" \
    --browser.gatherUsageStats=false \
    >> "${LOG_FILE}" 2>&1
}

start_server() {
  mkdir -p "${RUNTIME_DIR}"
  chmod 700 "${RUNTIME_DIR}"
  if systemd_service_running; then
    local systemd_pid
    systemd_pid="$(systemd_main_pid)"
    printf '%s\n' "${systemd_pid}" > "${PID_FILE}"
    echo "PySDM Seeding Lab is already running (PID ${systemd_pid}, systemd user service)."
    return 0
  elif is_running; then
    echo "PySDM Seeding Lab is already running (PID $(read_pid))."
    return 0
  fi

  local python_bin
  python_bin="$(find_python)"
  if [[ -z "${python_bin}" ]]; then
    echo "Python was not found. Set PYSDM_PYTHON to the virtual-environment interpreter." >&2
    exit 1
  fi

  if user_systemd_available; then
    write_systemd_unit "${python_bin}"
    systemctl --user enable "${SYSTEMD_UNIT_NAME}" >/dev/null
    systemctl --user start "${SYSTEMD_UNIT_NAME}"
    sleep 1

    if ! systemd_service_running; then
      echo "Streamlit systemd service exited during startup." >&2
      echo "Inspect: journalctl --user -u ${SYSTEMD_UNIT_NAME} -n 100" >&2
      echo "Log: ${LOG_FILE}" >&2
      exit 1
    fi

    local systemd_pid
    systemd_pid="$(systemd_main_pid)"
    printf '%s\n' "${systemd_pid}" > "${PID_FILE}"
    echo "PySDM Seeding Lab started (PID ${systemd_pid}, systemd user service)."
    echo "Listening on ${HOST}:${PORT}"
    echo "Log: ${LOG_FILE}"
    return 0
  fi

  echo "Warning: user systemd is unavailable; falling back to nohup." >&2
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
  if user_systemd_available && [[ -f "${SYSTEMD_UNIT_PATH}" ]]; then
    if systemd_service_running; then
      systemctl --user stop "${SYSTEMD_UNIT_NAME}"
      rm -f "${PID_FILE}"
      echo "PySDM Seeding Lab stopped (systemd user service)."
      return 0
    fi
    rm -f "${PID_FILE}"
    echo "PySDM Seeding Lab is not running."
    return 0
  fi

  if ! is_running; then
    echo "PySDM Seeding Lab is not running."
    rm -f "${PID_FILE}"
    return 0
  fi
  local pid
  pid="$(read_pid)"
  kill "${pid}"
  for _ in {1..20}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      rm -f "${PID_FILE}"
      echo "PySDM Seeding Lab stopped."
      return 0
    fi
    sleep 0.25
  done
  echo "PID ${pid} did not stop within 5 seconds; inspect it before using a force signal." >&2
  return 1
}

status_server() {
  if systemd_service_running; then
    local systemd_pid
    systemd_pid="$(systemd_main_pid)"
    printf '%s\n' "${systemd_pid}" > "${PID_FILE}"
    echo "running (PID ${systemd_pid}, ${HOST}:${PORT}, systemd user service)"
    exit 0
  elif is_running; then
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
  run-process) run_server_process ;;
  *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac

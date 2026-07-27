#!/usr/bin/env bash
set -euo pipefail

BUNDLE_PATH="${1:?Usage: apply_server_bundle.sh BUNDLE_PATH [BRANCH]}"
BRANCH="${2:-develop}"
PROJECT_ROOT="${PYSDM_PROJECT_ROOT:-${HOME}/PySDM-Seeding-Lab}"

cleanup() {
  case "${BUNDLE_PATH}" in
    /tmp/pysdm-*.bundle) rm -f -- "${BUNDLE_PATH}" ;;
  esac
  case "${0}" in
    /tmp/apply-pysdm-*.sh) rm -f -- "${0}" ;;
  esac
}
trap cleanup EXIT

if [[ ! -f "${BUNDLE_PATH}" ]]; then
  echo "Bundle not found: ${BUNDLE_PATH}" >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

current_branch="$(git branch --show-current)"
if [[ "${current_branch}" != "${BRANCH}" ]]; then
  echo "Expected branch ${BRANCH}, but server is on ${current_branch}." >&2
  exit 1
fi

# configs/default.yaml is the server's mutable working configuration. Refuse to
# deploy over any other tracked server-side edit.
unexpected_changes="$(
  git status --porcelain --untracked-files=no |
    awk '$2 != "configs/default.yaml" { print }'
)"
if [[ -n "${unexpected_changes}" ]]; then
  echo "Deployment stopped: unexpected tracked changes exist on the server." >&2
  printf '%s\n' "${unexpected_changes}" >&2
  exit 1
fi

git bundle verify "${BUNDLE_PATH}"
git fetch "${BUNDLE_PATH}" "refs/heads/${BRANCH}"
git merge --ff-only FETCH_HEAD

bash scripts/server_web.sh restart
bash scripts/server_web.sh status

for _ in {1..20}; do
  if [[ "$(curl --noproxy '*' --silent --show-error --max-time 2 \
    http://127.0.0.1:8501/_stcore/health 2>/dev/null || true)" == "ok" ]]; then
    echo "Deployment complete: ${BRANCH} $(git rev-parse --short HEAD)"
    echo "Health check: ok"
    exit 0
  fi
  sleep 0.5
done

echo "Deployment applied, but the Streamlit health check failed." >&2
echo "Inspect: ${PROJECT_ROOT}/.runtime/server/streamlit.log" >&2
exit 1

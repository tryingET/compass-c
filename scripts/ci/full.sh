#!/bin/sh
set -eu

say() { printf '%s\n' "$*"; }
err() { printf '%s\n' "$*" >&2; }

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "error: not a git repo" >&2; exit 1; }
AK_CMD="${AK_CMD:-ak}"
cd "$repo_root"

say "==> fast"
"$script_dir/fast.sh"

log_dir="$(mktemp -d "${TMPDIR:-/tmp}/tpl-project-full.XXXXXX")"
cleanup() {
  rm -rf "$log_dir"
}
trap cleanup EXIT INT TERM

run_task_scope_snapshots() {
  if [ -x "./scripts/check-task-scope-snapshots.sh" ]; then
    ./scripts/check-task-scope-snapshots.sh
  fi
}

run_rocs() {
  if [ -x "./scripts/rocs.sh" ] && [ -f "./ontology/manifest.yaml" ]; then
    ./scripts/rocs.sh version
    ./scripts/rocs.sh build --repo . --resolve-refs --clean
    ./scripts/rocs.sh validate --repo . --resolve-refs
  fi
}

say "==> task-scope snapshots"
task_scopes_status=0
if run_task_scope_snapshots >"$log_dir/task-scopes.log" 2>&1; then
  task_scopes_status=0
else
  task_scopes_status=$?
fi

say "==> rocs"
rocs_status=0
if run_rocs >"$log_dir/rocs.log" 2>&1; then
  rocs_status=0
else
  rocs_status=$?
fi

say "--- task-scope output ---"
cat "$log_dir/task-scopes.log"
say "--- rocs output ---"
cat "$log_dir/rocs.log"

if [ "$task_scopes_status" -ne 0 ] || [ "$rocs_status" -ne 0 ]; then
  err "error: full.sh failed"
  [ "$task_scopes_status" -eq 0 ] || err "- task-scope snapshots exit=$task_scopes_status"
  [ "$rocs_status" -eq 0 ] || err "- rocs exit=$rocs_status"
  exit 1
fi

say "ok: full"

#!/bin/sh
set -eu

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "error: document policy requires a git repository" >&2
  exit 2
}
cd "$repo_root"

posture="docs/project/product_posture.md"
errors=0

error() {
  echo "error: $*" >&2
  errors=$((errors + 1))
}

validate_frontmatter() {
  awk '
    NR == 1 {
      if ($0 != "---") invalid=1
      in_frontmatter=1
      next
    }
    in_frontmatter && $0 == "---" {
      closed=1
      exit
    }
    in_frontmatter {
      if ($0 ~ /^as_of:/) as_of_count++
      if ($0 ~ /^last_validated:/) last_validated_count++
      if ($0 ~ /^last_validated_commit:/) baseline_count++
      if ($0 ~ /^evidence_paths:/) evidence_paths_count++
    }
    END {
      if (invalid || !closed || as_of_count != 1 || last_validated_count != 1 || baseline_count != 1 || evidence_paths_count != 1) exit 1
    }
  ' "$posture"
}

scalar() {
  key="$1"
  awk -F: -v key="$key" '
    NR == 1 { in_frontmatter=($0 == "---"); next }
    in_frontmatter && $0 == "---" { exit }
    in_frontmatter && $1 == key {
      value=substr($0, index($0, ":") + 1)
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      gsub(/^"|"$/, "", value)
      print value
      exit
    }
  ' "$posture"
}

# Print a Gregorian day ordinal, or fail for a malformed/impossible YYYY-MM-DD.
date_ordinal() {
  awk -v value="$1" '
    function leap(y) { return (y % 4 == 0 && y % 100 != 0) || y % 400 == 0 }
    BEGIN {
      if (value !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) exit 1
      split(value, p, "-"); y=p[1]+0; m=p[2]+0; d=p[3]+0
      if (y < 1 || m < 1 || m > 12) exit 1
      md[1]=31; md[2]=28+leap(y); md[3]=31; md[4]=30; md[5]=31; md[6]=30
      md[7]=31; md[8]=31; md[9]=30; md[10]=31; md[11]=30; md[12]=31
      if (d < 1 || d > md[m]) exit 1
      n=y-1; days=365*n+int(n/4)-int(n/100)+int(n/400)
      for (i=1; i<m; i++) days+=md[i]
      print days+d
    }
  '
}

[ -f "$posture" ] || {
  echo "error: missing living posture: $posture" >&2
  exit 1
}

validate_frontmatter || error "$posture: frontmatter must be delimited and declare each required metadata key exactly once"

as_of="$(scalar as_of)"
last_validated="$(scalar last_validated)"
baseline="$(scalar last_validated_commit)"

as_of_day=""
validated_day=""
if ! as_of_day="$(date_ordinal "$as_of")"; then
  error "$posture: as_of must be a real YYYY-MM-DD date"
fi
if ! validated_day="$(date_ordinal "$last_validated")"; then
  error "$posture: last_validated must be a real YYYY-MM-DD date"
fi

if [ -n "${PRODUCT_POSTURE_TODAY+x}" ]; then
  [ "${PRODUCT_POSTURE_TEST_MODE:-}" = "1" ] || error "PRODUCT_POSTURE_TODAY is allowed only with PRODUCT_POSTURE_TEST_MODE=1"
  today="$PRODUCT_POSTURE_TODAY"
else
  today="$(date -u +%F)"
fi
if ! today_day="$(date_ordinal "$today")"; then
  error "effective current date must be a real YYYY-MM-DD date"
  today_day=""
fi

if [ -n "$as_of_day" ] && [ -n "$validated_day" ]; then
  [ "$as_of_day" -le "$validated_day" ] || error "$posture: as_of must not be later than last_validated"
fi
if [ -n "$validated_day" ] && [ -n "$today_day" ]; then
  [ "$validated_day" -le "$today_day" ] || error "$posture: last_validated must not be in the future"
  age_days=$((today_day - validated_day))
  [ "$age_days" -le 30 ] || error "$posture: validation is $age_days days old (maximum 30)"
fi
if [ -n "$as_of_day" ] && [ -n "$today_day" ]; then
  [ "$as_of_day" -le "$today_day" ] || error "$posture: as_of must not be in the future"
  as_of_age_days=$((today_day - as_of_day))
  [ "$as_of_age_days" -le 30 ] || error "$posture: as_of is $as_of_age_days days old (maximum 30 for a living posture)"
fi

printf '%s\n' "$baseline" | grep -Eq '^[0-9a-f]{40}$' || error "$posture: last_validated_commit must be a full 40-character lowercase commit SHA"

baseline_ok=0
if printf '%s\n' "$baseline" | grep -Eq '^[0-9a-f]{40}$'; then
  if ! git cat-file -e "$baseline^{commit}" 2>/dev/null; then
    error "$posture: validation baseline is unavailable; freshness is unverifiable"
  elif ! git merge-base --is-ancestor "$baseline" HEAD 2>/dev/null; then
    error "$posture: validation baseline is not an ancestor of HEAD; freshness is unverifiable"
  else
    baseline_ok=1
  fi
fi

# The documented two-commit workflow requires exactly one committed posture
# update after the evidence baseline. Further posture edits require revalidation.
if [ "$baseline_ok" -eq 1 ]; then
  posture_commits="$(git log --format=%H "$baseline..HEAD" -- "$posture" | awk 'END { print NR+0 }')"
  [ "$posture_commits" -eq 1 ] || error "$posture: expected exactly one validation commit after the evidence baseline; found $posture_commits"
fi
[ -z "$(git status --porcelain --untracked-files=all -- "$posture")" ] || error "$posture: uncommitted posture changes make validation unverifiable"

evidence_file="$(mktemp "${TMPDIR:-/tmp}/product-posture-evidence.XXXXXX")"
trap 'rm -f "$evidence_file"' EXIT HUP INT TERM
awk '
  NR == 1 { in_frontmatter=($0 == "---"); next }
  in_frontmatter && $0 == "---" { exit }
  in_frontmatter && /^evidence_paths:[[:space:]]*$/ { in_paths=1; next }
  in_frontmatter && in_paths && /^  -[[:space:]]+/ {
    value=$0
    sub(/^  -[[:space:]]+/, "", value)
    gsub(/^"|"$/, "", value)
    print value
    next
  }
  in_frontmatter && in_paths && /^[^[:space:]]/ { exit }
' "$posture" > "$evidence_file"

[ -s "$evidence_file" ] || error "$posture: evidence_paths must contain at least one repo-relative path"
while IFS= read -r path; do
  case "$path" in
    ""|/*|../*|*/../*|*/..|:*|*\\*|*'*'*|*'?'*|*'['*|*']'*)
      error "$posture: invalid evidence path: $path"
      continue
      ;;
    "$posture")
      error "$posture: may not cite itself as evidence"
      continue
      ;;
  esac
  [ -z "$(git status --porcelain --untracked-files=all -- "$path")" ] || error "$posture: uncommitted evidence changes make freshness unverifiable: $path"
  if [ "$baseline_ok" -eq 1 ]; then
    if ! git ls-tree -r --name-only "$baseline" -- "$path" | grep -q .; then
      error "$posture: evidence path has no tracked match at baseline: $path"
      continue
    fi
    if git log --format=%H "$baseline..HEAD" -- "$path" | grep -q .; then
      error "$posture: stale because a relevant commit touched evidence path after validation: $path"
    fi
  fi
done < "$evidence_file"

# Fail malformed uses of the explicit dated-snapshot grammar and a small set of
# unambiguously snapshot-shaped legacy names. Do not classify arbitrary durable
# guides merely because they contain words such as "migration" or "status".
find docs -type f -name '*.md' ! -path 'docs/project/product_posture.md' ! -path 'docs/diary/*' -print |
while IFS= read -r path; do
  base="${path##*/}"
  lower="$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')"
  requires_dated=0
  case "$lower" in
    *--transition--*|*--migration--*|*--current-vs-target--*|*--status--*|status.md|project-status.md|implementation-status.md|current-status.md|*-current-status.md|current-vs-target.md|*-current-vs-target.md|transition-summary.md|*-transition-summary.md|migration-status.md|*-migration-status.md)
      requires_dated=1
      ;;
  esac
  if [ "$requires_dated" -eq 1 ]; then
    if ! printf '%s\n' "$lower" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}--(transition|migration|current-vs-target|status)--[a-z0-9][a-z0-9-]*\.md$'; then
      echo "error: time-bounded document must use YYYY-MM-DD--{transition|migration|current-vs-target|status}--scope.md: $path" >&2
      exit 1
    fi
    snapshot_date="${lower%%--*}"
    date_ordinal "$snapshot_date" >/dev/null || {
      echo "error: dated snapshot has an impossible calendar date: $path" >&2
      exit 1
    }
  fi
done || errors=$((errors + 1))

[ "$errors" -eq 0 ] || exit 1
echo "ok: document freshness and dated-snapshot policy"

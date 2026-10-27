#!/usr/bin/env bash
# Link the self-improvement skill into the opencode and Hermes skill
# directories, and the /self-improvement command into opencode. Writes only those
# harnesses' own directories: the plugin-marketplace harnesses get the skill
# without this script (no duplicate installs). A path that sits at a link name
# moves into a new NAME.bak-TIMESTAMP directory first; the script deletes
# nothing. On a failure or a signal the report names the links done, the links
# missing, and the backups made.
set -euo pipefail

usage() {
  echo "usage: install.sh [--dry-run] [--help]"
  echo "  --dry-run   print each action and write nothing"
  echo "  -h, --help  print this help and exit 0"
}

# install.sh sets the report trap after parsing because nothing is linked before it.
DRY=0
for arg in "$@"; do
  case "$arg" in
    -h | --help)
      usage
      exit 0
      ;;
    --dry-run)
      DRY=1
      ;;
    *)
      echo "install.sh: unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OC="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
HERMES="${HERMES_HOME:-$HOME/.hermes}"

OC_SKILL="$OC/skills/self-improvement"
OC_CMD="$OC/commands/self-improvement.md"
HRM_SKILL="$HERMES/skills/self-improvement"
PLANNED=("$OC_SKILL" "$OC_CMD" "$HRM_SKILL")
DONE=()
BAKS=()
# The move can finish before BAKS records it; the report checks this path then.
PENDING_BAK=""

# On failure or signal name the links done, the links missing, and the backups made.
report() {
  local cause="$1" dst linked="" missing="" made
  for dst in "${PLANNED[@]}"; do
    if [[ " ${DONE[*]:-} " == *" $dst "* ]]; then
      linked="$linked $dst"
    else
      missing="$missing $dst"
    fi
  done
  echo "install.sh: $cause; nothing is rolled back" >&2
  echo "install.sh: linked:${linked:- none}" >&2
  echo "install.sh: not linked:${missing:- none}" >&2
  made="${BAKS[*]:-}"
  if [ -n "$PENDING_BAK" ] && { [ -e "$PENDING_BAK" ] || [ -L "$PENDING_BAK" ]; }; then
    made="${made:+$made }$PENDING_BAK"
  fi
  if [ -n "$made" ]; then
    echo "install.sh: backups made:$made" >&2
  fi
}

# Re-raise the signal after the report so the caller sees the signal, not an exit code.
on_signal() {
  local sig="$1"
  report "interrupted by SIG$sig"
  trap - EXIT
  trap - "$sig"
  kill -"$sig" $$
}

# On a nonzero exit status report like a failure.
on_exit() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then report "failed with exit $rc"; fi
  exit "$rc"
}

trap on_exit EXIT
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM

# Back up any existing path at DST, then symlink SRC there.
link() {
  local src="$1" dst="$2" name bak
  name="$(basename "$dst")"
  while :; do
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
      DONE+=("$dst")
      return 0
    fi
    if [ -e "$dst" ] || [ -L "$dst" ]; then
      bak="$dst.bak-$(date -u +%Y%m%dT%H%M%S)"
      if [ "$DRY" = 1 ]; then
        while [ -e "$bak" ] || [ -L "$bak" ]; do bak="$bak.1"; done
        echo "would back up: $dst -> $bak/$name"
      else
        # mkdir reserves the backup name and fails on an existing name, and the
        # move into the fresh empty dir replaces no path.
        while ! mkdir "$bak" 2>/dev/null; do
          [ -e "$bak" ] || [ -L "$bak" ] || return 1
          bak="$bak.1"
        done
        PENDING_BAK="$bak/$name"
        if mv "$dst" "$PENDING_BAK"; then
          BAKS+=("$PENDING_BAK")
          PENDING_BAK=""
          echo "backed up: $dst -> $bak/$name"
        else
          # The mv can die after its move finished; the disk state wins over
          # the exit code. Keep and name the moved payload, never drop it.
          if [ -e "$PENDING_BAK" ] || [ -L "$PENDING_BAK" ]; then
            if [ -e "$dst" ] || [ -L "$dst" ]; then
              echo "install.sh: cannot back up $dst" >&2
              return 1
            fi
            BAKS+=("$PENDING_BAK")
            echo "backed up: $dst -> $PENDING_BAK"
            PENDING_BAK=""
            continue
          fi
          rmdir "$bak" 2>/dev/null || true
          PENDING_BAK=""
          # A concurrent install took the path; re-read its state then. Any
          # other mv failure must stop the run so this loop cannot spin.
          if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            continue
          elif [ -e "$dst" ] || [ -L "$dst" ]; then
            echo "install.sh: cannot back up $dst" >&2
            return 1
          fi
          continue
        fi
      fi
    fi
    if [ "$DRY" = 1 ]; then
      echo "would link: $src -> $dst"
      DONE+=("$dst")
      return 0
    fi
    # -T treats DST as a link name even when a real directory sits there, so
    # ln never writes a link inside it; a failure means the path is occupied.
    if ! ln -sTn "$src" "$dst" 2>/dev/null; then
      if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        : # leave the link that a concurrent install made
      else
        echo "install.sh: cannot link $src -> $dst" >&2
        return 1
      fi
    fi
    DONE+=("$dst")
    return 0
  done
}

if [ "$DRY" = 1 ]; then
  echo "would mkdir: $OC/skills $OC/commands $HERMES/skills"
else
  mkdir -p "$OC/skills" "$OC/commands" "$HERMES/skills"
fi

link "$ROOT/skills/self-improvement" "$OC_SKILL"
link "$ROOT/.opencode/command/self-improvement.md" "$OC_CMD"
link "$ROOT/skills/self-improvement" "$HRM_SKILL"

if [ "$DRY" = 0 ]; then
  echo "linked; restart opencode to pick the skill up"
fi

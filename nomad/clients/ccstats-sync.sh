#!/usr/bin/env bash
# ccstats-sync.sh — push this machine's Claude Code transcripts to the ccstats server.
# Incremental tar-over-transport (no rsync). Idempotent: the ccstats ledger dedups
# by session id, so re-sending is harmless. Resumable: each project dir is sent
# independently, so a dropped connection only redoes one dir. Transcripts only
# (~/.claude/projects) — does NOT copy credentials or any secret.
#
# Two transports:
#   SSH  (default, for boxes on the mesh that can reach the VM's private IP):
#        needs CCSTATS_VM (default 10.0.0.1) + key ~/.ssh/ccstats_sync -> ccsync@VM.
#   HTTP (for boxes that can only reach the public tunnel URL):
#        set CCSTATS_URL=https://ccstats.example.com and CCSTATS_TOKEN=<master token>.
#        Pushes to POST /ingest/<machine>?token=… (needs only curl + tar).
#
# Machine name defaults to the hostname slug; override with CCSTATS_MACHINE.
# The server must already have /home/<machine>/.claude/projects (owned by ccsync).
set -uo pipefail

MACHINE="${CCSTATS_MACHINE:-$(hostname | tr 'A-Z' 'a-z' | tr -c 'a-z0-9' '-' | sed 's/-\{2,\}/-/g;s/^-//;s/-$//')}"
SRC="$HOME/.claude/projects"
STAMP_DIR="$HOME/.cache/ccstats-sync"
STAMP="$STAMP_DIR/stamp-$MACHINE"

URL="${CCSTATS_URL:-}"
HTTP_TOKEN="${CCSTATS_TOKEN:-}"
VM="${CCSTATS_VM:-10.0.0.1}"
KEY="${CCSTATS_KEY:-$HOME/.ssh/ccstats_sync}"
DEST="/home/$MACHINE/.claude/projects"
SSH="ssh -i $KEY -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 ccsync@$VM"

# send(): read a gzip tar on stdin, deliver it for $MACHINE. Returns non-zero on failure.
send() {
  if [ -n "$URL" ]; then
    curl -sf --max-time 300 -H 'Content-Type: application/octet-stream' \
         --data-binary @- "$URL/ingest/$MACHINE?token=$HTTP_TOKEN" >/dev/null
  else
    $SSH "tar xzf - -C '$DEST'"
  fi
}

mkdir -p "$STAMP_DIR"

# Single-instance lock (atomic mkdir); skip if a run is already in progress.
LOCK="$STAMP_DIR/lock-$MACHINE"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') another sync is running ($LOCK) — skipping"; exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# Reachability preflight (also creates the dest dir in SSH mode).
if [ -n "$URL" ]; then
  curl -sf -o /dev/null --max-time 20 "$URL/claude-stats.json?token=$HTTP_TOKEN" \
    || { echo "$(date '+%F %T') $URL unreachable / bad token"; exit 1; }
else
  $SSH "mkdir -p '$DEST'" || { echo "$(date '+%F %T') VM $VM unreachable"; exit 1; }
fi

cd "$SRC" 2>/dev/null || { echo "$(date '+%F %T') no $SRC"; exit 1; }

# Incremental after the first successful run; full seed otherwise.
NEWSTAMP="$STAMP.new"; : > "$NEWSTAMP"
INCR=0; [ -f "$STAMP" ] && INCR=1

fail=0; sent=0
for d in */; do
  d="${d%/}"
  [ -d "$d" ] || continue
  if [ "$INCR" = 1 ]; then
    files=$(find "$d" -type f -newer "$STAMP" 2>/dev/null)
  else
    files=$(find "$d" -type f 2>/dev/null)
  fi
  [ -z "$files" ] && continue
  n=$(printf '%s\n' "$files" | grep -c .)
  if printf '%s\n' "$files" | tar czf - -T - 2>/dev/null | send; then
    sent=$((sent + n)); echo "  ok   $d ($n)"
  else
    echo "  FAIL $d"; fail=1
  fi
done

if [ "$fail" = 0 ]; then
  mv -f "$NEWSTAMP" "$STAMP"
  echo "$(date '+%F %T') sync OK  machine=$MACHINE files=$sent transport=${URL:+http}${URL:-ssh}"
else
  rm -f "$NEWSTAMP"
  echo "$(date '+%F %T') sync PARTIAL machine=$MACHINE files=$sent (will retry next run)"
fi
exit $fail

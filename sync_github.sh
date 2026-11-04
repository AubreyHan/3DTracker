#!/usr/bin/env bash
# Bidirectional GitHub Sync Script for /home/gcpvm/3DTracker
# - Runs every 5 minutes via crontab
# - Conflict strategy: Newer overwrites Older (compares file/commit timestamps)
# - Log file: /home/gcpvm/3DTracker/sync.log (1MB max, FIFO truncation)

set -u

export HOME="/home/gcpvm"
export PATH="/home/gcpvm/.local/bin:/usr/local/bin:/usr/bin:/bin"

REPO_DIR="/home/gcpvm/3DTracker"
LOG_FILE="${REPO_DIR}/sync.log"
LOCK_FILE="/tmp/3dtracker_sync.lock"
MAX_LOG_BYTES=1048576  # 1 MB (1024 * 1024 bytes)
BRANCH="main"
REMOTE="origin"

mkdir -p "${REPO_DIR}"
touch "${LOG_FILE}"

# Enforce 1MB FIFO rotation on sync.log (deletes oldest lines from the top first)
trim_log_fifo() {
    python3 - "${LOG_FILE}" "${MAX_LOG_BYTES}" << 'PYEOF'
import os, sys

log_path = sys.argv[1]
max_bytes = int(sys.argv[2])

if not os.path.exists(log_path):
    sys.exit(0)

size = os.path.getsize(log_path)
if size <= max_bytes:
    sys.exit(0)

with open(log_path, "rb") as f:
    # Seek to retain at most max_bytes from the end
    f.seek(size - max_bytes)
    data = f.read()

# Align to the next full line so we remove complete oldest lines first (FIFO)
nl_idx = data.find(b"\n")
if nl_idx != -1 and nl_idx + 1 < len(data):
    data = data[nl_idx + 1:]

with open(log_path, "wb") as f:
    f.write(data)
PYEOF
}

log_msg() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*" >> "${LOG_FILE}"
}

# Prevent overlapping executions
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    log_msg "SKIP: Previous sync process is still running."
    trim_log_fifo
    exit 0
fi

{
    echo "============================================================"
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Starting bidirectional GitHub sync..."

    cd "${REPO_DIR}" || {
        echo "ERROR: Cannot cd to ${REPO_DIR}"
        exit 1
    }

    # Perform bidirectional sync with Newer-Overwrites-Older conflict resolution
    python3 - << 'PYEOF'
import os
import subprocess
import time
from datetime import datetime, timezone

REPO_DIR = "/home/gcpvm/3DTracker"
REMOTE = "origin"
BRANCH = "main"

def run(cmd, check=False):
    return subprocess.run(cmd, cwd=REPO_DIR, text=True, capture_output=True, check=check)

def fmt_ts(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# 1. Record actual modification times of dirty/untracked local files before auto-committing
local_mtimes = {}
status_res = run(["git", "status", "--porcelain", "-z"])
if status_res.stdout:
    entries = status_res.stdout.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        if not entry:
            i += 1
            continue
        xy = entry[:2]
        path = entry[3:]
        if "R" in xy or "C" in xy:
            i += 1
        full_path = os.path.join(REPO_DIR, path)
        if os.path.exists(full_path):
            local_mtimes[path] = int(os.path.getmtime(full_path))
        else:
            local_mtimes[path] = int(time.time())
        i += 1

# 2. Stage and commit any local changes
if local_mtimes:
    run(["git", "add", "-A"])
    diff_cached = run(["git", "diff", "--cached", "--name-only"])
    if diff_cached.stdout.strip():
        changed_files = diff_cached.stdout.strip().splitlines()
        # Use the newest modified file's mtime as the commit date so timestamps stay accurate
        max_mtime = max(local_mtimes.get(f, int(time.time())) for f in changed_files)
        env = os.environ.copy()
        date_str = f"@{max_mtime} +0000"
        env["GIT_AUTHOR_DATE"] = date_str
        env["GIT_COMMITTER_DATE"] = date_str
        commit_msg = f"Auto-sync local changes ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')})"
        c_res = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=REPO_DIR, env=env, text=True, capture_output=True
        )
        print(f"Committed {len(changed_files)} local file change(s): {', '.join(changed_files)}")
        if c_res.returncode != 0:
            print(f"WARNING: git commit returned {c_res.returncode}: {c_res.stderr.strip()}")

# 3. Fetch remote changes
fetch_res = run(["git", "fetch", REMOTE, BRANCH])
if fetch_res.returncode != 0:
    print(f"ERROR: git fetch failed: {fetch_res.stderr.strip()}")
    raise SystemExit(1)

head_sha = run(["git", "rev-parse", "HEAD"]).stdout.strip()
remote_sha = run(["git", "rev-parse", f"{REMOTE}/{BRANCH}"]).stdout.strip()

if head_sha == remote_sha:
    print(f"Up to date with {REMOTE}/{BRANCH} ({head_sha[:7]}). No changes to sync.")
    raise SystemExit(0)

# Check ancestry relationships
is_head_ancestor = run(["git", "merge-base", "--is-ancestor", head_sha, remote_sha]).returncode == 0
is_remote_ancestor = run(["git", "merge-base", "--is-ancestor", remote_sha, head_sha]).returncode == 0

if is_head_ancestor:
    print(f"Fast-forwarding local {BRANCH} ({head_sha[:7]} -> {remote_sha[:7]})...")
    ff_res = run(["git", "merge", "--ff-only", f"{REMOTE}/{BRANCH}"])
    print(ff_res.stdout.strip() or ff_res.stderr.strip())
    run(["git", "lfs", "pull"])
    print("Pull completed successfully.")
elif is_remote_ancestor:
    print(f"Pushing local commits ({remote_sha[:7]} -> {head_sha[:7]}) to {REMOTE}/{BRANCH}...")
    push_res = run(["git", "push", REMOTE, BRANCH])
    if push_res.returncode != 0:
        print(f"ERROR: git push failed: {push_res.stderr.strip()}")
        raise SystemExit(1)
    print("Push completed successfully.")
else:
    print(f"Diverged histories detected (local={head_sha[:7]}, remote={remote_sha[:7]}). Merging...")
    merge_res = run(["git", "merge", "--no-commit", "--no-ff", f"{REMOTE}/{BRANCH}"])

    # Check for unmerged/conflicted paths
    unmerged_res = run(["git", "diff", "--name-only", "--diff-filter=U"])
    conflicted_files = [f for f in unmerged_res.stdout.splitlines() if f.strip()]

    if conflicted_files:
        print(f"Conflict detected in {len(conflicted_files)} file(s). Applying NEWER-OVERWRITES-OLDER policy:")
        for fpath in conflicted_files:
            # Get local timestamp (prefer recorded mtime if modified in this run, else HEAD commit timestamp)
            if fpath in local_mtimes:
                local_ts = local_mtimes[fpath]
            else:
                l_log = run(["git", "log", "-1", "--format=%ct", "HEAD", "--", fpath]).stdout.strip()
                local_ts = int(l_log) if l_log.isdigit() else 0

            r_log = run(["git", "log", "-1", "--format=%ct", f"{REMOTE}/{BRANCH}", "--", fpath]).stdout.strip()
            remote_ts = int(r_log) if r_log.isdigit() else 0

            if local_ts >= remote_ts:
                winner = "LOCAL (ours)"
                print(f"  - {fpath}: LOCAL is newer ({fmt_ts(local_ts)} >= {fmt_ts(remote_ts)}) -> Keeping LOCAL")
                exists_local = run(["git", "cat-file", "-e", f"HEAD:{fpath}"]).returncode == 0
                if exists_local:
                    run(["git", "checkout", "--ours", "--", fpath])
                    run(["git", "add", "--", fpath])
                else:
                    run(["git", "rm", "-f", "--", fpath])
            else:
                winner = "REMOTE (theirs)"
                print(f"  - {fpath}: REMOTE is newer ({fmt_ts(remote_ts)} > {fmt_ts(local_ts)}) -> Keeping REMOTE")
                exists_remote = run(["git", "cat-file", "-e", f"{REMOTE}/{BRANCH}:{fpath}"]).returncode == 0
                if exists_remote:
                    run(["git", "checkout", "--theirs", "--", fpath])
                    run(["git", "add", "--", fpath])
                else:
                    run(["git", "rm", "-f", "--", fpath])

    # Commit the merge if MERGE_HEAD exists
    if os.path.exists(os.path.join(REPO_DIR, ".git", "MERGE_HEAD")):
        run(["git", "commit", "-m", f"Auto-merge {REMOTE}/{BRANCH} (newer-overwrites-older)"])

    run(["git", "lfs", "pull"])
    push_res = run(["git", "push", REMOTE, BRANCH])
    if push_res.returncode != 0:
        print(f"ERROR: git push after merge failed: {push_res.stderr.strip()}")
        raise SystemExit(1)
    print("Bidirectional merge and push completed successfully.")
PYEOF

    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Sync finished."
} >> "${LOG_FILE}" 2>&1

trim_log_fifo

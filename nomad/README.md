# nomad/ — self-host additions

Customizations for a self-hosted ccstats deployment (VM `ccstats` @ 10.0.0.1, served at
`https://ccstats.example.com` via a Cloudflare tunnel behind Access SSO with a bypass for the feeds).

These are **additions** kept out of the upstream tree so upstream stays easy to merge. Two upstream
files are patched in place (both minimal):

- `server/pipeline/extract.py` — `project_name()` uses a **separator-agnostic basename**, so Windows
  `cwd`s (backslashes) yield the folder name, not the full path. Reapply after an upstream change with
  `nomad/server/winpath_patch.py <path-to-extract.py>`.
- `viewscreens/screens.js` — `drawUsage()` renders **one SESSION/WEEKLY block per Claude account** from
  the multi-account `claude-limits.json` (falls back to the single-account shape).

No secrets live in this repo. Tokens are read from files (`/opt/claude-stats/token.txt`) or passed via
env at runtime.

## Multi-account usage limits (architecture B — tokens stay local)

Rate limits are per-Anthropic-account, and accounts are juggled across machines. So each machine polls
its **currently-active** account locally and ships only the numbers; the VM aggregates per account uuid.

- **`clients/ccstats-limits.py`** — per-machine poller (every ~2 min). Reads the local active-account
  token, calls `api.anthropic.com/api/oauth/profile` (stable `account.uuid` + label + plan) and
  `/api/oauth/usage` (5h/7d limits), POSTs `{account_uuid, label, session, weekly, …}` to
  `POST $CCSTATS_URL/limits/<uuid>?token=$CCSTATS_TOKEN`. **The OAuth token never leaves the machine.**
  Env: `CCSTATS_URL`, `CCSTATS_TOKEN` (master), `CCSTATS_MACHINE`.
- **`server/ingest-receiver.py`** — runs as `ccsync` on 127.0.0.1:8899 (systemd `ccstats-ingest`),
  nginx-proxied + token-gated. Two routes:
  - `POST /ingest/<machine>` — gzip tar of `*.jsonl` transcripts → `/home/<machine>/.claude/projects`
    (safe extraction, `tarfile` data filter).
  - `POST /limits/<uuid>` — one account's reading → `/var/lib/ccstats/limits-in/<uuid>.json`, then
    rebuilds `/var/www/stats/claude-limits.json` as `{ accounts: [...] }` (freshest per uuid; `stale`
    after 180 s; backward-compat top-level = freshest active account so the badge shows one account).

## Transcript sync

- **`clients/ccstats-sync.sh`** — per-machine transcript push (incremental `tar`-over-transport, no
  rsync). SSH transport for mesh boxes (`ccsync@VM`), or HTTP transport over the tunnel
  (`CCSTATS_URL`+`CCSTATS_TOKEN` → `POST /ingest/<machine>`). Transcripts only; no credentials.

## VM install helpers (deployment-specific reference)

Run on the ccstats VM (Debian). They assume the upstream playbook's layout (`/opt/claude-stats`,
`/var/www/stats`, de-rooted `ccollector` runtime).

- `server/bootstrap.sh` — core install: tokens, `config.json`, webroots, `deploy.sh`, nginx vhost.
- `server/cloudflared-setup.sh` — cloudflared binary + creds + systemd service (tunnel → localhost:80).
- `server/install-ingest.sh` — deploy the ingest receiver + nginx `/ingest/` route.
- `server/install-limits.sh` — deploy the limits receiver + nginx `/limits/` route; retires the
  single-account `ccstats-usage.timer`.

## TODO

- **Badge firmware multi-account** — `firmware/screens_live.py:draw_usage` still shows one account
  (mirror the `viewscreens/screens.js:drawUsage` change). See the owner's badge handoff doc.

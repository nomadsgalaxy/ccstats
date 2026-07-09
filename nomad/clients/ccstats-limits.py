#!/usr/bin/env python3
# ccstats-limits.py — per-account Claude usage-limits poller (ccstats architecture B).
#
# Runs on EACH machine every ~2 min. Reads the machine's CURRENTLY-ACTIVE Claude
# account token LOCALLY, fetches that account's identity + limits from
# api.anthropic.com, and ships ONLY the numeric reading (+ account uuid/label) to
# the ccstats VM over the public tunnel. The OAuth token NEVER leaves this machine.
#
# Hop accounts freely: each run self-identifies via /oauth/profile (account.uuid),
# so whatever account is active right now is what gets reported. Idle/expired token
# => nothing to report (that account ages to HELD on the server).
#
# Env: CCSTATS_URL (https://ccstats.example.com), CCSTATS_TOKEN (master token),
#      CCSTATS_MACHINE (optional label; defaults to hostname).
import json, os, sys, time, socket, urllib.request

CRED    = os.path.expanduser("~/.claude/.credentials.json")
URL     = os.environ.get("CCSTATS_URL", "").rstrip("/")
TOKEN   = os.environ.get("CCSTATS_TOKEN", "")
MACHINE = (os.environ.get("CCSTATS_MACHINE") or socket.gethostname()).lower()
PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"
USAGE_URL   = "https://api.anthropic.com/api/oauth/usage"
SKEW_MS = 60_000   # token counts as usable unless expired by >60s (i.e. a session is active)

def out(msg): print(f"{time.strftime('%F %T')} {msg}")

def api(url, tok):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/json",
        "User-Agent": "ccstats-limits/1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def bucket(b):
    if not isinstance(b, dict): return None
    u = b.get("utilization")
    return {"utilization": round(float(u), 1) if u is not None else None,
            "resets_at": b.get("resets_at")}

def main():
    if not URL or not TOKEN:
        out("set CCSTATS_URL and CCSTATS_TOKEN"); return 2
    try:
        o = (json.load(open(CRED)) or {}).get("claudeAiOauth") or {}
    except Exception as e:
        out(f"no readable creds ({e})"); return 0
    tok = o.get("accessToken")
    exp = float(o.get("expiresAt") or 0)
    if not tok or (exp and exp < time.time() * 1000 - SKEW_MS):
        out("token expired / no active session — nothing to report"); return 0
    try:
        prof  = api(PROFILE_URL, tok)
        usage = api(USAGE_URL, tok)
    except Exception as e:
        out(f"api error ({e})"); return 0
    acct = prof.get("account") or {}
    org  = prof.get("organization") or {}
    uuid = acct.get("uuid")
    if not uuid:
        out("no account uuid in profile"); return 0
    reading = {
        "account_uuid": uuid,
        "label": acct.get("display_name") or acct.get("full_name") or "account",
        "subscription": ("max" if acct.get("has_claude_max")
                         else "pro" if acct.get("has_claude_pro")
                         else (o.get("subscriptionType") or "?")),
        "rate_limit_tier": org.get("rate_limit_tier"),
        "session":       bucket(usage.get("five_hour")),
        "weekly":        bucket(usage.get("seven_day")),
        "weekly_opus":   bucket(usage.get("seven_day_opus")),
        "weekly_sonnet": bucket(usage.get("seven_day_sonnet")),
        "taken_at": int(time.time()),
        "machine": MACHINE,
    }
    body = json.dumps(reading).encode()
    req = urllib.request.Request(f"{URL}/limits/{uuid}?token={TOKEN}",
                                 data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "ccstats-limits/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            out(f"shipped '{reading['label']}' {uuid[:8]} "
                f"sess={(reading['session'] or {}).get('utilization')}% "
                f"wk={(reading['weekly'] or {}).get('utilization')}% -> {r.status}")
    except Exception as e:
        out(f"ship failed ({e})"); return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())

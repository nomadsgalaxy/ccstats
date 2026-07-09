#!/usr/bin/env python3
# ccstats ingest receiver — runs as ccsync on 127.0.0.1:8899. nginx does the token
# check and proxies here. Two routes:
#   POST /ingest/<machine>  : gzip tar of *.jsonl transcripts -> /home/<machine>/.claude/projects
#   POST /limits/<uuid>     : one account's usage-limits reading (JSON) -> rebuilds claude-limits.json
# Safe extraction only (tarfile "data" filter); machine/uuid names are validated.
import http.server, io, os, re, json, time, tarfile, datetime

HOME = "/home"
SUB = ".claude/projects"
LIMITS_IN = "/var/lib/ccstats/limits-in"          # per-account shipped readings (ccsync-owned)
LIMITS_OUT = "/var/www/stats/claude-limits.json"  # served feed (ccsync-owned)
MACHINE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
UUID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")
MAX_TAR = 1024 * 1024 * 1024      # 1 GiB
MAX_JSON = 256 * 1024             # 256 KiB
STALE_S = 180                     # reading older than this => HELD (last-known, exact countdowns)
DROP_S = 14 * 86400               # account unseen this long => dropped from the feed


def resets_in_sec(resets_at):
    if not resets_at:
        return None
    try:
        dt = datetime.datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return max(0, int((dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()))
    except (ValueError, AttributeError):
        return None


def _decorate(bucket):
    if not isinstance(bucket, dict):
        return None
    return {"utilization": bucket.get("utilization"),
            "resets_at": bucket.get("resets_at"),
            "resets_in_sec": resets_in_sec(bucket.get("resets_at"))}


def rebuild_feed():
    """Read every per-account reading, keep freshest per uuid, write the multi-account feed."""
    now = int(time.time())
    best = {}
    try:
        files = os.listdir(LIMITS_IN)
    except OSError:
        files = []
    for fn in files:
        if not fn.endswith(".json"):
            continue
        try:
            r = json.load(open(os.path.join(LIMITS_IN, fn)))
        except (OSError, ValueError):
            continue
        u = r.get("account_uuid")
        if not u or (now - int(r.get("taken_at") or 0)) > DROP_S:
            continue
        if u not in best or int(r.get("taken_at") or 0) > int(best[u].get("taken_at") or 0):
            best[u] = r
    accounts = []
    for u, r in best.items():
        stale = (now - int(r.get("taken_at") or 0)) > STALE_S
        accounts.append({
            "account_uuid": u,
            "label": r.get("label") or "account",
            "subscription": r.get("subscription"),
            "rate_limit_tier": r.get("rate_limit_tier"),
            "session": _decorate(r.get("session")),
            "weekly": _decorate(r.get("weekly")),
            "weekly_opus": _decorate(r.get("weekly_opus")),
            "weekly_sonnet": _decorate(r.get("weekly_sonnet")),
            "machine": r.get("machine"),
            "taken_at": r.get("taken_at"),
            "stale": stale,
        })
    accounts.sort(key=lambda a: (a["stale"], a["label"].lower()))
    feed = {
        "schema_version": 2,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "accounts": accounts,
    }
    # backward-compat top-level = freshest non-stale account (older single-account consumers)
    live = [a for a in accounts if not a["stale"]] or accounts
    if live:
        top = max(live, key=lambda a: int(a.get("taken_at") or 0))
        feed.update({"session": top["session"], "weekly": top["weekly"],
                     "stale": top["stale"], "source": top["label"]})
    # Written in place (ccsync owns the file but not the ccollector-owned webroot dir,
    # so a temp-file rename would need dir write we don't have). ponytail: in-place write,
    # tiny read-during-write race on a <few-KB file; switch to temp+rename if it ever matters.
    with open(LIMITS_OUT, "w") as fh:
        json.dump(feed, fh, separators=(",", ":"))
    return len(accounts)


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith("/limits/"):
            return self.handle_limits()
        if self.path.startswith("/ingest/"):
            return self.handle_ingest()
        return self.reply(404, "unknown route")

    def handle_limits(self):
        m = re.match(r"^/limits/([^/?]+)", self.path)
        uuid = m.group(1) if m else ""
        if not UUID_RE.match(uuid):
            return self.reply(400, "bad account uuid")
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > MAX_JSON:
                return self.reply(413, "bad/too-large body")
            r = json.loads(self.rfile.read(n).decode())
            if r.get("account_uuid") != uuid:
                return self.reply(400, "uuid mismatch")
            os.makedirs(LIMITS_IN, exist_ok=True)
            tmp = os.path.join(LIMITS_IN, uuid + ".json.tmp")
            with open(tmp, "w") as fh:
                json.dump(r, fh, separators=(",", ":"))
            os.replace(tmp, os.path.join(LIMITS_IN, uuid + ".json"))
            k = rebuild_feed()
            return self.reply(200, f"ok accounts={k}")
        except Exception as e:
            return self.reply(500, f"error {type(e).__name__}: {e}")

    def handle_ingest(self):
        m = re.match(r"^/ingest/([^/?]+)", self.path)
        machine = (m.group(1).lower() if m else "")
        if not MACHINE_RE.match(machine):
            return self.reply(400, "bad machine name")
        if not os.path.isdir(os.path.join(HOME, machine)):
            return self.reply(409, f"unknown machine '{machine}' (create /home/{machine} first)")
        dest = os.path.join(HOME, machine, SUB)
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > MAX_TAR:
                return self.reply(413, "bad/too-large body")
            body = self.rfile.read(n)
            os.makedirs(dest, exist_ok=True)
            count = 0
            with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tf:
                members = []
                for ti in tf.getmembers():
                    if not ti.isreg():
                        continue
                    p = os.path.normpath(ti.name)
                    if p.startswith("/") or p.startswith(".."):
                        continue
                    ti.name = p
                    members.append(ti)
                    count += 1
                tf.extractall(dest, members=members, filter="data")
            return self.reply(200, f"ok {count}")
        except Exception as e:
            return self.reply(500, f"error {type(e).__name__}: {e}")

    def reply(self, code, msg):
        b = (msg + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    http.server.HTTPServer(("127.0.0.1", 8899), H).serve_forever()

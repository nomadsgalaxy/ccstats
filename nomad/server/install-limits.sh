#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
OPT=/opt/claude-stats
VHOST=/etc/nginx/sites-available/ccstats.conf

# 1) new receiver (handles /ingest/ tars AND /limits/<uuid> readings)
install -m755 /tmp/ingest-receiver.py "$OPT/ingest-receiver.py"

# 2) per-account inbox + served feed, both ccsync-writable
install -d -m755 -o ccsync -g ccsync /var/lib/ccstats /var/lib/ccstats/limits-in
touch /var/www/stats/claude-limits.json
chown ccsync:www-data /var/www/stats/claude-limits.json
chmod 644 /var/www/stats/claude-limits.json

# 3) retire the single-account poller (no local creds here; the shipped per-account feed replaces it)
systemctl disable --now ccstats-usage.timer 2>/dev/null || true
systemctl stop ccstats-usage.service 2>/dev/null || true

systemctl restart ccstats-ingest
sleep 2
systemctl is-active ccstats-ingest

# 4) nginx: token-gated /limits/<uuid> ingest route (before the catch-all)
TOKEN=$(cat "$OPT/token.txt")
python3 - "$VHOST" "$TOKEN" <<'PY'
import sys
vhost, token = sys.argv[1], sys.argv[2]
s = open(vhost).read()
if "/limits/" in s:
    print("limits location already present"); sys.exit(0)
block = (
    '    # ── per-account usage-limits ingest (token-gated push from each machine) ──\n'
    '    location ~ ^/limits/[0-9a-fA-F-]+$ {\n'
    '        if ($arg_token != "%s") { return 403; }\n'
    '        proxy_pass http://127.0.0.1:8899;\n'
    '        proxy_read_timeout 60s;\n'
    '        client_max_body_size 256k;\n'
    '        add_header X-Robots-Tag "noindex" always;\n'
    '    }\n\n'
) % token
marker = "    location / { return 404; }"
assert marker in s, "catch-all not found"
s = s.replace(marker, block + marker, 1)
open(vhost, "w").write(s)
print("inserted /limits/ location")
PY

nginx -t
systemctl reload nginx
echo "LIMITS-RECEIVER OK"

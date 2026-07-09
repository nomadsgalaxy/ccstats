#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
OPT=/opt/claude-stats
VHOST=/etc/nginx/sites-available/ccstats.conf

install -m755 /tmp/ingest-receiver.py "$OPT/ingest-receiver.py"

cat > /etc/systemd/system/ccstats-ingest.service <<'UNIT'
[Unit]
Description=ccstats transcript ingest receiver (localhost:8899)
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/claude-stats/ingest-receiver.py
User=ccsync
Group=ccsync
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=full
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now ccstats-ingest
sleep 2
systemctl is-active ccstats-ingest

# Insert the token-gated /ingest/ nginx location before the catch-all "location /".
TOKEN=$(cat "$OPT/token.txt")
python3 - "$VHOST" "$TOKEN" <<'PY'
import sys
vhost, token = sys.argv[1], sys.argv[2]
s = open(vhost).read()
if "/ingest/" in s:
    print("ingest location already present"); sys.exit(0)
block = (
    '    # ── transcript ingest (token-gated push from remote machines) ──\n'
    '    location ~ ^/ingest/[a-z0-9][a-z0-9-]*$ {\n'
    '        if ($arg_token != "%s") { return 403; }\n'
    '        proxy_pass http://127.0.0.1:8899;\n'
    '        proxy_read_timeout 300s;\n'
    '        client_max_body_size 1024m;\n'
    '        add_header X-Robots-Tag "noindex" always;\n'
    '    }\n\n'
) % token
marker = "    location / { return 404; }"
assert marker in s, "catch-all location not found"
s = s.replace(marker, block + marker, 1)
open(vhost, "w").write(s)
print("inserted /ingest/ location")
PY

nginx -t
systemctl reload nginx
echo "INGEST OK"

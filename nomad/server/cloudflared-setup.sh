#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
UUID=00000000-0000-0000-0000-000000000000

install -d -m755 /etc/cloudflared
install -m600 /tmp/ccstats-creds.json /etc/cloudflared/ccstats-creds.json
rm -f /tmp/ccstats-creds.json

cat > /etc/cloudflared/config.yml <<CFG
tunnel: $UUID
credentials-file: /etc/cloudflared/ccstats-creds.json
no-autoupdate: true

ingress:
  - hostname: ccstats.example.com
    service: http://localhost:80
  - service: http_status:404
CFG

if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
       -o /usr/local/bin/cloudflared
  chmod +x /usr/local/bin/cloudflared
fi
cloudflared --version

cat > /etc/systemd/system/cloudflared.service <<'UNIT'
[Unit]
Description=cloudflared tunnel (ccstats)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run
Restart=on-failure
RestartSec=5
User=root
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now cloudflared
sleep 6
echo "=== cloudflared status ==="
systemctl is-active cloudflared
journalctl -u cloudflared --no-pager -n 12 | sed 's/[A-Za-z0-9._-]*TunnelSecret[^ ]*/<redacted>/g'

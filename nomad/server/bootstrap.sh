#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
REPO=/opt/ccstats-src/server
OPT=/opt/claude-stats
WEB=/var/www/stats
DOMAIN=ccstats.example.com

install -d -m755 "$OPT"
[ -s "$OPT/token.txt" ]      || python3 -c "import secrets;print(secrets.token_urlsafe(32))" > "$OPT/token.txt"
[ -s "$OPT/peer-token.txt" ] || python3 -c "import secrets;print(secrets.token_urlsafe(32))" > "$OPT/peer-token.txt"
chmod 600 "$OPT/token.txt" "$OPT/peer-token.txt"

cat > "$OPT/config.json" <<'JSON'
{
  "timezone": "America/New_York",
  "server": "homelab",
  "project_granularity": "directory",
  "alias": "Nomad",
  "live_monitor": {},
  "peers": []
}
JSON
chmod 600 "$OPT/config.json"

install -m755 "$REPO/pipeline/extract.py"      "$OPT/extract.py"
install -m644 "$REPO/pipeline/pricing.json"    "$OPT/pricing.json"
install -m755 "$REPO/monitor/usage-monitor.py" "$OPT/usage-monitor.py"

install -d -m755 -o root -g www-data "$WEB" "$WEB/fragments"
install -d -o www-data -g www-data "$WEB/viewscreens" "$WEB/viewscreens/fonts" "$WEB/livetest"
[ -f "$WEB/competitor.json" ]  || install -o www-data -g www-data /dev/null "$WEB/competitor.json"
[ -f "$WEB/competition.json" ] || install -o www-data -g www-data /dev/null "$WEB/competition.json"

# dedicated restricted user for Windows->VM transcript sync
id ccsync >/dev/null 2>&1 || useradd --create-home --shell /bin/bash ccsync

echo "########## deploy.sh ##########"
bash "$REPO/deploy.sh"

echo "########## nginx vhost ##########"
TOKEN=$(cat "$OPT/token.txt"); PEER=$(cat "$OPT/peer-token.txt")
sed -e "s|__DOMAIN__|$DOMAIN|g" -e "s|__TOKEN__|$TOKEN|g" -e "s|__WEBROOT__|$WEB|g" -e "s|__PEER_TOKEN__|$PEER|g" \
    "$REPO/nginx/stats-site.conf.template" > /etc/nginx/sites-available/ccstats.conf
ln -sf /etc/nginx/sites-available/ccstats.conf /etc/nginx/sites-enabled/ccstats.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "########## RESULT ##########"
echo "TOKEN=$TOKEN"
echo "PEER_TOKEN=$PEER"
ls -la "$WEB"/*.json 2>/dev/null || true
echo "--- timers ---"; systemctl list-timers 'ccstats-*' --no-pager 2>/dev/null | head

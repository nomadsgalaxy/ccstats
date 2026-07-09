# ccstats — e-ink (Badger 2350) device secrets. Copy to firmware-badger/secrets.py,
# fill in, then push to the badge with `python tools/install-badger-secrets.py`.
# secrets.py is gitignored and must NEVER be committed.
#
# On the badge these land in the device-root /secrets.py, which the badgeware
# `secrets` module reads. The installer preserves the stock REGION/TIMEZONE
# (used by the clock app) and only overrides the keys below.

# WiFi — the Badger's framework `wifi` module joins a single network.
WIFI_SSID = "your-wifi-ssid"
WIFI_PASSWORD = "your-wifi-password"

# Base URL of your stats server (no trailing slash) + its access token.
STATS_BASE_URL = "https://stats.example.net"
STATS_TOKEN = "paste-your-access-token"

# Display name shown on the badge.
ALIAS = "YourName"

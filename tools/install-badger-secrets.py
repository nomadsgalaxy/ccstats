#!/usr/bin/env python3
# ccstats — push e-ink (Badger 2350) secrets to the device-root /secrets.py.
#
# Reads your LOCAL firmware-badger/secrets.py (gitignored; copy it from
# secrets.example.py and fill it in), then rewrites the badge's root
# /secrets.py = the stock /system/secrets.py contents (so REGION/TIMEZONE for
# the clock app are preserved) with your WiFi + ccstats keys applied on top.
#
# The badgeware `secrets` module reads root /secrets.py and does NOT merge the
# stock file, so this merge is what keeps both apps working. No credentials are
# hardcoded here — everything comes from your secrets.py.
#
# Usage:  python tools/install-badger-secrets.py [PORT]   (default COM8)

import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_PATH = os.path.join(REPO_ROOT, "firmware-badger", "secrets.py")

KEYS = ("WIFI_SSID", "WIFI_PASSWORD", "STATS_BASE_URL", "STATS_TOKEN", "ALIAS")

ONDEVICE = '''\
OVERRIDE = %r

# Load the stock config (keeps REGION/TIMEZONE for the clock app), apply our
# overrides, and rewrite root /secrets.py from the merged dict.
ns = {}
try:
    exec(open("/system/secrets.py").read(), ns)
except OSError:
    pass
cfg = {k: v for k, v in ns.items() if k.isupper() and not k.startswith("_")}
cfg.update(OVERRIDE)

lines = ["%%s = %%r" %% (k, cfg[k]) for k in sorted(cfg)]
with open("/secrets.py", "w") as f:
    f.write("\\n".join(lines) + "\\n")

import secrets  # fresh read of the rebuilt root file
print("secrets keys:", [n for n in dir(secrets) if n.isupper()])
print("WIFI_SSID:", getattr(secrets, "WIFI_SSID", "(unset)"))
print("has STATS_BASE_URL:", hasattr(secrets, "STATS_BASE_URL"),
      "| ALIAS:", getattr(secrets, "ALIAS", "(none)"))
'''


def load_local_secrets():
    if not os.path.exists(SECRETS_PATH):
        sys.exit("no %s — copy firmware-badger/secrets.example.py to it and fill it in"
                 % SECRETS_PATH)
    namespace = {}
    with open(SECRETS_PATH) as f:
        exec(f.read(), namespace)  # noqa: S102 -- local, user-owned config
    override = {}
    for key in KEYS:
        if key in namespace:
            override[key] = namespace[key]
    missing = [k for k in ("STATS_BASE_URL", "STATS_TOKEN") if k not in override]
    if missing:
        sys.exit("firmware-badger/secrets.py is missing: %s" % ", ".join(missing))
    return override


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    override = load_local_secrets()
    mpremote = [sys.executable, "-m", "mpremote", "connect", port]
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(ONDEVICE % (override,))
        script_path = f.name
    try:
        subprocess.run(mpremote + ["run", script_path], check=True)
    finally:
        os.unlink(script_path)


if __name__ == "__main__":
    main()

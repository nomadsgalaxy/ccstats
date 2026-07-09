#!/usr/bin/env python3
# ccstats — install the e-ink (Badger 2350) app to /system/apps/ccstats.
#
# Mirrors tools/install-app.py: /system (FAT) is mounted read-only at runtime
# and every mpremote call soft-resets the board, so the whole install runs in
# ONE generated on-device script that remounts /system read-write, writes the
# app files, sweeps stale ones, and resets. A guard aborts if the remounted
# /system doesn't look like the badge's app partition (wrong flash geometry).
#
# The app reuses the LCD firmware's http_client.py + certificate_authorities.py
# verbatim (they're display-agnostic), plus the two badge-specific files under
# firmware-badger/. secrets are NOT app content — /secrets.py lives at the
# device root; use tools/install-badger-secrets.py for that.
#
# Usage:  python tools/install-badger.py [PORT]   (default COM8)

import base64
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (source path, name on device) — DERIVED nowhere; this list IS the app.
APP_FILES = [
    (os.path.join(REPO_ROOT, "firmware", "http_client.py"), "http_client.py"),
    (os.path.join(REPO_ROOT, "firmware", "certificate_authorities.py"), "certificate_authorities.py"),
    (os.path.join(REPO_ROOT, "firmware-badger", "ccfetch.py"), "ccfetch.py"),
    (os.path.join(REPO_ROOT, "firmware-badger", "__init__.py"), "__init__.py"),
    # The badgewa.re menu lists an app only if <app>/icon.png exists — without
    # it the app installs fine but never appears in the launcher.
    (os.path.join(REPO_ROOT, "firmware-badger", "icon.png"), "icon.png"),
]

APP_DIR = "/system/apps/ccstats"

INSTALLER = '''\
import binascii
import os
import rp2
import vfs

os.umount("/system")
user_flash_size = rp2.Flash().ioctl(4, 0) * rp2.Flash().ioctl(5, 0)
vfs.mount(vfs.VfsFat(rp2.Flash(start=0, len=user_flash_size - 1024 * 1024)), "/system")

apps = os.listdir("/system/apps")
print("flash bytes:", user_flash_size, "| apps seen:", apps)
if "menu" not in apps:
    raise SystemExit("unexpected /system layout (no 'menu' app) - aborting, nothing written")

try:
    os.mkdir("%s")
except OSError:
    pass

APP_FILES = {
%s}

for file_name, encoded in APP_FILES.items():
    data = binascii.a2b_base64(encoded)
    with open("%s/" + file_name, "wb") as f:
        f.write(data)
    print("wrote", file_name, len(data), "bytes")

expected = set(APP_FILES)
for file_name in os.listdir("%s"):
    if file_name not in expected:
        try:
            os.remove("%s/" + file_name)
            print("removed stale", file_name)
        except OSError:
            pass

print("installed:", sorted(os.listdir("%s")))
'''


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    mpremote = [sys.executable, "-m", "mpremote", "connect", port]

    entries = []
    for source_path, device_name in APP_FILES:
        with open(source_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        entries.append("    %r: %r,\n" % (device_name, encoded))
    print("installing %d files to %s: %s" % (
        len(APP_FILES), APP_DIR, " ".join(n for _, n in APP_FILES)))

    script = INSTALLER % (APP_DIR, "".join(entries), APP_DIR, APP_DIR, APP_DIR, APP_DIR)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name
    try:
        subprocess.run(mpremote + ["run", script_path], check=True)
        subprocess.run(mpremote + ["reset"], check=True)
        print("done — reset. Open the badge menu and pick 'Ccstats'.")
    finally:
        os.unlink(script_path)


if __name__ == "__main__":
    main()

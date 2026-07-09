#!/usr/bin/env python3
# Idempotent patch: make ccstats' directory-mode project name a separator-agnostic
# basename, so Windows cwds (backslashes) yield the folder name, not the full path.
import sys

OLD = '        base = os.path.basename(cwd.rstrip("/"))'
NEW = '        base = cwd.replace("\\\\", "/").rstrip("/").split("/")[-1]'

f = sys.argv[1]
s = open(f, encoding="utf-8").read()
if NEW in s:
    print("already patched:", f); sys.exit(0)
if OLD not in s:
    print("PATTERN NOT FOUND in", f); sys.exit(2)
open(f, "w", encoding="utf-8").write(s.replace(OLD, NEW, 1))
print("patched:", f)

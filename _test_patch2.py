#!/usr/bin/env python3
"""Test if curl-suppress-connect-headers.patch applies cleanly to cf-h1-proxy.c"""
import subprocess
import shutil
from pathlib import Path

ROOT = Path(r"d:\curl-impersonate-8.20.0")
TMP = ROOT / "_patch_test2"
ORIG_C = ROOT / "_curl_cf_h1_proxy_orig.c"
PATCH = ROOT / "patches_new" / "curl-suppress-connect-headers.patch"

# Setup
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)

# Create lib/ directory structure to match patch paths
lib_dir = TMP / "lib"
lib_dir.mkdir()
shutil.copy2(ORIG_C, lib_dir / "cf-h1-proxy.c")

# Init git
subprocess.run(["git", "init"], cwd=TMP, check=True, capture_output=True)
subprocess.run(["git", "config", "user.email", "test@local"], cwd=TMP, check=True, capture_output=True)
subprocess.run(["git", "config", "user.name", "test"], cwd=TMP, check=True, capture_output=True)
subprocess.run(["git", "add", "-A"], cwd=TMP, check=True, capture_output=True)
subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=TMP, check=True, capture_output=True)

# Test patch with --check
print("Testing patch with --check...")
r = subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=TMP, capture_output=True, text=True)
if r.returncode == 0:
    print("[OK] Patch applies cleanly (dry-run)")
else:
    print(f"[FAIL] Patch check failed (exit {r.returncode})")
    print("STDOUT:", r.stdout)
    print("STDERR:", r.stderr)
    exit(1)

# Actually apply
print("\nApplying patch for real...")
r = subprocess.run(["git", "apply", str(PATCH)], cwd=TMP, capture_output=True, text=True)
if r.returncode == 0:
    print("[OK] Patch applied successfully")
else:
    print(f"[FAIL] Apply failed (exit {r.returncode})")
    print("STDERR:", r.stderr)
    exit(1)

# Show the modified region
print("\n--- Modified region (around the change) ---")
url_c = lib_dir / "cf-h1-proxy.c"
lines = url_c.read_text(encoding='utf-8').splitlines()
# Find our comment
for i, line in enumerate(lines, 1):
    if 'curl-impersonate: Do NOT send CONNECT' in line:
        start = max(0, i - 5)
        end = min(len(lines), i + 25)
        for j in range(start, end):
            print(f"{j+1:5d}: {lines[j]}")
        break

print("\n[OK] All tests passed")

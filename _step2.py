# Step 2 v2: Download deps using official repos + ghfast.top mirror,
# extract with Python's tarfile/zipfile (no xz/bzip2 dependency)
# git baseline for each dep
import subprocess, os, sys, shutil, tarfile, zipfile

BASE = r"d:\curl-impersonate-8.20.0"
DEPS = os.path.join(BASE, "deps")
CURL_BAT = r"C:\Users\hmz\bin\curl.bat"
os.makedirs(DEPS, exist_ok=True)

def run(cmd, cwd=None, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr[:500]}")
        return False
    return True

def curl_download(url, output_path, timeout=1800):
    print(f"  Downloading: {url}")
    sys.stdout.flush()
    try:
        r = subprocess.run(
            ["cmd", "/c", CURL_BAT, "-L", "--retry", "3", "-o", output_path, url],
            timeout=timeout
        )
        if r.returncode != 0:
            print(f"  FAILED (return code {r.returncode})")
            return False
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            print(f"  FAILED (file too small or missing)")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
        sz = os.path.getsize(output_path)
        print(f"  OK ({sz:,} bytes)")
        return True
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT ({timeout}s)")
        return False

def extract_archive(archive_path, dest_dir):
    """Extract archive using Python's built-in modules"""
    name = os.path.basename(archive_path)
    print(f"  Extracting: {name}")
    try:
        if name.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(dest_dir)
        elif name.endswith('.tar.xz') or name.endswith('.tar.bz2') or name.endswith('.tar.gz') or name.endswith('.tgz'):
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(dest_dir)
        else:
            print(f"  Unknown archive format: {name}")
            return False
        print(f"  OK")
        return True
    except Exception as e:
        print(f"  EXTRACT ERROR: {e}")
        return False

def git_init_commit(path, msg):
    print(f"  git init + commit: {os.path.basename(path)}")
    git_dir = os.path.join(path, ".git")
    if os.path.exists(git_dir):
        shutil.rmtree(git_dir, ignore_errors=True)
    if not run(["git", "init"], cwd=path): return False
    if not run(["git", "add", "-A"], cwd=path): return False
    run(["git", "config", "user.email", "build@local"], cwd=path)
    run(["git", "config", "user.name", "build"], cwd=path)
    if not run(["git", "commit", "-m", msg], cwd=path): return False
    return True

# Download list: (archive_name, url, extracted_top_dir_name, target_dir_name)
# Using official repos with ghfast.top mirror for GitHub URLs
# BoringSSL uses full commit hash
downloads = [
    ("curl-8.20.0.tar.xz",
     "https://curl.se/download/curl-8.20.0.tar.xz",
     "curl-8.20.0", "curl-8.20.0"),

    ("boringssl-673e61fc2.zip",
     "https://ghfast.top/https://github.com/google/boringssl/archive/673e61fc215b178a90c0e67858bbf162c8158993.zip",
     "boringssl-673e61fc215b178a90c0e67858bbf162c8158993", "boringssl"),

    ("brotli-1.2.0.tar.gz",
     "https://ghfast.top/https://github.com/google/brotli/archive/refs/tags/v1.2.0.tar.gz",
     "brotli-1.2.0", "brotli-1.2.0"),

    ("nghttp2-1.63.0.tar.bz2",
     "https://ghfast.top/https://github.com/nghttp2/nghttp2/releases/download/v1.63.0/nghttp2-1.63.0.tar.bz2",
     "nghttp2-1.63.0", "nghttp2-1.63.0"),

    ("ngtcp2-1.20.0.tar.bz2",
     "https://ghfast.top/https://github.com/ngtcp2/ngtcp2/releases/download/v1.20.0/ngtcp2-1.20.0.tar.bz2",
     "ngtcp2-1.20.0", "ngtcp2-1.20.0"),

    ("nghttp3-1.15.0.tar.bz2",
     "https://ghfast.top/https://github.com/ngtcp2/nghttp3/releases/download/v1.15.0/nghttp3-1.15.0.tar.bz2",
     "nghttp3-1.15.0", "nghttp3-1.15.0"),

    ("zstd-1.5.7.tar.gz",
     "https://ghfast.top/https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz",
     "zstd-1.5.7", "zstd-1.5.7"),

    ("zlib-1.3.1.tar.gz",
     "https://ghfast.top/https://github.com/madler/zlib/archive/refs/tags/v1.3.1.tar.gz",
     "zlib-1.3.1", "zlib-1.3.1"),
]

print("=" * 60)
print(" Step 2 v2: Download deps + git baseline")
print("=" * 60)

for archive_name, url, extracted_name, target_name in downloads:
    archive_path = os.path.join(DEPS, archive_name)
    target_dir = os.path.join(DEPS, target_name)

    # Skip if already done
    if os.path.exists(os.path.join(target_dir, ".git")):
        print(f"[SKIP] {target_name}: already done (has .git)")
        continue

    print(f"\n--- {target_name} ---")

    # Download
    if not os.path.exists(archive_path):
        if not curl_download(url, archive_path):
            print(f"[FAIL] Cannot download {archive_name}")
            continue
    else:
        print(f"[EXISTS] {archive_name} ({os.path.getsize(archive_path):,} bytes)")

    # Extract
    if not os.path.exists(target_dir):
        if not extract_archive(archive_path, DEPS):
            print(f"[FAIL] Cannot extract {archive_name}")
            continue
        # Rename if extracted name differs from target
        extracted_path = os.path.join(DEPS, extracted_name)
        if extracted_name != target_name and os.path.exists(extracted_path):
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            os.rename(extracted_path, target_dir)
            print(f"  RENAMED {extracted_name} -> {target_name}")
        # Check again
        if not os.path.exists(target_dir):
            # Maybe extracted with different name
            print(f"  Looking for extracted directory...")
            for d in os.listdir(DEPS):
                full = os.path.join(DEPS, d)
                if os.path.isdir(full) and not os.path.exists(os.path.join(full, ".git")):
                    if target_name.replace("-", "") in d.replace("-", "").lower() or d.replace("-", "").lower() in target_name.replace("-", ""):
                        os.rename(full, target_dir)
                        print(f"  RENAMED {d} -> {target_name}")
                        break
    else:
        print(f"[EXISTS] {target_name}/")

    # Git init + commit
    if os.path.exists(target_dir) and not os.path.exists(os.path.join(target_dir, ".git")):
        print(f"[GIT] {target_name} baseline...")
        if git_init_commit(target_dir, f"{target_name} baseline"):
            print(f"  OK")
        else:
            print(f"  FAILED!")

# Delete archives to save space
print("\n[CLEANUP] Deleting archives...")
for archive_name, _, _, _ in downloads:
    p = os.path.join(DEPS, archive_name)
    if os.path.exists(p):
        os.remove(p)
        print(f"  Deleted {archive_name}")

# Clone lexiforest for reference (for Step 3 analysis)
print("\n[LEXIFOREST] Cloning reference repo...")
LEXI = os.path.join(BASE, "lexiforest_ref")
if os.path.exists(os.path.join(LEXI, ".git")):
    print("  Already exists, skip")
else:
    if os.path.exists(LEXI):
        shutil.rmtree(LEXI, ignore_errors=True)
    try:
        r = subprocess.run(
            ["git", "clone", "--depth=1",
             "https://ghfast.top/https://github.com/lexiforest/curl-impersonate.git",
             LEXI],
            timeout=600
        )
        if r.returncode == 0:
            print("  OK (via ghfast.top)")
        else:
            print("  ghfast.top failed, trying direct...")
            r = subprocess.run(
                ["git", "clone", "--depth=1",
                 "https://github.com/lexiforest/curl-impersonate.git",
                 LEXI],
                timeout=600
            )
            print("  OK (direct)" if r.returncode == 0 else "  FAILED!")
    except Exception as e:
        print(f"  FAILED: {e}")

# Project root git init
print("\n[ROOT] Project root git init...")
if os.path.exists(os.path.join(BASE, ".git")):
    print("  Already exists, skip")
else:
    if git_init_commit(BASE, "Step 1+2: baseline"):
        print("  OK")
    else:
        print("  FAILED!")

# Summary
print("\n" + "=" * 60)
print(" Step 2 Status Summary")
print("=" * 60)
for d in sorted(os.listdir(DEPS)):
    full = os.path.join(DEPS, d)
    if os.path.isdir(full):
        has_git = os.path.exists(os.path.join(full, ".git"))
        print(f"  {d}: git={'OK' if has_git else 'MISSING'}")

lexi_ok = os.path.exists(os.path.join(LEXI, ".git")) if os.path.exists(LEXI) else False
root_ok = os.path.exists(os.path.join(BASE, ".git"))
print(f"  lexiforest_ref: {'OK' if lexi_ok else 'MISSING'}")
print(f"  project root git: {'OK' if root_ok else 'MISSING'}")
print("\n=== Step 2 Complete ===")

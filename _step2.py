# Step 2: Download deps, git baseline, clone lexiforest ref
import subprocess, os, sys, shutil

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
    """使用 curl.bat 下载文件（自动检测系统代理）"""
    print(f"  下载: {url}")
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
            return False
        sz = os.path.getsize(output_path)
        print(f"  OK ({sz:,} bytes)")
        return True
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT ({timeout}s)")
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

# Download list: (archive_name, url, extracted_dir_name, target_dir_name)
downloads = [
    ("curl-8.20.0.tar.xz",
     "https://curl.se/download/curl-8.20.0.tar.xz",
     "curl-8.20.0", "curl-8.20.0"),
    ("boringssl-673e61fc2.zip",
     "https://github.com/nicowilliams/boringssl/archive/673e61fc2.zip",
     "boringssl-673e61fc2", "boringssl"),
    ("brotli-1.2.0.tar.gz",
     "https://github.com/nicowilliams/brotli/archive/refs/tags/v1.2.0.tar.gz",
     "brotli-1.2.0", "brotli-1.2.0"),
    ("nghttp2-1.63.0.tar.bz2",
     "https://github.com/nghttp2/nghttp2/releases/download/v1.63.0/nghttp2-1.63.0.tar.bz2",
     "nghttp2-1.63.0", "nghttp2-1.63.0"),
    ("ngtcp2-1.20.0.tar.bz2",
     "https://github.com/ngtcp2/ngtcp2/releases/download/v1.20.0/ngtcp2-1.20.0.tar.bz2",
     "ngtcp2-1.20.0", "ngtcp2-1.20.0"),
    ("nghttp3-1.15.0.tar.bz2",
     "https://github.com/ngtcp2/nghttp3/releases/download/v1.15.0/nghttp3-1.15.0.tar.bz2",
     "nghttp3-1.15.0", "nghttp3-1.15.0"),
    ("zstd-1.5.7.tar.gz",
     "https://github.com/nicowilliams/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz",
     "zstd-1.5.7", "zstd-1.5.7"),
    ("zlib-1.3.1.tar.gz",
     "https://zlib.net/fossils/zlib-1.3.1.tar.gz",
     "zlib-1.3.1", "zlib-1.3.1"),
]

print("=" * 60)
print(" Step 2: 下载依赖 + 建立git基线")
print("=" * 60)

for archive_name, url, extracted_name, target_name in downloads:
    archive_path = os.path.join(DEPS, archive_name)
    target_dir = os.path.join(DEPS, target_name)

    # Skip if already done
    if os.path.exists(os.path.join(target_dir, ".git")):
        print(f"[SKIP] {target_name}: 已完成（有.git）")
        continue

    print(f"\n--- {target_name} ---")

    # Download
    if not os.path.exists(target_dir):
        if not os.path.exists(archive_path):
            if not curl_download(url, archive_path):
                print(f"[FAIL] 无法下载 {archive_name}，跳过")
                continue
        else:
            print(f"[EXISTS] {archive_name} ({os.path.getsize(archive_path):,} bytes)")

    # Extract
    if not os.path.exists(target_dir):
        print(f"[EXTRACT] {archive_name}...")
        extracted_path = os.path.join(DEPS, extracted_name)
        r = subprocess.run(
            ["tar", "-xf", archive_path, "-C", DEPS],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            print(f"  EXTRACT ERROR: {r.stderr[:300]}")
            continue
        # Rename if needed
        if extracted_name != target_name and os.path.exists(extracted_path):
            os.rename(extracted_path, target_dir)
            print(f"  RENAMED {extracted_name} -> {target_name}")
        # Also handle case where tar extracts with different name
        if not os.path.exists(target_dir) and os.path.exists(extracted_path):
            os.rename(extracted_path, target_dir)
        print(f"  OK - {target_dir}")
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
print("\n[CLEANUP] 删除下载包...")
for archive_name, _, _, _ in downloads:
    p = os.path.join(DEPS, archive_name)
    if os.path.exists(p):
        os.remove(p)
        print(f"  删除 {archive_name}")

# Clone lexiforest for reference (for Step 3 analysis)
print("\n[LEXIFOREST] 克隆参考仓库...")
LEXI = os.path.join(BASE, "lexiforest_ref")
if os.path.exists(LEXI):
    print("  已存在, 跳过")
else:
    try:
        # 使用 ghfast.top 镜像加速 GitHub 克隆
        r = subprocess.run(
            ["git", "clone", "--depth=1",
             "https://ghfast.top/https://github.com/lexiforest/curl-impersonate.git",
             LEXI],
            timeout=600
        )
        if r.returncode == 0:
            print("  OK (via ghfast.top mirror)")
        else:
            print("  ghfast.top 失败，尝试直连...")
            r = subprocess.run(
                ["git", "clone", "--depth=1",
                 "https://github.com/lexiforest/curl-impersonate.git",
                 LEXI],
                timeout=600
            )
            if r.returncode == 0:
                print("  OK (direct)")
            else:
                print("  FAILED!")
    except subprocess.TimeoutExpired:
        print("  TIMEOUT")
    except Exception as e:
        print(f"  FAILED: {e}")

# Project root git init
print("\n[ROOT] 项目根git初始化...")
if os.path.exists(os.path.join(BASE, ".git")):
    print("  已存在, 跳过")
else:
    if git_init_commit(BASE, "Step 1+2: baseline"):
        print("  OK")
    else:
        print("  FAILED!")

# Summary
print("\n" + "=" * 60)
print(" Step 2 状态总结")
print("=" * 60)
for d in sorted(os.listdir(DEPS)):
    full = os.path.join(DEPS, d)
    if os.path.isdir(full):
        has_git = os.path.exists(os.path.join(full, ".git"))
        print(f"  {d}: git={'OK' if has_git else 'MISSING'}")

lexi_ok = os.path.exists(os.path.join(LEXI, ".git")) if os.path.exists(LEXI) else False
root_ok = os.path.exists(os.path.join(BASE, ".git"))
print(f"  lexiforest_ref: {'OK' if lexi_ok else 'MISSING'}")
print(f"  项目根git: {'OK' if root_ok else 'MISSING'}")
print("\n=== Step 2 完成 ===")

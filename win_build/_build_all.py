#!/usr/bin/env python3
"""
_build_all.py - Unified build script for curl-impersonate Windows

Builds x86 and x64 DLL+lib from scratch:
1. Clean all intermediate files (build/deps/install)
2. Download original source archives
3. Apply patches from patches/ directory
4. Build all dependencies in correct order
5. Build curl-impersonate DLL for each architecture
6. Verify DLL functionality
7. Clean intermediate files, keep only final output

Usage: python _build_all.py [options]
  --arch=x64,x86     Target architectures (default: x64,x86)
  --vs=2022          Visual Studio version (default: 2022)
  --skip-clean       Skip initial cleanup
  --skip-build       Skip build (for testing)
  --keep-intermediates  Keep build/deps/install directories
  --only-arch=x64    Build only one architecture
"""

import os
import sys
import shutil
import subprocess
import glob
import time
import json
import hashlib
import tarfile
import urllib.request
import zipfile
import tempfile
import argparse
import struct
import re
from pathlib import Path

# ============================================================
# Configuration
# ============================================================
ROOT_DIR = Path(__file__).resolve().parent
WIN_BUILD_DIR = ROOT_DIR  # helper scripts are in the same directory
PATCHES_DIR = ROOT_DIR / "patches"

# Version numbers (must match config.bat)
CURL_VERSION = "8.20.0"
CURL_VERSION_DIR = f"curl-{CURL_VERSION}"
BORINGSSL_COMMIT = "673e61fc215b178a90c0e67858bbf162c8158993"
BROTLI_VERSION = "1.2.0"
NGHTTP2_VERSION = "1.63.0"
NGTCP2_VERSION = "1.20.0"
NGHTTP3_VERSION = "1.15.0"
ZLIB_VERSION = "1.3.1"
ZSTD_VERSION = "1.5.7"
LIBSSH2_VERSION = "1.11.1"

# Download URLs
GH_MIRROR = "https://ghfast.top/https://github.com"
URLS = {
    "curl": f"https://curl.se/download/curl-{CURL_VERSION}.tar.xz",
    "boringssl": f"{GH_MIRROR}/google/boringssl/archive/{BORINGSSL_COMMIT}.zip",
    "brotli": f"{GH_MIRROR}/google/brotli/archive/refs/tags/v{BROTLI_VERSION}.tar.gz",
    "nghttp2": f"{GH_MIRROR}/nghttp2/nghttp2/releases/download/v{NGHTTP2_VERSION}/nghttp2-{NGHTTP2_VERSION}.tar.bz2",
    "ngtcp2": f"{GH_MIRROR}/ngtcp2/ngtcp2/archive/refs/tags/v{NGTCP2_VERSION}.tar.gz",
    "nghttp3": f"{GH_MIRROR}/ngtcp2/nghttp3/archive/refs/tags/v{NGHTTP3_VERSION}.tar.gz",
    "zlib": f"{GH_MIRROR}/madler/zlib/archive/refs/tags/v{ZLIB_VERSION}.tar.gz",
    "zstd": f"{GH_MIRROR}/facebook/zstd/releases/download/v{ZSTD_VERSION}/zstd-{ZSTD_VERSION}.tar.gz",
    "libssh2": f"{GH_MIRROR}/libssh2/libssh2/releases/download/libssh2-{LIBSSH2_VERSION}/libssh2-{LIBSSH2_VERSION}.tar.gz",
}

# Architecture-specific directory names
ARCH_DIRS = {
    "x64": {"build": "build", "install": "install", "output": "output"},
    "x86": {"build": "build_x86", "install": "install_x86", "output": "output_x86"},
}

# Build order matters!
BUILD_ORDER = ["zlib", "zstd", "brotli", "nghttp2", "nghttp3", "boringssl", "ngtcp2", "libssh2", "curl"]

# System DLLs whitelist
SYSTEM_DLLS = {
    "kernel32.dll", "ntdll.dll", "ws2_32.dll", "advapi32.dll", "crypt32.dll",
    "secur32.dll", "user32.dll", "gdi32.dll", "shell32.dll", "shlwapi.dll",
    "ole32.dll", "oleaut32.dll", "uuid.dll", "msvcrt.dll", "bcrypt.dll",
    "ncrypt.dll", "imm32.dll", "comdlg32.dll", "version.dll", "winmm.dll",
    "wsock32.dll", "wldap32.dll", "normaliz.dll", "iphlpapi.dll",
}

# ============================================================
# Utility functions
# ============================================================
def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    prefix = {"INFO": "", "WARN": "[WARN] ", "ERROR": "[ERROR] ", "OK": "[OK] "}.get(level, "")
    print(f"[{ts}] {prefix}{msg}", flush=True)

def run(cmd, cwd=None, check=True, env=None, shell=False):
    """Run a command, return CompletedProcess."""
    if isinstance(cmd, str):
        cmd_str = cmd
    else:
        cmd_str = " ".join(str(c) for c in cmd)
    log(f"  > {cmd_str}")
    result = subprocess.run(
        cmd, cwd=cwd, check=False, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, shell=shell
    )
    if check and result.returncode != 0:
        log(f"Command failed (rc={result.returncode}): {cmd_str}", "ERROR")
        if result.stdout:
            for line in result.stdout.splitlines()[-20:]:
                log(f"  stdout: {line}", "ERROR")
        if result.stderr:
            for line in result.stderr.splitlines()[-20:]:
                log(f"  stderr: {line}", "ERROR")
        raise RuntimeError(f"Command failed: {cmd_str}")
    return result

# Custom curl.bat path (auto-detects system proxy)
CURL_BAT = Path(r"C:\Users\hmz\bin\curl.bat")

def download(url, dest, desc=""):
    """Download a file. Uses curl.bat (with proxy auto-detect) first, then urllib fallback."""
    if dest.exists():
        log(f"  Already downloaded: {dest.name}")
        return
    log(f"  Downloading {desc or dest.name}...")

    # Try curl.bat first (auto-detects system proxy, more reliable for SSL)
    curl_cmd = str(CURL_BAT) if CURL_BAT.exists() else "curl"
    for attempt in range(3):
        try:
            result = subprocess.run(
                [curl_cmd, "-L", "--retry", "5", "--retry-delay", "10",
                 "--connect-timeout", "30", "--max-time", "600",
                 "-o", str(dest), url],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and dest.exists() and dest.stat().st_size > 1000:
                return
            else:
                log(f"  curl attempt {attempt+1} failed (rc={result.returncode})", "WARN")
        except FileNotFoundError:
            log(f"  {curl_cmd} not found, trying urllib...", "WARN")
            break
        except Exception as e:
            log(f"  curl attempt {attempt+1} failed: {e}", "WARN")
        if dest.exists():
            dest.unlink()
        time.sleep(3)

    # Fallback: urllib
    import ssl
    for attempt in range(3):
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(url, context=ctx) as resp:
                with open(dest, 'wb') as f:
                    shutil.copyfileobj(resp, f)
            if dest.exists() and dest.stat().st_size > 1000:
                return
        except Exception as e:
            log(f"  urllib attempt {attempt+1} failed: {e}", "WARN")
            if dest.exists():
                dest.unlink()
            time.sleep(3)

    raise RuntimeError(f"Failed to download {url}")

def rmtree_safe(path):
    """Safely remove a directory tree. Handles Windows read-only git objects."""
    path = Path(path) if not isinstance(path, Path) else path
    if not path.exists():
        return
    log(f"  Removing {path}...")
    import stat
    def _remove_readonly(func, path_, excinfo):
        """Clear read-only flag and retry (needed for git objects)."""
        os.chmod(path_, stat.S_IWRITE)
        func(path_)
    try:
        shutil.rmtree(str(path), onerror=_remove_readonly)
    except Exception:
        shutil.rmtree(str(path), ignore_errors=True)

def apply_patch(src_dir, patch_file, git_exe="git"):
    """Apply a git patch to a source directory. Returns True on success."""
    if not patch_file.exists():
        log(f"  Patch not found: {patch_file}", "WARN")
        return False

    if patch_file.stat().st_size == 0:
        log(f"  Empty patch (no modifications needed): {patch_file.name}")
        return True

    # Initialize git repo if needed (or reinit if broken)
    git_dir = src_dir / ".git"
    need_init = not git_dir.exists()
    if not need_init:
        # Check if git repo is functional
        result = subprocess.run(
            [git_exe, "status", "--short"],
            cwd=str(src_dir), capture_output=True, text=True
        )
        if result.returncode != 0:
            need_init = True
            log(f"  Git repo broken, reinitializing...")

    if need_init:
        if git_dir.exists():
            rmtree_safe(git_dir)
        run([git_exe, "init"], cwd=src_dir)
        # Set local identity for commit (required even with --allow-empty)
        run([git_exe, "config", "user.email", "build@local"], cwd=src_dir, check=False)
        run([git_exe, "config", "user.name", "build"], cwd=src_dir, check=False)
        run([git_exe, "add", "-A"], cwd=src_dir)
        run([git_exe, "commit", "-q", "-m", "baseline", "--allow-empty"], cwd=src_dir)

    # Check and apply (use --ignore-whitespace for trailing whitespace tolerance)
    result = run([git_exe, "apply", "--ignore-whitespace", "--check", str(patch_file)], cwd=src_dir, check=False)
    if result.returncode == 0:
        run([git_exe, "apply", "--ignore-whitespace", str(patch_file)], cwd=src_dir)
        log(f"  Applied patch: {patch_file.name}", "OK")
        return True
    else:
        # Try --3way
        result = run([git_exe, "apply", "--ignore-whitespace", "--3way", str(patch_file)], cwd=src_dir, check=False)
        if result.returncode == 0:
            log(f"  Applied patch (3way): {patch_file.name}", "OK")
            return True
        else:
            log(f"  Failed to apply patch: {patch_file.name}", "ERROR")
            return False

def copy_new_files(src_dir, patches_dir, file_list):
    """Copy new files from patches_dir to src_dir/lib/."""
    lib_dir = src_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    for f in file_list:
        src = patches_dir / f
        dst = lib_dir / f
        if src.exists():
            shutil.copy2(src, dst)
            log(f"  Copied: {f}")
        else:
            log(f"  File not found: {f}", "WARN")

# ============================================================
# Find Visual Studio
# ============================================================
def find_vs(vs_version="2022"):
    """Find VS install path and vcvarsall.bat."""
    vs_major = {"2022": "17", "2019": "16"}.get(vs_version, "17")
    try:
        result = run(
            ["powershell", "-NoProfile", "-Command",
             f"& '{{}}' {vs_major}" .format(str(WIN_BUILD_DIR / "find_vs.bat"))],
            check=False
        )
        vs_path = result.stdout.strip()
        if vs_path and Path(vs_path).exists():
            vcvarsall = Path(vs_path) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
            if vcvarsall.exists():
                return vs_path, vcvarsall
    except Exception:
        pass

    # Fallback: try known paths
    for base in [r"C:\Program Files\Microsoft Visual Studio",
                 r"D:\Program Files\Microsoft Visual Studio"]:
        for edition in ["Community", "Professional", "Enterprise"]:
            path = Path(base) / f"{vs_version}" / edition
            vcvarsall = path / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat"
            if vcvarsall.exists():
                return str(path), vcvarsall

    raise RuntimeError(f"Visual Studio {vs_version} not found")

# ============================================================
# Build environment setup
# ============================================================
def setup_msvc_env(arch, vcvarsall):
    """Setup MSVC environment by calling vcvarsall.bat and capturing env vars."""
    # Use a temp script to dump environment after vcvarsall
    tmp_script = ROOT_DIR / "_msvc_env.bat"
    tmp_output = ROOT_DIR / "_msvc_env.txt"
    tmp_script.write_text(
        f'@echo off\n'
        f'call "{vcvarsall}" {arch}\n'
        f'set > "{tmp_output}"\n'
    )
    run(["cmd", "/c", str(tmp_script)], check=True)
    tmp_script.unlink(missing_ok=True)

    # Parse env vars
    env = os.environ.copy()
    if tmp_output.exists():
        for line in tmp_output.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                env[key] = val
        tmp_output.unlink(missing_ok=True)

    # Verify cl.exe is available
    cl_check = run(["cl"], env=env, check=False, shell=True)
    if cl_check.returncode != 0 and "Microsoft" not in cl_check.stderr:
        # Try where cl
        cl_where = run(["where", "cl"], env=env, check=False)
        if cl_where.returncode != 0:
            log("  cl.exe not found in PATH after vcvarsall", "WARN")
        else:
            log("  cl.exe found via where", "OK")

    return env

# ============================================================
# Download all source archives
# ============================================================
def download_all_sources(deps_dir):
    """Download all source archives to deps/."""
    deps_dir.mkdir(parents=True, exist_ok=True)
    # Explicit filename mappings to avoid collisions (GitHub archive URLs have generic names)
    FNAME_MAP = {
        "ngtcp2": f"ngtcp2-{NGTCP2_VERSION}.tar.gz",
        "nghttp3": f"nghttp3-{NGHTTP3_VERSION}.tar.gz",
        "brotli": f"brotli-{BROTLI_VERSION}.tar.gz",
        "zlib": f"zlib-{ZLIB_VERSION}.tar.gz",
        "libssh2": f"libssh2-{LIBSSH2_VERSION}.tar.gz",
    }
    archives = {}
    for name, url in URLS.items():
        fname = FNAME_MAP.get(name, url.split("/")[-1])
        dest = deps_dir / fname
        download(url, dest, desc=name)
        archives[name] = dest
    return archives

# ============================================================
# Extract source archives
# ============================================================
def dir_is_empty(path):
    """Check if a directory is empty or doesn't contain real source files.
    Ignores .git directories (leftover from previous patch attempts)."""
    if not path.exists():
        return True
    # Count non-.git entries
    entries = [e for e in os.listdir(str(path)) if e != '.git']
    return len(entries) == 0

def extract_sources(deps_dir, archives):
    """Extract all source archives to deps/."""
    if not archives:
        log("  No archives to extract (already downloaded)")
        return
    # Curl
    curl_src = deps_dir / CURL_VERSION_DIR
    if dir_is_empty(curl_src):
        log("  Extracting curl...")
        if curl_src.exists():
            rmtree_safe(curl_src)
        with tarfile.open(str(archives["curl"]), "r:xz") as t:
            t.extractall(str(deps_dir), filter='data')

    # BoringSSL (zip, renames from boringssl-<commit>)
    boringssl_src = deps_dir / "boringssl"
    tmp_extract = deps_dir / f"boringssl-{BORINGSSL_COMMIT}"
    if not (boringssl_src / "CMakeLists.txt").exists():
        log("  Extracting boringssl...")
        # Always clean start - remove any stale directories
        rmtree_safe(boringssl_src)
        rmtree_safe(tmp_extract)
        # Extract with retry to handle Windows file locking (antivirus, etc.)
        max_retries = 5
        for attempt in range(max_retries):
            try:
                with zipfile.ZipFile(str(archives["boringssl"]), "r") as z:
                    z.extractall(str(deps_dir))
                break
            except Exception as e:
                log(f"  Extract attempt {attempt+1} failed: {e}", "WARN")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    # Clean partial extraction
                    rmtree_safe(tmp_extract)
                else:
                    raise
        # Clear read-only attributes on all extracted files (Windows fix)
        import stat as _stat
        for root, dirs, files in os.walk(str(tmp_extract)):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    os.chmod(fpath, _stat.S_IWRITE | _stat.S_IREAD)
                except Exception:
                    pass
        if tmp_extract.exists():
            # Use os.rename (same drive) instead of shutil.move to avoid
            # file copy issues with read-only files
            try:
                os.rename(str(tmp_extract), str(boringssl_src))
            except OSError:
                shutil.move(str(tmp_extract), str(boringssl_src))
        # Final check
        if not (boringssl_src / "CMakeLists.txt").exists():
            log("  BoringSSL CMakeLists.txt still missing after extraction!", "FATAL")
            sys.exit(1)

    # Brotli (tar.gz, renames from brotli-<version>)
    brotli_src = deps_dir / f"brotli-{BROTLI_VERSION}"
    if dir_is_empty(brotli_src):
        log("  Extracting brotli...")
        if brotli_src.exists():
            rmtree_safe(brotli_src)
        with tarfile.open(str(archives["brotli"]), "r:gz") as t:
            t.extractall(str(deps_dir), filter='data')

    # nghttp2
    nghttp2_src = deps_dir / f"nghttp2-{NGHTTP2_VERSION}"
    if dir_is_empty(nghttp2_src):
        log("  Extracting nghttp2...")
        if nghttp2_src.exists():
            rmtree_safe(nghttp2_src)
        with tarfile.open(str(archives["nghttp2"]), "r:bz2") as t:
            t.extractall(str(deps_dir), filter='data')

    # ngtcp2 (tar.gz from GitHub archive)
    ngtcp2_src = deps_dir / f"ngtcp2-{NGTCP2_VERSION}"
    if dir_is_empty(ngtcp2_src):
        log("  Extracting ngtcp2...")
        if ngtcp2_src.exists():
            rmtree_safe(ngtcp2_src)
        with tarfile.open(str(archives["ngtcp2"]), "r:gz") as t:
            t.extractall(str(deps_dir), filter='data')

    # nghttp3 (tar.gz from GitHub archive)
    nghttp3_src = deps_dir / f"nghttp3-{NGHTTP3_VERSION}"
    if dir_is_empty(nghttp3_src):
        log("  Extracting nghttp3...")
        if nghttp3_src.exists():
            rmtree_safe(nghttp3_src)
        with tarfile.open(str(archives["nghttp3"]), "r:gz") as t:
            t.extractall(str(deps_dir), filter='data')

    # zlib (tar.gz, renames from zlib-<version>)
    zlib_src = deps_dir / f"zlib-{ZLIB_VERSION}"
    if dir_is_empty(zlib_src):
        log("  Extracting zlib...")
        if zlib_src.exists():
            rmtree_safe(zlib_src)
        with tarfile.open(str(archives["zlib"]), "r:gz") as t:
            t.extractall(str(deps_dir), filter='data')

    # zstd (tar.gz)
    zstd_src = deps_dir / f"zstd-{ZSTD_VERSION}"
    if dir_is_empty(zstd_src):
        log("  Extracting zstd...")
        if zstd_src.exists():
            rmtree_safe(zstd_src)
        with tarfile.open(str(archives["zstd"]), "r:gz") as t:
            t.extractall(str(deps_dir), filter='data')

    # libssh2 (tar.gz)
    libssh2_src = deps_dir / f"libssh2-{LIBSSH2_VERSION}"
    if dir_is_empty(libssh2_src):
        log("  Extracting libssh2...")
        if libssh2_src.exists():
            rmtree_safe(libssh2_src)
        with tarfile.open(str(archives["libssh2"]), "r:gz") as t:
            t.extractall(str(deps_dir), filter='data')

    # Download missing git submodules (GitHub archives don't include them)
    # nghttp3 requires lib/sfparse
    sfparse_dir = nghttp3_src / "lib" / "sfparse"
    sfparse_marker = nghttp3_src / "lib" / ".sfparse_downloaded"
    if nghttp3_src.exists() and not sfparse_marker.exists():
        log("  Downloading nghttp3 submodule: sfparse...")
        sfparse_dir.mkdir(parents=True, exist_ok=True)
        sfparse_archive = deps_dir / "sfparse.tar.gz"
        if sfparse_archive.exists():
            sfparse_archive.unlink()
        download(
            f"{GH_MIRROR}/ngtcp2/sfparse/archive/refs/heads/main.tar.gz",
            sfparse_archive,
            desc="sfparse"
        )
        with tarfile.open(str(sfparse_archive), "r:gz") as t:
            t.extractall(str(sfparse_dir.parent), filter='data')
        # GitHub archive extracts to sfparse-main, move contents into sfparse/
        sfparse_extracted = sfparse_dir.parent / "sfparse-main"
        if sfparse_extracted.exists():
            for item in sfparse_extracted.iterdir():
                dest = sfparse_dir / item.name
                if not dest.exists():
                    shutil.move(str(item), str(dest))
            rmtree_safe(sfparse_extracted)
        sfparse_marker.touch()

# ============================================================
# Apply all patches
# ============================================================
def apply_all_patches(deps_dir, git_exe):
    """Apply patches from patches/ to all deps. Exits on failure."""
    # BoringSSL patch
    if not apply_patch(deps_dir / "boringssl", PATCHES_DIR / "boringssl.patch", git_exe):
        log("BoringSSL patch failed, aborting build", "FATAL")
        sys.exit(1)

    # Curl patch (includes all lexiforest + custom modifications)
    curl_src = deps_dir / CURL_VERSION_DIR
    if not apply_patch(curl_src, PATCHES_DIR / "curl.patch", git_exe):
        log("Curl patch failed, aborting build", "FATAL")
        sys.exit(1)
    # Curl patch: disable proxy environment variable reading
    # (fixes CONNECT tunnel bug when libcurl is linked into a DLL with
    # its own CRT that does not share _environ with the host process)
    if not apply_patch(curl_src, PATCHES_DIR / "curl-disable-proxy-env.patch", git_exe):
        log("curl-disable-proxy-env patch failed, aborting build", "FATAL")
        sys.exit(1)
    # Curl patch: suppress CONNECT tunnel response headers
    # (fixes bug where CONNECT response headers like "HTTP/1.1 200 Connection
    # established" leak into CURLOPT_HEADERFUNCTION callback, polluting
    # CURLINFO_RESPONSE_CODE and real HTTP response headers)
    if not apply_patch(curl_src, PATCHES_DIR / "curl-suppress-connect-headers.patch", git_exe):
        log("curl-suppress-connect-headers patch failed, aborting build", "FATAL")
        sys.exit(1)
    # Curl patch: fix HTTP/2 header value case (remove incorrect lowercasing)
    # Without this, :method becomes "get" instead of "GET", causing 400 from strict servers (AWS ALB)
    if not apply_patch(curl_src, PATCHES_DIR / "fix-h2-header-value-case.patch", git_exe):
        log("fix-h2-header-value-case patch failed, aborting build", "FATAL")
        sys.exit(1)

    # Curl patch: add __stdcall to Curl_share_lock/unlock (replaces fix_merge_forward_decl.py)
    if not apply_patch(curl_src, PATCHES_DIR / "curl-share-stdcall.patch", git_exe):
        log("curl-share-stdcall patch failed, aborting build", "FATAL")
        sys.exit(1)

    # Copy new files for curl
    copy_new_files(curl_src, PATCHES_DIR, [
        "cJSON.c", "cJSON.h",
        "impersonate.c", "impersonate.h",
        "impersonate_register.c", "impersonate_register.h",
        "libcurl-impersonate.def",
    ])

    # nghttp3 patch
    if not apply_patch(deps_dir / f"nghttp3-{NGHTTP3_VERSION}", PATCHES_DIR / "nghttp3.patch", git_exe):
        log("nghttp3 patch failed, aborting build", "FATAL")
        sys.exit(1)

    # ngtcp2 patch
    if not apply_patch(deps_dir / f"ngtcp2-{NGTCP2_VERSION}", PATCHES_DIR / "ngtcp2.patch", git_exe):
        log("ngtcp2 patch failed, aborting build", "FATAL")
        sys.exit(1)

    # Brotli patch
    if not apply_patch(deps_dir / f"brotli-{BROTLI_VERSION}", PATCHES_DIR / "brotli.patch", git_exe):
        log("Brotli patch failed, aborting build", "FATAL")
        sys.exit(1)

    # zlib patch
    if not apply_patch(deps_dir / f"zlib-{ZLIB_VERSION}", PATCHES_DIR / "zlib.patch", git_exe):
        log("zlib patch failed, aborting build", "FATAL")
        sys.exit(1)

    # nghttp2 and zstd have no patches (empty files)

# ============================================================
# Build functions for each dependency
# ============================================================
def cmake_configure(src_dir, build_dir, install_dir, env, extra_args=None):
    """Generic CMake configure."""
    build_dir.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        env.get("CMAKE_EXE", "cmake"), "-G", "Ninja",
        f"-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_C_COMPILER=cl",
        "-DCMAKE_CXX_COMPILER=cl",
        "-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded",
        "-DCMAKE_C_FLAGS_RELEASE=/MT /O2 /DNDEBUG",
        "-DCMAKE_CXX_FLAGS_RELEASE=/MT /O2 /DNDEBUG",
        f"-DCMAKE_MAKE_PROGRAM={env.get('NINJA_EXE', 'ninja')}",
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(["-S", str(src_dir), "-B", str(build_dir)])
    run(cmd, env=env)

def cmake_build(build_dir, env):
    """Generic CMake build."""
    run([env.get("CMAKE_EXE", "cmake"), "--build", str(build_dir), "--config", "Release"], env=env)

def cmake_install(build_dir, env):
    """Generic CMake install."""
    run([env.get("CMAKE_EXE", "cmake"), "--install", str(build_dir), "--config", "Release"], env=env)

def build_zlib(src_dir, build_dir, install_dir, env):
    log("Building zlib...")
    cmake_configure(src_dir, build_dir, install_dir, env, [
        "-DCMAKE_INSTALL_LIBDIR=lib",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("zlib done.", "OK")

def build_zstd(src_dir, build_dir, install_dir, env):
    log("Building zstd...")
    cmake_configure(
        src_dir / "build" / "cmake", build_dir, install_dir, env, [
        "-DZSTD_BUILD_STATIC=ON",
        "-DZSTD_BUILD_SHARED=OFF",
        "-DZSTD_BUILD_PROGRAMS=OFF",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("zstd done.", "OK")

def build_brotli(src_dir, build_dir, install_dir, env):
    log("Building brotli...")
    cmake_configure(src_dir, build_dir, install_dir, env, [
        "-DBROTLI_BUNDLED_MODE=OFF",
        # brotli uses standard BUILD_SHARED_LIBS (not BROTLI_BUILD_SHARED/STATIC)
        "-DBUILD_SHARED_LIBS=OFF",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("brotli done.", "OK")

def build_nghttp2(src_dir, build_dir, install_dir, env):
    log("Building nghttp2...")
    cmake_configure(src_dir, build_dir, install_dir, env, [
        # nghttp2 uses BUILD_SHARED_LIBS/BUILD_STATIC_LIBS (standard CMake),
        # NOT ENABLE_SHARED_LIB/ENABLE_STATIC_LIB (which nghttp3/ngtcp2 use)
        "-DBUILD_SHARED_LIBS=OFF",
        "-DBUILD_STATIC_LIBS=ON",
        "-DENABLE_APP=OFF",
        "-DENABLE_HPACK_TOOLS=OFF",
        "-DENABLE_EXAMPLES=OFF",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("nghttp2 done.", "OK")

def build_nghttp3(src_src, build_dir, install_dir, env):
    log("Building nghttp3...")
    cmake_configure(src_src, build_dir, install_dir, env, [
        "-DENABLE_SHARED_LIB=OFF",
        "-DENABLE_STATIC_LIB=ON",
        "-DENABLE_LIB_ONLY=ON",
        "-DBUILD_TESTING=OFF",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("nghttp3 done.", "OK")

def build_boringssl(src_dir, build_dir, install_dir, env):
    log("Building BoringSSL...")
    nasm = env.get("NASM_EXE", "nasm")
    cmake_configure(src_dir, build_dir, install_dir, env, [
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        "-DCMAKE_C_FLAGS=/MT /O2 /DNDEBUG /D_CRT_NONSTDC_NO_DEPRECATE",
        "-DCMAKE_CXX_FLAGS=/MT /O2 /DNDEBUG /D_CRT_NONSTDC_NO_DEPRECATE",
        f"-DCMAKE_ASM_NASM_COMPILER={nasm}",
        "-DBUILD_TESTING=OFF",
        "-DBENCHMARK_ENABLE_TESTING=OFF",
    ])

    # Fix MSVC compilation errors
    log("  Applying MSVC compatibility fixes...")
    fix_env = env.copy()
    fix_env["BORINGSSL_SRC_DIR"] = str(src_dir)
    run([sys.executable, str(WIN_BUILD_DIR / "fix_boringssl_msvc.py")], env=fix_env)

    cmake_build(build_dir, env)

    # Fix directory structure for curl compatibility
    lib_dir = build_dir / "lib"
    lib_dir.mkdir(exist_ok=True)
    # Copy SSL and Crypto libraries
    ssl_copied = False
    crypto_copied = False
    for src_pattern, dst_name in [
        ("ssl/ssl.lib", "libssl.lib"),
        ("ssl/ssl_static.lib", "libssl.lib"),
        ("crypto/crypto.lib", "libcrypto.lib"),
        ("crypto/crypto_static.lib", "libcrypto.lib"),
    ]:
        src = build_dir / src_pattern
        if src.exists():
            shutil.copy2(src, lib_dir / dst_name)
            if dst_name.startswith("libssl"):
                ssl_copied = True
            else:
                crypto_copied = True
            if ssl_copied and crypto_copied:
                break

    # Copy include directory
    include_dir = build_dir / "include"
    if not include_dir.exists():
        shutil.copytree(src_dir / "include", include_dir)

    # Install
    install_lib = install_dir / "lib"
    install_inc = install_dir / "include"
    install_lib.mkdir(parents=True, exist_ok=True)
    install_inc.mkdir(parents=True, exist_ok=True)
    for f in lib_dir.glob("*.lib"):
        shutil.copy2(f, install_lib / f.name)
    if not (install_inc / "openssl").exists():
        shutil.copytree(build_dir / "include" / "openssl", install_inc / "openssl",
                       dirs_exist_ok=True)

    # Create opensslconf.h stub
    conf_h = install_inc / "openssl" / "opensslconf.h"
    if not conf_h.exists():
        conf_h.write_text("#ifndef OPENSSL_OPENSSLCONF_H\n#define OPENSSL_OPENSSLCONF_H\n#endif\n")

    # Create ocsp.h stub
    ocsp_h = install_inc / "openssl" / "ocsp.h"
    ocsp_stub = WIN_BUILD_DIR / "patches" / "boringssl-ocsp-stub.h"
    if not ocsp_h.exists():
        if ocsp_stub.exists():
            shutil.copy2(ocsp_stub, ocsp_h)
        else:
            # Create minimal stub
            ocsp_h.write_text("/* ocsp.h stub - BoringSSL does not provide OCSP API */\n")

    # Fix installed opensslv.h - Add OPENSSL_VERSION_NUMBER for CMake FindOpenSSL
    opensslv_h = install_inc / "openssl" / "opensslv.h"
    if opensslv_h.exists():
        content = opensslv_h.read_text(encoding="utf-8", errors="replace")
        if "OPENSSL_VERSION_NUMBER" not in content:
            version_macros = """/* Added for CMake FindOpenSSL compatibility */
#ifndef OPENSSL_VERSION_NUMBER
#define OPENSSL_VERSION_NUMBER 0x30300000L
#endif
#ifndef OPENSSL_VERSION_TEXT
#define OPENSSL_VERSION_TEXT "BoringSSL"
#endif
#ifndef OPENSSL_VERSION
#define OPENSSL_VERSION OPENSSL_VERSION_NUMBER
#endif

"""
            if "#include" in content:
                idx = content.find("#include")
                content = content[:idx] + version_macros + content[idx:]
            else:
                content = version_macros + content
            opensslv_h.write_text(content, encoding="utf-8")
            log("  Added OPENSSL_VERSION_NUMBER to opensslv.h")

    log("BoringSSL done.", "OK")

def build_ngtcp2(src_dir, build_dir, install_dir, boringssl_install, env):
    log("Building ngtcp2...")
    # Fix CMakeLists.txt - skip BoringSSL symbol checks for MSVC
    # The check_symbol_exists try_compile fails because BORINGSSL_LIBRARIES
    # contains backslash Windows paths that CMake can't parse in try_compile.
    # Replace the entire first if(ENABLE_BORINGSSL) block with a simple set.
    cmake_file = src_dir / "CMakeLists.txt"
    if cmake_file.exists():
        content = cmake_file.read_text(encoding="utf-8", errors="replace")
        # Only patch if the check_symbol_exists is still there
        if 'check_symbol_exists("OPENSSL_IS_BORINGSSL"' in content:
            old_block_start = "# BoringSSL (required for libngtcp2_crypto_boringssl)\nif(ENABLE_BORINGSSL)"
            old_block_end = "cmake_pop_check_state()\nendif()"
            idx_start = content.find(old_block_start)
            idx_end = content.find(old_block_end, idx_start)
            if idx_start >= 0 and idx_end >= 0:
                old_block = content[idx_start:idx_end + len(old_block_end)]
                new_block = """# BoringSSL (required for libngtcp2_crypto_boringssl)
if(ENABLE_BORINGSSL)
  # Skip symbol checks for MSVC - backslash paths in BORINGSSL_LIBRARIES
  # cause CMake try_compile "Invalid character escape" errors.
  # We know it's BoringSSL because we built it ourselves.
  set(HAVE_BORINGSSL TRUE)
  set(HAVE_SSL_SET_QUIC_EARLY_DATA_CONTEXT TRUE)
endif()"""
                content = content.replace(old_block, new_block, 1)
                cmake_file.write_text(content, encoding="utf-8")
                log("  Fixed ngtcp2 CMakeLists.txt for BoringSSL")
    cmake_configure(src_dir, build_dir, install_dir, env, [
        "-DENABLE_SHARED_LIB=OFF",
        "-DENABLE_STATIC_LIB=ON",
        "-DENABLE_LIB_ONLY=ON",
        "-DBUILD_TESTING=OFF",
        "-DENABLE_OPENSSL=OFF",
        "-DENABLE_BORINGSSL=ON",
        f"-DCMAKE_PREFIX_PATH={boringssl_install}",
        f"-DBORINGSSL_INCLUDE_DIR={boringssl_install}/include",
        f"-DBORINGSSL_LIBRARIES={boringssl_install}/lib/libssl.lib;{boringssl_install}/lib/libcrypto.lib",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("ngtcp2 done.", "OK")

def build_libssh2(src_dir, build_dir, install_dir, boringssl_install, zlib_install, env):
    log("Building libssh2...")
    cmake_configure(src_dir, build_dir, install_dir, env, [
        "-DBUILD_SHARED_LIBS=OFF",
        "-DBUILD_STATIC_LIBS=ON",
        "-DBUILD_TESTING=OFF",
        "-DBUILD_EXAMPLES=OFF",
        "-DCRYPTO_BACKEND=OpenSSL",
        f"-DOPENSSL_ROOT_DIR={boringssl_install}",
        f"-DOPENSSL_INCLUDE_DIR={boringssl_install}/include",
        f"-DOPENSSL_LIBRARIES={boringssl_install}/lib/libssl.lib;{boringssl_install}/lib/libcrypto.lib",
        f"-DZLIB_INCLUDE_DIR={zlib_install}/include",
        f"-DZLIB_LIBRARY={zlib_install}/lib/zlibstatic.lib",
        "-DENABLE_ZLIB_COMPRESSION=ON",
        "-DLIBSSH2_NO_HTONLL=OFF",
    ])
    cmake_build(build_dir, env)
    cmake_install(build_dir, env)
    log("libssh2 done.", "OK")

def filter_def_for_arch(def_file, deps_info, env, arch):
    """Filter .def file to remove symbols not present in the architecture's libraries.

    On x86, BoringSSL doesn't include x64-only assembly routines (nistz256,
    rdrand, AVX-512, etc.). The .def file was generated from x64 exports, so
    we need to remove x64-only symbols when building for x86.

    We only filter symbols in non-curl sections (boringssl, zlib, etc.) because
    curl symbols come from the curl source code itself, not from dependency libs.
    """
    if arch == "x64":
        return  # x64 build uses the .def file as-is

    if not def_file.exists():
        log("  .def file not found, skipping filter", "WARN")
        return

    # Map section names in .def comments to dependency install dirs
    SECTION_TO_DEP = {
        "boringssl": "boringssl",
        "zlib": "zlib",
        "brotli": "brotli",
        "nghttp2": "nghttp2",
        "nghttp3": "nghttp3",
        "ngtcp2": "ngtcp2",
        "zstd": "zstd",
        "libssh2": "libssh2",
    }

    # Find dumpbin
    dumpbin_path = shutil.which("dumpbin", path=env.get("PATH", ""))
    if not dumpbin_path:
        import glob as _glob
        for base in [
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC",
        ]:
            if Path(base).exists():
                for ver in sorted(Path(base).iterdir(), reverse=True):
                    for host_arch in ["Hostx64", "Hostx86"]:
                        candidate = ver / "bin" / host_arch / "x86" / "dumpbin.exe"
                        if candidate.exists():
                            dumpbin_path = str(candidate)
                            break
                    if dumpbin_path:
                        break
            if dumpbin_path:
                break

    # Extract available symbols per dependency using dumpbin
    dep_symbols = {}  # dep_name -> set of available symbols
    for dep_name in SECTION_TO_DEP.values():
        dep_symbols[dep_name] = set()
        if dep_name not in deps_info or not dumpbin_path:
            continue
        install = deps_info[dep_name]["install"]
        lib_dir = install / "lib"
        if not lib_dir.exists():
            continue
        for lib_file in lib_dir.glob("*.lib"):
            result = subprocess.run(
                [dumpbin_path, "/symbols", str(lib_file)],
                capture_output=True, text=True, check=False
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if "External" in line:
                    parts = line.split()
                    if parts:
                        sym = parts[-1]
                        # Skip C++ decorated names (start with ?)
                        if sym.startswith("?"):
                            continue
                        # Strip MSVC C name decoration: leading _ and trailing @N (stdcall)
                        if sym.startswith("_"):
                            sym = sym[1:]
                        at_idx = sym.rfind("@")
                        if at_idx > 0 and sym[at_idx+1:].isdigit():
                            sym = sym[:at_idx]
                        dep_symbols[dep_name].add(sym)

    if not dumpbin_path:
        log("  dumpbin not found, using hardcoded x64-only BoringSSL symbol list", "WARN")
        dep_symbols["boringssl"] = {
            # Known x86 BoringSSL CRYPTO_is_ symbols
            "CRYPTO_is_AESNI_capable", "CRYPTO_is_AVX_capable",
            "CRYPTO_is_FXSR_capable", "CRYPTO_is_PCLMUL_capable",
            "CRYPTO_is_SSSE3_capable", "CRYPTO_is_confidential_build",
            "CRYPTO_is_intel_cpu",
        }

    # Parse .def file by section and filter
    with open(def_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()
    filtered_lines = []
    current_section = None  # "curl", "boringssl", etc.
    removed = 0

    for line in lines:
        stripped = line.strip()

        # Detect section headers like "; === boringssl ==="
        if stripped.startswith("; ==="):
            for section_name in SECTION_TO_DEP:
                if section_name in stripped.lower():
                    current_section = section_name
                    break
            else:
                if "curl" in stripped.lower():
                    current_section = "curl"
                else:
                    current_section = None
            filtered_lines.append(line)
            continue

        # Skip non-symbol lines (LIBRARY, EXPORTS, comments, blank)
        if not stripped or stripped.startswith(";") or stripped.startswith("LIBRARY") or stripped.startswith("EXPORTS"):
            filtered_lines.append(line)
            continue

        # Extract symbol name (before any comment)
        sym = stripped.split(";")[0].strip()
        if not sym:
            filtered_lines.append(line)
            continue

        # Only filter symbols in dependency sections (not curl section)
        if current_section and current_section in SECTION_TO_DEP:
            dep_name = SECTION_TO_DEP[current_section]
            if sym not in dep_symbols.get(dep_name, set()):
                removed += 1
                continue  # Skip this symbol

        filtered_lines.append(line)

    if removed > 0:
        with open(def_file, "w", encoding="utf-8") as f:
            f.write("\n".join(filtered_lines) + "\n")
        log(f"  Filtered {removed} x64-only symbols from .def file for {arch}")
    else:
        log("  No x64-only symbols found in .def file")


def build_curl(src_dir, build_dir, install_dir, output_dir, deps_info, env, arch="x64"):
    """Build curl-impersonate DLL."""
    log("Building curl-impersonate DLL...")

    # Fix VLA for MSVC (catch patterns not in patch)
    fix_vla_script = WIN_BUILD_DIR / "fix_vla.py"
    if fix_vla_script.exists():
        run([sys.executable, str(fix_vla_script)], cwd=str(src_dir), env=env, check=False)

    # fix_merge_forward_decl.py is no longer needed - all its modifications
    # (slist.h, static, merge call, curl_easy_reset, share_stdcall) are now
    # included in curl.patch and curl-share-stdcall.patch directly.

    # Fix BoringSSL detection in CMakeLists.txt
    cmakelists = src_dir / "lib" / "CMakeLists.txt"
    if cmakelists.exists():
        bor_def_script = WIN_BUILD_DIR / "patch_boringssl_def.py"
        if bor_def_script.exists():
            run([sys.executable, str(bor_def_script), str(cmakelists)],
                env=env, check=False)

    # Patch CMakeLists.txt for DLL export
    if cmakelists.exists():
        cmake_dll_script = WIN_BUILD_DIR / "patch_cmake_dll.py"
        if cmake_dll_script.exists():
            run([sys.executable, str(cmake_dll_script), str(cmakelists)],
                env=env, check=False)

    # Ensure output name is libcurl-impersonate
    lib_cmake = src_dir / "lib" / "CMakeLists.txt"
    if lib_cmake.exists():
        content = lib_cmake.read_text(encoding="utf-8", errors="replace")
        content = content.replace(
            "set(LIBCURL_OUTPUT_NAME libcurl CACHE",
            "set(LIBCURL_OUTPUT_NAME libcurl-impersonate CACHE"
        )
        lib_cmake.write_text(content, encoding="utf-8")

    src_cmake = src_dir / "src" / "CMakeLists.txt"
    if src_cmake.exists():
        content = src_cmake.read_text(encoding="utf-8", errors="replace")
        content = content.replace("set(EXE_NAME curl)", "set(EXE_NAME curl-impersonate)")
        src_cmake.write_text(content, encoding="utf-8")

    # Filter .def files to remove x64-only symbols when building for x86
    # CMakeLists.txt uses libcurl.def (not libcurl-impersonate.def)
    for def_name in ["libcurl.def", "libcurl-impersonate.def"]:
        def_path = src_dir / "lib" / def_name
        if def_path.exists():
            filter_def_for_arch(def_path, deps_info, env, arch)

    # Get all install dirs
    zlib_install = deps_info["zlib"]["install"]
    brotli_install = deps_info["brotli"]["install"]
    nghttp2_install = deps_info["nghttp2"]["install"]
    ngtcp2_install = deps_info["ngtcp2"]["install"]
    nghttp3_install = deps_info["nghttp3"]["install"]
    boringssl_install = deps_info["boringssl"]["install"]
    zstd_install = deps_info["zstd"]["install"]
    libssh2_install = deps_info["libssh2"]["install"]

    cmake_args = [
        "-DBUILD_SHARED_LIBS=ON",
        "-DBUILD_STATIC_LIBS=OFF",
        "-DBUILD_CURL_EXE=OFF",
        "-DBUILD_TESTING=OFF",
        # Use static libs for dependencies (adds *_STATICLIB defines)
        "-DNGHTTP2_USE_STATIC_LIBS=ON",
        "-DNGHTTP3_USE_STATIC_LIBS=ON",
        "-DNGTCP2_USE_STATIC_LIBS=ON",
        "-DBROTLI_USE_STATIC_LIBS=ON",
        "-DZSTD_USE_STATIC_LIBS=ON",
        "-DLIBSSH2_USE_STATIC_LIBS=ON",
        # SSL/TLS
        "-DCURL_USE_OPENSSL=ON",
        "-DHAVE_BORINGSSL=ON",
        f"-DCMAKE_PREFIX_PATH={boringssl_install};{brotli_install};{zlib_install};{nghttp2_install};{nghttp3_install};{ngtcp2_install};{zstd_install};{libssh2_install}",
        f"-DOPENSSL_ROOT_DIR={boringssl_install}",
        f"-DZLIB_ROOT={zlib_install}",
        # Compression
        "-DCURL_BROTLI=ON",
        f"-DBROTLI_INCLUDE_DIR={brotli_install}/include",
        f"-DBROTLI_LIBRARY={brotli_install}/lib/brotlidec.lib",
        f"-DBROTLIDEC_LIBRARY={brotli_install}/lib/brotlidec.lib",
        f"-DBROTLIENC_LIBRARY={brotli_install}/lib/brotlienc.lib",
        f"-DBROTLI_ENCODER_LIBRARY={brotli_install}/lib/brotlienc.lib",
        f"-DBROTLI_COMMON_LIBRARY={brotli_install}/lib/brotlicommon.lib",
        f"-DBROTLICOMMON_LIBRARY={brotli_install}/lib/brotlicommon.lib",
        "-DCURL_ZSTD=ON",
        f"-DZSTD_INCLUDE_DIR={zstd_install}/include",
        f"-DZSTD_LIBRARY={zstd_install}/lib/zstd_static.lib",
        f"-DZSTD_ROOT={zstd_install}",
        # HTTP/2
        "-DUSE_NGHTTP2=ON",
        f"-DNGHTTP2_INCLUDE_DIR={nghttp2_install}/include",
        f"-DNGHTTP2_LIBRARY={nghttp2_install}/lib/nghttp2.lib",
        f"-DNGHTTP2_ROOT={nghttp2_install}",
        # HTTP/3 (QUIC)
        "-DUSE_NGTCP2=ON",
        f"-DNGTCP2_INCLUDE_DIR={ngtcp2_install}/include",
        f"-DNGTCP2_LIBRARY={ngtcp2_install}/lib/ngtcp2.lib",
        f"-DNGTCP2_CRYPTO_BORINGSSL_LIBRARY={ngtcp2_install}/lib/ngtcp2_crypto_boringssl.lib",
        "-DUSE_NGHTTP3=ON",
        f"-DNGHTTP3_INCLUDE_DIR={nghttp3_install}/include",
        f"-DNGHTTP3_LIBRARY={nghttp3_install}/lib/nghttp3.lib",
        # Zlib
        f"-DZLIB_INCLUDE_DIR={zlib_install}/include",
        f"-DZLIB_LIBRARY={zlib_install}/lib/zlibstatic.lib",
        # SSH/SFTP
        "-DCURL_USE_LIBSSH2=ON",
        f"-DLIBSSH2_INCLUDE_DIR={libssh2_install}/include",
        f"-DLIBSSH2_LIBRARY={libssh2_install}/lib/libssh2.lib",
        # IDN - Use Windows native IDN API (no external lib needed)
        "-DUSE_WIN32_IDN=ON",
        "-DUSE_LIBIDN2=OFF",
        # libpsl - OFF on Windows (needs meson+libicu/libidn2 chain)
        "-DCURL_USE_LIBPSL=OFF",
        # No quiche (we use ngtcp2 for HTTP/3)
        "-DUSE_QUICHE=OFF",
        # No GSSAPI/Kerberos via MIT krb5 (Windows has SSPI)
        "-DCURL_USE_GSSAPI=OFF",
        # Enable all protocols
        "-DHTTP_ONLY=OFF",
        "-DCURL_DISABLE_HTTP=OFF",
        "-DCURL_DISABLE_FTP=OFF",
        "-DCURL_DISABLE_FILE=OFF",
        "-DCURL_DISABLE_LDAP=ON",
        "-DCURL_DISABLE_LDAPS=ON",
        "-DCURL_DISABLE_RTSP=OFF",
        "-DCURL_DISABLE_DICT=OFF",
        "-DCURL_DISABLE_TELNET=OFF",
        "-DCURL_DISABLE_TFTP=OFF",
        "-DCURL_DISABLE_IMAP=OFF",
        "-DCURL_DISABLE_POP3=OFF",
        "-DCURL_DISABLE_SMTP=OFF",
        "-DCURL_DISABLE_GOPHER=OFF",
        "-DCURL_DISABLE_MQTT=OFF",
        # Enable all features
        "-DCURL_ENABLE_NTLM=ON",
        "-DCURL_ENABLE_SMB=ON",
        "-DENABLE_WEBSOCKETS=ON",
        "-DCURL_DISABLE_COOKIES=OFF",
        "-DCURL_DISABLE_BASIC_AUTH=OFF",
        "-DCURL_DISABLE_BEARER_AUTH=OFF",
        "-DCURL_DISABLE_DIGEST_AUTH=OFF",
        "-DCURL_DISABLE_KERBEROS_AUTH=OFF",
        "-DCURL_DISABLE_NEGOTIATE_AUTH=OFF",
        "-DCURL_DISABLE_AWS=OFF",
        "-DCURL_DISABLE_ALTSVC=OFF",
        "-DCURL_DISABLE_DOH=OFF",
        "-DCURL_DISABLE_HSTS=OFF",
        "-DCURL_DISABLE_IPFS=OFF",
        "-DCURL_DISABLE_MIME=OFF",
        "-DCURL_DISABLE_NETRC=OFF",
        "-DCURL_DISABLE_PROXY=OFF",
        "-DCURL_DISABLE_SRP=OFF",
        "-DCURL_DISABLE_SHA512_256=OFF",
        "-DCURL_DISABLE_SHUFFLE_DNS=OFF",
        "-DCURL_DISABLE_PARSEDATE=OFF",
        "-DCURL_DISABLE_PROGRESS_METER=OFF",
        "-DCURL_DISABLE_HEADERS_API=OFF",
        "-DCURL_DISABLE_GETOPTIONS=OFF",
        "-DCURL_DISABLE_VERBOSE_STRINGS=OFF",
        # Manual
        "-DENABLE_MANUAL=OFF",
        # Hidden symbols for smaller DLL
        "-DCURL_HIDDEN_SYMBOLS=ON",
        "-DCURL_ENABLE_EXPORT_TARGET=OFF",
    ]

    # Add STATICLIB defines for static dependencies (Windows requires these
    # to avoid __declspec(dllimport) on function declarations in headers)
    cmake_args.append(
        "-DCMAKE_C_FLAGS=/DNGHTTP2_STATICLIB /DNGHTTP3_STATICLIB /DNGTCP2_STATICLIB /DLIBSSH2_API="
    )

    cmake_configure(src_dir, build_dir, install_dir, env, cmake_args)
    cmake_build(build_dir, env)

    # Find and copy DLL + lib
    dll_path = None
    lib_path = None
    for candidate in [
        build_dir / "lib" / "libcurl-impersonate.dll",
        build_dir / "lib" / "Release" / "libcurl-impersonate.dll",
        build_dir / "bin" / "libcurl-impersonate.dll",
    ]:
        if candidate.exists():
            dll_path = candidate
            break
    if not dll_path:
        # Search
        for f in build_dir.rglob("libcurl-impersonate.dll"):
            dll_path = f
            break

    for candidate in [
        build_dir / "lib" / "libcurl-impersonate.lib",
        build_dir / "lib" / "libcurl-impersonate_imp.lib",
        build_dir / "lib" / "Release" / "libcurl-impersonate.lib",
        build_dir / "lib" / "Release" / "libcurl-impersonate_imp.lib",
    ]:
        if candidate.exists():
            lib_path = candidate
            break
    if not lib_path:
        for f in build_dir.rglob("libcurl-impersonate.lib"):
            lib_path = f
            break

    if not dll_path:
        raise RuntimeError("libcurl-impersonate.dll not found after build")

    # Copy to output
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dll_path, output_dir / "libcurl-impersonate.dll")
    log(f"  Copied DLL: {dll_path}", "OK")
    if lib_path:
        shutil.copy2(lib_path, output_dir / "libcurl-impersonate.lib")
        log(f"  Copied lib: {lib_path}", "OK")

    # Copy curl-impersonate.exe if available
    exe_path = build_dir / "src" / "curl-impersonate.exe"
    if exe_path.exists():
        shutil.copy2(exe_path, output_dir / "curl-impersonate.exe")

    # Copy include headers
    inc_src = src_dir / "include"
    inc_dst = output_dir / "include"
    if inc_src.exists() and not inc_dst.exists():
        shutil.copytree(inc_src, inc_dst, dirs_exist_ok=True)

    log("curl-impersonate DLL build done.", "OK")
    return dll_path, lib_path

# ============================================================
# Build curl-impersonate static library
# ============================================================
def build_curl_static(src_dir, build_dir, install_dir, output_dir, deps_info, env, arch="x64"):
    """Build a combined static .lib that includes curl + all dependencies.

    Strategy:
    1. Restore CMakeLists.txt from git (remove DLL-only patches like WHOLEARCHIVE)
    2. Apply only static-compatible patches
    3. CMake builds curl as a static lib (BUILD_SHARED_LIBS=OFF)
    4. Use lib.exe to merge curl's static lib with all dependency static libs
       into a single libcurl-impersonate-static.lib
    """
    log("Building curl-impersonate static lib...")

    # Restore CMakeLists.txt from git to remove DLL-only patches (WHOLEARCHIVE etc.)
    # The DLL build patches CMakeLists.txt with target_link_options(${LIB_SHARED} ...)
    # which fails when BUILD_SHARED_LIBS=OFF (LIB_SHARED target doesn't exist)
    git_exe = env.get("GIT_EXE", "git")
    cmakelists = src_dir / "lib" / "CMakeLists.txt"
    if cmakelists.exists():
        # Try git checkout first
        result = run([git_exe, "checkout", "--", "lib/CMakeLists.txt"],
                      cwd=str(src_dir), env=env, check=False)
        if result.returncode != 0:
            # Fallback: manually remove WHOLEARCHIVE patch block
            content = cmakelists.read_text(encoding="utf-8", errors="replace")
            if "wholearchive_patched" in content:
                # Remove everything between the wholearchive markers
                pattern = r'\n\s*#\s*\[wholearchive_patched\].*?endif\(\)\s*\n'
                content = re.sub(pattern, '\n', content, flags=re.DOTALL)
                cmakelists.write_text(content, encoding="utf-8")
                log("  Removed WHOLEARCHIVE patch from CMakeLists.txt (manual fallback)")

    # Re-apply patches that are compatible with static builds
    # Fix VLA for MSVC
    fix_vla_script = WIN_BUILD_DIR / "fix_vla.py"
    if fix_vla_script.exists():
        run([sys.executable, str(fix_vla_script)], cwd=str(src_dir), env=env, check=False)
    # Fix BoringSSL detection
    if cmakelists.exists():
        bor_def_script = WIN_BUILD_DIR / "patch_boringssl_def.py"
        if bor_def_script.exists():
            run([sys.executable, str(bor_def_script), str(cmakelists)],
                env=env, check=False)
    # Do NOT apply patch_cmake_dll.py - it's DLL-only (WHOLEARCHIVE on ${LIB_SHARED})

    # Ensure output name is libcurl-impersonate
    lib_cmake = src_dir / "lib" / "CMakeLists.txt"
    if lib_cmake.exists():
        content = lib_cmake.read_text(encoding="utf-8", errors="replace")
        content = content.replace(
            "set(LIBCURL_OUTPUT_NAME libcurl CACHE",
            "set(LIBCURL_OUTPUT_NAME libcurl-impersonate CACHE"
        )
        lib_cmake.write_text(content, encoding="utf-8")

    # Get all install dirs
    boringssl_install = deps_info["boringssl"]["install"]
    brotli_install = deps_info["brotli"]["install"]
    zlib_install = deps_info["zlib"]["install"]
    nghttp2_install = deps_info["nghttp2"]["install"]
    nghttp3_install = deps_info["nghttp3"]["install"]
    ngtcp2_install = deps_info["ngtcp2"]["install"]
    zstd_install = deps_info["zstd"]["install"]
    libssh2_install = deps_info["libssh2"]["install"]

    cmake_args = [
        "-DBUILD_SHARED_LIBS=OFF",
        "-DBUILD_STATIC_LIBS=ON",
        "-DBUILD_CURL_EXE=OFF",
        "-DBUILD_TESTING=OFF",
        # Use static libs for dependencies
        "-DNGHTTP2_USE_STATIC_LIBS=ON",
        "-DNGHTTP3_USE_STATIC_LIBS=ON",
        "-DNGTCP2_USE_STATIC_LIBS=ON",
        "-DBROTLI_USE_STATIC_LIBS=ON",
        "-DZSTD_USE_STATIC_LIBS=ON",
        "-DLIBSSH2_USE_STATIC_LIBS=ON",
        # SSL/TLS
        "-DCURL_USE_OPENSSL=ON",
        "-DHAVE_BORINGSSL=ON",
        f"-DCMAKE_PREFIX_PATH={boringssl_install};{brotli_install};{zlib_install};{nghttp2_install};{nghttp3_install};{ngtcp2_install};{zstd_install};{libssh2_install}",
        f"-DOPENSSL_ROOT_DIR={boringssl_install}",
        f"-DZLIB_ROOT={zlib_install}",
        # Compression
        "-DCURL_BROTLI=ON",
        f"-DBROTLI_INCLUDE_DIR={brotli_install}/include",
        f"-DBROTLI_LIBRARY={brotli_install}/lib/brotlidec.lib",
        f"-DBROTLIDEC_LIBRARY={brotli_install}/lib/brotlidec.lib",
        f"-DBROTLIENC_LIBRARY={brotli_install}/lib/brotlienc.lib",
        f"-DBROTLI_ENCODER_LIBRARY={brotli_install}/lib/brotlienc.lib",
        f"-DBROTLI_COMMON_LIBRARY={brotli_install}/lib/brotlicommon.lib",
        f"-DBROTLICOMMON_LIBRARY={brotli_install}/lib/brotlicommon.lib",
        "-DCURL_ZSTD=ON",
        f"-DZSTD_INCLUDE_DIR={zstd_install}/include",
        f"-DZSTD_LIBRARY={zstd_install}/lib/zstd_static.lib",
        f"-DZSTD_ROOT={zstd_install}",
        # HTTP/2
        "-DUSE_NGHTTP2=ON",
        f"-DNGHTTP2_INCLUDE_DIR={nghttp2_install}/include",
        f"-DNGHTTP2_LIBRARY={nghttp2_install}/lib/nghttp2.lib",
        f"-DNGHTTP2_ROOT={nghttp2_install}",
        # HTTP/3 (QUIC)
        "-DUSE_NGTCP2=ON",
        f"-DNGTCP2_INCLUDE_DIR={ngtcp2_install}/include",
        f"-DNGTCP2_LIBRARY={ngtcp2_install}/lib/ngtcp2.lib",
        f"-DNGTCP2_CRYPTO_BORINGSSL_LIBRARY={ngtcp2_install}/lib/ngtcp2_crypto_boringssl.lib",
        "-DUSE_NGHTTP3=ON",
        f"-DNGHTTP3_INCLUDE_DIR={nghttp3_install}/include",
        f"-DNGHTTP3_LIBRARY={nghttp3_install}/lib/nghttp3.lib",
        # Zlib
        f"-DZLIB_INCLUDE_DIR={zlib_install}/include",
        f"-DZLIB_LIBRARY={zlib_install}/lib/zlibstatic.lib",
        # SSH/SFTP
        "-DCURL_USE_LIBSSH2=ON",
        f"-DLIBSSH2_INCLUDE_DIR={libssh2_install}/include",
        f"-DLIBSSH2_LIBRARY={libssh2_install}/lib/libssh2.lib",
        # IDN
        "-DUSE_WIN32_IDN=ON",
        "-DUSE_LIBIDN2=OFF",
        "-DCURL_USE_LIBPSL=OFF",
        "-DUSE_QUICHE=OFF",
        "-DCURL_USE_GSSAPI=OFF",
        # Protocols
        "-DHTTP_ONLY=OFF",
        "-DCURL_DISABLE_HTTP=OFF",
        "-DCURL_DISABLE_FTP=OFF",
        "-DCURL_DISABLE_FILE=OFF",
        "-DCURL_DISABLE_LDAP=ON",
        "-DCURL_DISABLE_LDAPS=ON",
        "-DCURL_DISABLE_RTSP=OFF",
        "-DCURL_DISABLE_DICT=OFF",
        "-DCURL_DISABLE_TELNET=OFF",
        "-DCURL_DISABLE_TFTP=OFF",
        "-DCURL_DISABLE_IMAP=OFF",
        "-DCURL_DISABLE_POP3=OFF",
        "-DCURL_DISABLE_SMTP=OFF",
        "-DCURL_DISABLE_GOPHER=OFF",
        "-DCURL_DISABLE_MQTT=OFF",
        # Features
        "-DCURL_ENABLE_NTLM=ON",
        "-DCURL_ENABLE_SMB=ON",
        "-DENABLE_WEBSOCKETS=ON",
        "-DCURL_DISABLE_COOKIES=OFF",
        "-DCURL_DISABLE_BASIC_AUTH=OFF",
        "-DCURL_DISABLE_BEARER_AUTH=OFF",
        "-DCURL_DISABLE_DIGEST_AUTH=OFF",
        "-DCURL_DISABLE_KERBEROS_AUTH=OFF",
        "-DCURL_DISABLE_NEGOTIATE_AUTH=OFF",
        "-DCURL_DISABLE_AWS=OFF",
        "-DCURL_DISABLE_ALTSVC=OFF",
        "-DCURL_DISABLE_DOH=OFF",
        "-DCURL_DISABLE_HSTS=OFF",
        "-DCURL_DISABLE_IPFS=OFF",
        "-DCURL_DISABLE_MIME=OFF",
        "-DCURL_DISABLE_NETRC=OFF",
        "-DCURL_DISABLE_PROXY=OFF",
        "-DCURL_DISABLE_SRP=OFF",
        "-DCURL_DISABLE_SHA512_256=OFF",
        "-DCURL_DISABLE_SHUFFLE_DNS=OFF",
        "-DCURL_DISABLE_PARSEDATE=OFF",
        "-DCURL_DISABLE_PROGRESS_METER=OFF",
        "-DCURL_DISABLE_HEADERS_API=OFF",
        "-DCURL_DISABLE_GETOPTIONS=OFF",
        "-DCURL_DISABLE_VERBOSE_STRINGS=OFF",
        "-DENABLE_MANUAL=OFF",
        # Static lib: no hidden symbols, no export target
        "-DCURL_HIDDEN_SYMBOLS=OFF",
        "-DCURL_ENABLE_EXPORT_TARGET=OFF",
        # CMAKE_STATICLIB_PREFIX/SUFFIX not needed - default produces .lib
    ]

    # Static defines for dependency headers
    cmake_args.append(
        "-DCMAKE_C_FLAGS=/DNGHTTP2_STATICLIB /DNGHTTP3_STATICLIB /DNGTCP2_STATICLIB /DLIBSSH2_API= /DCURL_STATICLIB"
    )

    cmake_configure(src_dir, build_dir, install_dir, env, cmake_args)
    cmake_build(build_dir, env)

    # Find curl's static lib
    curl_static_lib = None
    for candidate in [
        build_dir / "lib" / "libcurl-impersonate.lib",
        build_dir / "lib" / "Release" / "libcurl-impersonate.lib",
    ]:
        if candidate.exists():
            curl_static_lib = candidate
            break
    if not curl_static_lib:
        for f in build_dir.rglob("libcurl-impersonate.lib"):
            curl_static_lib = f
            break

    if not curl_static_lib:
        log("  curl static lib not found, skipping combined static lib", "WARN")
        return None

    # Collect all dependency static libs
    dep_libs = []
    # BoringSSL
    for name in ["libssl.lib", "libcrypto.lib"]:
        p = boringssl_install / "lib" / name
        if p.exists():
            dep_libs.append(p)
    # zlib
    p = zlib_install / "lib" / "zlibstatic.lib"
    if p.exists():
        dep_libs.append(p)
    # brotli
    for name in ["brotlidec.lib", "brotlienc.lib", "brotlicommon.lib"]:
        p = brotli_install / "lib" / name
        if p.exists():
            dep_libs.append(p)
    # nghttp2
    p = nghttp2_install / "lib" / "nghttp2.lib"
    if p.exists():
        dep_libs.append(p)
    # ngtcp2
    for name in ["ngtcp2.lib", "ngtcp2_crypto_boringssl.lib"]:
        p = ngtcp2_install / "lib" / name
        if p.exists():
            dep_libs.append(p)
    # nghttp3
    p = nghttp3_install / "lib" / "nghttp3.lib"
    if p.exists():
        dep_libs.append(p)
    # zstd
    p = zstd_install / "lib" / "zstd_static.lib"
    if p.exists():
        dep_libs.append(p)
    # libssh2
    p = libssh2_install / "lib" / "libssh2.lib"
    if p.exists():
        dep_libs.append(p)

    all_libs = [curl_static_lib] + dep_libs
    log(f"  Merging {len(all_libs)} static libs into combined archive...")

    # Use lib.exe to merge all static libs into one
    output_lib = output_dir / "libcurl-impersonate-static.lib"
    output_dir.mkdir(parents=True, exist_ok=True)

    # lib.exe /OUT:combined.lib lib1.lib lib2.lib ...
    # Find lib.exe - MSVC's library manager (not GNU lib or other tools)
    # vcvarsall.bat may not add MSVC bin dir to PATH, so search multiple ways
    lib_exe = None
    # Method 1: search PATH for lib.exe
    lib_which = shutil.which("lib.exe", path=env.get("PATH", ""))
    if lib_which and ("msvc" in lib_which.lower() or "visual studio" in lib_which.lower()):
        lib_exe = lib_which
    # Method 2: infer from LIB env var (e.g. LIB=C:\...\VC\Tools\MSVC\14.44\lib\x64;...)
    if not lib_exe:
        lib_var = env.get("LIB", "")
        for lib_dir in lib_var.split(";"):
            lib_dir = lib_dir.strip()
            # Look for pattern: VC\Tools\MSVC\<version>\lib\<arch>
            if "VC\\Tools\\MSVC" in lib_dir and "\\lib\\" in lib_dir:
                # Replace \lib\x64 with \bin\Hostx64\x64 (or \bin\Hostx64\x86 for x86)
                host_arch = "Hostx64"
                target_arch_dir = "x64" if "x64" in arch else "x86"
                bin_dir = lib_dir.replace("\\lib\\x64", f"\\bin\\{host_arch}\\{target_arch_dir}")
                bin_dir = bin_dir.replace("\\lib\\x86", f"\\bin\\{host_arch}\\{target_arch_dir}")
                lib_candidate = Path(bin_dir) / "lib.exe"
                if lib_candidate.exists():
                    lib_exe = str(lib_candidate)
                    break
    # Method 3: try finding via dumpbin path (same directory)
    if not lib_exe:
        dumpbin_path = shutil.which("dumpbin", path=env.get("PATH", ""))
        if dumpbin_path:
            lib_candidate = Path(dumpbin_path).parent / "lib.exe"
            if lib_candidate.exists():
                lib_exe = str(lib_candidate)
    if not lib_exe:
        log("  lib.exe not found in MSVC PATH, copying curl static lib as-is", "WARN")
        log("  (combined static lib will only contain curl, not dependencies)", "WARN")
        shutil.copy2(curl_static_lib, output_lib)
        log(f"  Copied static lib: {output_lib}", "OK")
        return output_lib

    cmd = [lib_exe, f"/OUT:{output_lib}"] + [str(p) for p in all_libs]
    result = run(cmd, env=env, check=False)
    if result.returncode != 0:
        log(f"  lib.exe merge failed (rc={result.returncode}), copying curl static lib as-is", "WARN")
        shutil.copy2(curl_static_lib, output_lib)
    else:
        log(f"  Combined static lib: {output_lib}", "OK")

    # Copy include headers (if not already done by DLL build)
    inc_src = src_dir / "include"
    inc_dst = output_dir / "include"
    if inc_src.exists() and not inc_dst.exists():
        shutil.copytree(inc_src, inc_dst, dirs_exist_ok=True)

    log("curl-impersonate static lib build done.", "OK")
    return output_lib

# ============================================================
# Verify DLL
# ============================================================
def verify_dll(dll_path, env, arch="x64"):
    """Verify DLL dependencies and basic functionality."""
    log("Verifying DLL...")
    if not dll_path or not dll_path.exists():
        log("DLL not found for verification!", "ERROR")
        return False

    # Check DLL dependencies via dumpbin
    # dumpbin lives in MSVC bin dir which is in env (from vcvarsall), but may not
    # be on the system PATH that subprocess uses.  Search env["PATH"] explicitly.
    dumpbin_path = shutil.which("dumpbin", path=env.get("PATH", ""))
    if dumpbin_path:
        result = run([dumpbin_path, "/dependents", str(dll_path)], env=env, check=False)
        if result.returncode == 0:
            non_system = []
            for line in result.stdout.splitlines():
                line = line.strip().lower()
                # Skip dumpbin header lines like "Dump of file ...\xxx.dll"
                if line.startswith("dump of file"):
                    continue
                if line.endswith(".dll"):
                    if line not in SYSTEM_DLLS:
                        non_system.append(line)
            if non_system:
                log(f"  Non-system DLL dependencies: {non_system}", "WARN")
            else:
                log("  All dependencies are system DLLs", "OK")
        else:
            log("  dumpbin failed", "WARN")
    else:
        log("  dumpbin not found in MSVC PATH, skipping dependency check", "WARN")

    # Check DLL exports via dumpbin
    if dumpbin_path:
        result = run([dumpbin_path, "/exports", str(dll_path)], env=env, check=False)
        if result.returncode == 0:
            exports = [l.strip() for l in result.stdout.splitlines()
                       if l.strip() and not l.strip().startswith((".", "=", "ordinal", "Summary", "Microsoft", "Copyright", "Dump", "File"))]
            # Filter to actual symbol names (lines with ordinal numbers)
            syms = []
            for l in exports:
                parts = l.split()
                if len(parts) >= 3 and parts[0].isdigit():
                    syms.append(parts[-1])
            log(f"  Exported symbols: {len(syms)}")
            key_syms = [s for s in syms if s.startswith("curl_easy_impersonate")]
            if key_syms:
                log(f"  Impersonate APIs: {', '.join(key_syms)}", "OK")
            else:
                log("  No curl_easy_impersonate exports found!", "ERROR")
        else:
            log("  dumpbin /exports failed", "WARN")

    # Load DLL and check version info
    # 64-bit Python cannot load 32-bit DLLs and vice versa
    python_bits = struct.calcsize("P") * 8
    dll_is_32bit = "x86" in arch.lower()
    can_load = (python_bits == 32 and dll_is_32bit) or (python_bits == 64 and not dll_is_32bit)
    if not can_load:
        log(f"  DLL load test: skipped ({python_bits}-bit Python cannot load {'32' if dll_is_32bit else '64'}-bit DLL)")
    else:
        try:
            result = run(
                ["python", "-c",
                 "import ctypes; dll=ctypes.WinDLL(r'%s'); "
                 "dll.curl_version.restype=ctypes.c_char_p; "
                 "v=dll.curl_version(); print('Version:', v.decode())" % dll_path],
                check=False
            )
            if result.returncode == 0:
                log("  DLL load test: OK", "OK")
                for line in result.stdout.splitlines():
                    if line.strip():
                        log(f"    {line.strip()}")
            else:
                log("  DLL load test failed (may need runtime deps)", "WARN")
        except Exception as e:
            log(f"  DLL load test error: {e}", "WARN")

    return True

# ============================================================
# Main build pipeline
# ============================================================
def build_arch(arch, vcvarsall, skip_download=False, keep_intermediates=False):
    """Build for a single architecture."""
    log(f"\n{'='*60}")
    log(f"Building for {arch}")
    log(f"{'='*60}")

    dirs = ARCH_DIRS[arch]
    deps_dir = ROOT_DIR / "deps"
    build_dir = ROOT_DIR / dirs["build"]
    install_dir = ROOT_DIR / dirs["install"]
    output_dir = ROOT_DIR / dirs["output"]

    # Setup MSVC environment
    env = setup_msvc_env(arch, vcvarsall)

    # Verify tools
    for tool in ["cmake", "ninja", "git"]:
        if tool not in env.get("PATH", "").lower():
            result = run(["where", tool], env=env, check=False)
            if result.returncode != 0:
                raise RuntimeError(f"{tool} not found in PATH")

    # Set CMAKE_EXE and NINJA_EXE in env
    for tool in ["cmake", "ninja", "git", "nasm", "python"]:
        result = run(["where", tool], env=env, check=False)
        if result.returncode == 0:
            path = result.stdout.strip().splitlines()[0]
            env[f"{tool.upper()}_EXE"] = path
            if tool == "python":
                env["PYTHON_EXE"] = path
        elif tool == "nasm":
            # nasm may not be in vcvarsall PATH, search common locations
            nasm_candidates = [
                r"C:\vcpkg\downloads\tools\nasm\nasm-3.01\nasm.exe",
                r"C:\msys64\mingw64\bin\nasm.exe",
                r"C:\Program Files\NASM\nasm.exe",
            ]
            for c in nasm_candidates:
                if Path(c).exists():
                    env["NASM_EXE"] = c
                    # Also add to PATH so cmake can find it
                    env["PATH"] = str(Path(c).parent) + ";" + env.get("PATH", "")
                    log(f"  Found nasm at: {c}", "OK")
                    break
            else:
                log("  nasm not found! BoringSSL build will fail.", "WARN")

    # Clean build and install dirs for this arch
    rmtree_safe(build_dir)
    rmtree_safe(install_dir)
    rmtree_safe(output_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    install_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Download sources (shared between architectures, only on first arch)
    if not (deps_dir / ".sources_downloaded").exists():
        archives = download_all_sources(deps_dir)
        extract_sources(deps_dir, archives)
        (deps_dir / ".sources_downloaded").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        log("  Sources already downloaded, checking extraction...")
        # Even if marker exists, verify extraction and re-extract if needed
        FNAME_MAP = {
            "ngtcp2": f"ngtcp2-{NGTCP2_VERSION}.tar.gz",
            "nghttp3": f"nghttp3-{NGHTTP3_VERSION}.tar.gz",
            "brotli": f"brotli-{BROTLI_VERSION}.tar.gz",
            "zlib": f"zlib-{ZLIB_VERSION}.tar.gz",
        }
        archives = {}
        # Build archives dict from existing files for re-extraction check
        for name, url in URLS.items():
            fname = FNAME_MAP.get(name, url.split("/")[-1])
            dest = deps_dir / fname
            if dest.exists():
                archives[name] = dest
        extract_sources(deps_dir, archives)

    # Apply patches (skip if already patched - .patched marker)
    git_exe = env.get("GIT_EXE", "git")
    if not (deps_dir / ".all_patched").exists():
        apply_all_patches(deps_dir, git_exe)
        (deps_dir / ".all_patched").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        log("  Patches already applied (skipping).")

    # Build each dependency in order
    deps_info = {}
    dep_configs = {
        "zlib": {
            "src": deps_dir / f"zlib-{ZLIB_VERSION}",
            "build": build_dir / "zlib",
            "install": install_dir / "zlib",
            "builder": lambda s, b, i, e: build_zlib(s, b, i, e),
        },
        "zstd": {
            "src": deps_dir / f"zstd-{ZSTD_VERSION}",
            "build": build_dir / "zstd",
            "install": install_dir / "zstd",
            "builder": lambda s, b, i, e: build_zstd(s, b, i, e),
        },
        "brotli": {
            "src": deps_dir / f"brotli-{BROTLI_VERSION}",
            "build": build_dir / "brotli",
            "install": install_dir / "brotli",
            "builder": lambda s, b, i, e: build_brotli(s, b, i, e),
        },
        "nghttp2": {
            "src": deps_dir / f"nghttp2-{NGHTTP2_VERSION}",
            "build": build_dir / "nghttp2",
            "install": install_dir / "nghttp2",
            "builder": lambda s, b, i, e: build_nghttp2(s, b, i, e),
        },
        "nghttp3": {
            "src": deps_dir / f"nghttp3-{NGHTTP3_VERSION}",
            "build": build_dir / "nghttp3",
            "install": install_dir / "nghttp3",
            "builder": lambda s, b, i, e: build_nghttp3(s, b, i, e),
        },
        "boringssl": {
            "src": deps_dir / "boringssl",
            "build": build_dir / "boringssl",
            "install": install_dir / "boringssl",
            "builder": lambda s, b, i, e: build_boringssl(s, b, i, e),
        },
        "ngtcp2": {
            "src": deps_dir / f"ngtcp2-{NGTCP2_VERSION}",
            "build": build_dir / "ngtcp2",
            "install": install_dir / "ngtcp2",
            "builder": lambda s, b, i, e: build_ngtcp2(s, b, i,
                deps_info["boringssl"]["install"], e),
        },
        "libssh2": {
            "src": deps_dir / f"libssh2-{LIBSSH2_VERSION}",
            "build": build_dir / "libssh2",
            "install": install_dir / "libssh2",
            "builder": lambda s, b, i, e: build_libssh2(s, b, i,
                deps_info["boringssl"]["install"], deps_info["zlib"]["install"], e),
        },
    }

    for dep_name in BUILD_ORDER[:-1]:  # All except curl
        if dep_name not in dep_configs:
            continue
        cfg = dep_configs[dep_name]
        deps_info[dep_name] = {"src": cfg["src"], "build": cfg["build"], "install": cfg["install"]}
        t0 = time.time()
        try:
            cfg["builder"](cfg["src"], cfg["build"], cfg["install"], env)
        except Exception as e:
            log(f"{dep_name} build FAILED: {e}", "ERROR")
            raise
        elapsed = time.time() - t0
        log(f"{dep_name} completed in {elapsed:.0f}s")

    # Build curl (final)
    curl_src = deps_dir / CURL_VERSION_DIR
    curl_build = build_dir / "curl"
    curl_install = install_dir / "curl"
    deps_info["curl"] = {"src": curl_src, "build": curl_build, "install": curl_install}

    t0 = time.time()
    dll_path, lib_path = build_curl(
        curl_src, curl_build, curl_install, output_dir, deps_info, env, arch=arch
    )
    elapsed = time.time() - t0
    log(f"curl-impersonate completed in {elapsed:.0f}s")

    # Verify DLL
    verify_dll(output_dir / "libcurl-impersonate.dll", env, arch)

    # Build static lib (after DLL, so dependencies are already built)
    curl_build_static = build_dir / "curl-static"
    curl_install_static = install_dir / "curl-static"
    t0 = time.time()
    static_lib = build_curl_static(
        curl_src, curl_build_static, curl_install_static, output_dir, deps_info, env, arch=arch
    )
    elapsed = time.time() - t0
    log(f"curl-impersonate static lib completed in {elapsed:.0f}s")

    # Cleanup for this arch (if not keeping intermediates)
    if not keep_intermediates:
        rmtree_safe(build_dir)
        rmtree_safe(install_dir)

    return True

# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Build curl-impersonate from scratch")
    parser.add_argument("--arch", default="x64,x86", help="Target architectures (default: x64,x86)")
    parser.add_argument("--vs", default="2022", help="Visual Studio version (default: 2022)")
    parser.add_argument("--skip-clean", action="store_true", help="Skip initial cleanup")
    parser.add_argument("--skip-build", action="store_true", help="Skip build (for testing)")
    parser.add_argument("--keep-intermediates", action="store_true", help="Keep build/deps/install")
    parser.add_argument("--only-arch", default=None, help="Build only one architecture")
    args = parser.parse_args()

    log("=" * 60)
    log("  curl-impersonate Unified Build Script")
    log("  (from scratch: download → patch → build → verify → cleanup)")
    log("=" * 60)

    # Determine architectures
    if args.only_arch:
        archs = [args.only_arch]
    else:
        archs = [a.strip() for a in args.arch.split(",")]

    # Find VS
    vs_path, vcvarsall = find_vs(args.vs)
    log(f"VS Path: {vs_path}")
    log(f"vcvarsall: {vcvarsall}")

    # Step 1: Clean everything
    if not args.skip_clean:
        log("\n[1] Cleaning all intermediate files...")
        for arch in archs:
            dirs = ARCH_DIRS[arch]
            rmtree_safe(ROOT_DIR / dirs["build"])
            rmtree_safe(ROOT_DIR / dirs["install"])
            rmtree_safe(ROOT_DIR / dirs["output"])
        # Clean deps (will be re-downloaded and extracted)
        rmtree_safe(ROOT_DIR / "deps")
        # Clean old patches
        rmtree_safe(ROOT_DIR / "patches")
        rmtree_safe(ROOT_DIR / "lexiforest_patches")
        # Clean marker files
        for marker in ["deps/.sources_downloaded", "deps/.all_patched"]:
            p = ROOT_DIR / marker
            if p.exists():
                p.unlink()
        log("Cleanup done.", "OK")

    # Ensure patches exists
    if not PATCHES_DIR.exists():
        log(f"patches/ directory not found at {PATCHES_DIR}", "ERROR")
        log("Run patch generation first: generate patches from git diffs", "ERROR")
        sys.exit(1)

    if args.skip_build:
        log("Skip build requested. Exiting.")
        return

    # Step 2-6: Build for each architecture
    total_t0 = time.time()
    for arch in archs:
        try:
            build_arch(arch, vcvarsall, keep_intermediates=args.keep_intermediates)
        except Exception as e:
            log(f"Build FAILED for {arch}: {e}", "ERROR")
            sys.exit(1)

    # Step 7: Final cleanup (deps)
    if not args.keep_intermediates:
        log("\n[7] Final cleanup - removing deps...")
        rmtree_safe(ROOT_DIR / "deps")

    # Summary
    total_elapsed = time.time() - total_t0
    log("\n" + "=" * 60)
    log("  BUILD COMPLETE")
    log("=" * 60)
    for arch in archs:
        dirs = ARCH_DIRS[arch]
        output_dir = ROOT_DIR / dirs["output"]
        if output_dir.exists():
            log(f"\n  {arch} output ({output_dir}):")
            for f in sorted(output_dir.iterdir()):
                if f.is_file():
                    size_mb = f.stat().st_size / (1024 * 1024)
                    log(f"    {f.name:40s} {size_mb:8.2f} MB")
    log(f"\n  Total build time: {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")
    log("=" * 60)

if __name__ == "__main__":
    main()

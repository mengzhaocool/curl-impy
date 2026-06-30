"""Rebuild DLL with full symbol export via .def file"""
import subprocess
import os
import shutil
import sys
import time

BASE = r'd:\curl-impersonate-8.20.0'
BUILD_DIR = os.path.join(BASE, 'build', 'curl-dll')
OUTPUT_DIR = os.path.join(BASE, 'output')
CURL_SRC = os.path.join(BASE, 'deps', 'curl-8.20.0')
NINJA = r'C:\vcpkg\downloads\tools\ninja-1.13.2-windows\ninja.exe'
CMAKE = r'C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe'

def run(cmd, cwd=None, timeout=600):
    print(f"  CMD: {cmd[:200]}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout
    )
    if result.stdout:
        for line in result.stdout.splitlines()[-20:]:
            print(f"  {line}")
    if result.returncode != 0:
        print(f"  FAILED (rc={result.returncode})")
        if result.stderr:
            for line in result.stderr.splitlines()[-20:]:
                print(f"  ERR: {line}")
    return result.returncode == 0

def main():
    # Step 1: Clean CMake cache
    print("[1] Cleaning CMake cache...")
    cache = os.path.join(BUILD_DIR, 'CMakeCache.txt')
    exports_def = os.path.join(BUILD_DIR, 'lib', 'CMakeFiles', 'libcurl_shared.dir', 'exports.def')
    if os.path.exists(cache):
        os.remove(cache)
        print(f"  Removed: {cache}")
    if os.path.exists(exports_def):
        os.remove(exports_def)
        print(f"  Removed: {exports_def}")
    
    # Step 2: CMake configure
    print("[2] CMake configure...")
    cmake_args = [
        CMAKE, '-G', 'Ninja', '-S', CURL_SRC, '-B', BUILD_DIR,
        f'-DCMAKE_INSTALL_PREFIX={BASE}/install/curl',
        f'-DCMAKE_MAKE_PROGRAM={NINJA}',
        '-DCMAKE_C_COMPILER=cl',
        '-DCMAKE_CXX_COMPILER=cl',
        '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_FLAGS=/DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB',
        '-DCMAKE_CXX_FLAGS=/EHsc /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB',
        '-DBUILD_SHARED_LIBS=ON',
        '-DBUILD_STATIC_LIBS=OFF',
        '-DCURL_USE_OPENSSL=ON',
        '-DHAVE_BORINGSSL=ON',
        f'-DOPENSSL_ROOT_DIR={BASE}/install/boringssl',
        f'-DOPENSSL_INCLUDE_DIR={BASE}/install/boringssl/include',
        f'-DOPENSSL_LIBRARIES={BASE}/install/boringssl/lib/libssl.lib;{BASE}/install/boringssl/lib/libcrypto.lib',
        '-DCURL_BROTLI=ON',
        f'-DBROTLI_INCLUDE_DIR={BASE}/install/brotli/include',
        f'-DBROTLIDEC_LIBRARY={BASE}/install/brotli/lib/brotlidec.lib',
        f'-DBROTLIENC_LIBRARY={BASE}/install/brotli/lib/brotlienc.lib',
        f'-DBROTLICOMMON_LIBRARY={BASE}/install/brotli/lib/brotlicommon.lib',
        '-DUSE_NGHTTP2=ON',
        f'-DNGHTTP2_INCLUDE_DIR={BASE}/install/nghttp2/include',
        f'-DNGHTTP2_LIBRARY={BASE}/install/nghttp2/lib/nghttp2.lib',
        f'-DNGHTTP2_ROOT={BASE}/install/nghttp2',
        '-DUSE_NGTCP2=ON',
        f'-DNGTCP2_INCLUDE_DIR={BASE}/install/ngtcp2/include',
        f'-DNGTCP2_LIBRARY={BASE}/install/ngtcp2/lib/ngtcp2.lib',
        f'-DNGTCP2_CRYPTO_BORINGSSL_LIBRARY={BASE}/install/ngtcp2/lib/ngtcp2_crypto_boringssl.lib',
        '-DUSE_NGHTTP3=ON',
        f'-DNGHTTP3_INCLUDE_DIR={BASE}/install/nghttp3/include',
        f'-DNGHTTP3_LIBRARY={BASE}/install/nghttp3/lib/nghttp3.lib',
        f'-DZLIB_INCLUDE_DIR={BASE}/install/zlib/include',
        f'-DZLIB_LIBRARY={BASE}/install/zlib/lib/zlibstatic.lib',
        f'-DZLIB_ROOT={BASE}/install/zlib',
        '-DCURL_ZSTD=ON',
        f'-DZSTD_INCLUDE_DIR={BASE}/install/zstd/include',
        f'-DZSTD_LIBRARY={BASE}/install/zstd/lib/zstd_static.lib',
        f'-DZSTD_ROOT={BASE}/install/zstd',
        '-DHTTP_ONLY=OFF',
        '-DENABLE_WEBSOCKETS=ON',
        '-DUSE_LIBIDN2=OFF',
        '-DCURL_USE_LIBPSL=OFF',
        '-DUSE_QUICHE=OFF',
        '-DENABLE_MANUAL=OFF',
        '-DCURL_USE_LIBSSH2=OFF',
        '-DCURL_USE_GSSAPI=OFF',
        '-DBUILD_CURL_EXE=OFF',
        '-DCURL_HIDDEN_SYMBOLS=ON',  # Use .def file for symbol export
        '-DCURL_STATIC_CRT=ON',
    ]
    
    cmd = ' '.join(f'"{a}"' if ' ' in a else a for a in cmake_args)
    if not run(cmd, timeout=300):
        print("FATAL: CMake configure failed!")
        sys.exit(1)
    
    # Step 2b: Check exports.def
    print("[2b] Checking exports.def...")
    if os.path.exists(exports_def):
        sz = os.path.getsize(exports_def)
        lines = open(exports_def, encoding='utf-8', errors='replace').readlines()
        print(f"  exports.def: {sz:,} bytes, {len(lines)} lines")
        ssl_count = sum(1 for l in lines if 'SSL_' in l)
        brotli_count = sum(1 for l in lines if 'BrotliDecoder' in l)
        print(f"  SSL_ entries: {ssl_count}")
        print(f"  BrotliDecoder entries: {brotli_count}")
    else:
        print("  exports.def not yet generated (will be during build)")
    
    # Step 3: Build
    print("[3] Building DLL...")
    if not run(f'"{CMAKE}" --build "{BUILD_DIR}" --config Release', timeout=600):
        print("FATAL: Build failed!")
        sys.exit(1)
    
    # Step 4: Copy output
    print("[4] Copying output...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for search_dir in [os.path.join(BUILD_DIR, 'lib'), os.path.join(BUILD_DIR, 'bin')]:
        dll = os.path.join(search_dir, 'libcurl-impersonate.dll')
        if os.path.exists(dll):
            shutil.copy2(dll, OUTPUT_DIR)
            shutil.copy2(dll, BASE)
            print(f"  Copied DLL: {dll} ({os.path.getsize(dll):,} bytes)")
        implib = os.path.join(search_dir, 'libcurl-impersonate_imp.lib')
        if os.path.exists(implib):
            shutil.copy2(implib, OUTPUT_DIR)
            print(f"  Copied import lib: {implib}")
    
    # Step 5: Merge static lib
    print("[5] Merging static lib...")
    curl_static = os.path.join(BASE, 'build', 'curl', 'lib', 'libcurl-impersonate.lib')
    if os.path.exists(curl_static):
        merge_libs = [
            curl_static,
            f'{BASE}/install/boringssl/lib/libssl.lib',
            f'{BASE}/install/boringssl/lib/libcrypto.lib',
            f'{BASE}/install/zlib/lib/zlibstatic.lib',
            f'{BASE}/install/brotli/lib/brotlidec.lib',
            f'{BASE}/install/brotli/lib/brotlienc.lib',
            f'{BASE}/install/brotli/lib/brotlicommon.lib',
            f'{BASE}/install/nghttp2/lib/nghttp2.lib',
            f'{BASE}/install/ngtcp2/lib/ngtcp2.lib',
            f'{BASE}/install/ngtcp2/lib/ngtcp2_crypto_boringssl.lib',
            f'{BASE}/install/nghttp3/lib/nghttp3.lib',
            f'{BASE}/install/zstd/lib/zstd_static.lib',
        ]
        merged = os.path.join(OUTPUT_DIR, 'libcurl-impersonate.lib')
        lib_cmd = f'lib.exe /OUT:"{merged}" ' + ' '.join(f'"{l}"' for l in merge_libs)
        if run(lib_cmd):
            print(f"  Merged static lib: {merged} ({os.path.getsize(merged):,} bytes)")
    
    # Summary
    print("\n" + "=" * 60)
    print("  REBUILD COMPLETE")
    print("=" * 60)
    for f in ['libcurl-impersonate.dll', 'libcurl-impersonate_imp.lib', 'libcurl-impersonate.lib']:
        p = os.path.join(OUTPUT_DIR, f)
        if os.path.exists(p):
            print(f"  {f}: {os.path.getsize(p):,} bytes ({os.path.getsize(p)/1024/1024:.1f} MB)")

if __name__ == '__main__':
    main()

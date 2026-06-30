"""Debug WHOLEARCHIVE: check if the cmake conditions are met"""
import os

BASE = r"d:\curl-impersonate-8.20.0"
INSTALL = os.path.join(BASE, "install")

# Check paths that the CMakeLists.txt checks with EXISTS
checks = {
    'OPENSSL_LIBRARIES[0]': os.path.join(INSTALL, "boringssl", "lib", "libssl.lib"),
    'OPENSSL_LIBRARIES[1]': os.path.join(INSTALL, "boringssl", "lib", "libcrypto.lib"),
    'ZLIB_LIBRARY': os.path.join(INSTALL, "zlib", "lib", "zlibstatic.lib"),
    'BROTLIDEC_LIBRARY': os.path.join(INSTALL, "brotli", "lib", "brotlidec.lib"),
    'brotlienc': os.path.join(INSTALL, "brotli", "lib", "brotlienc.lib"),
    'brotlicommon': os.path.join(INSTALL, "brotli", "lib", "brotlicommon.lib"),
    'NGHTTP2_LIBRARY': os.path.join(INSTALL, "nghttp2", "lib", "nghttp2.lib"),
    'NGTCP2_LIBRARY': os.path.join(INSTALL, "ngtcp2", "lib", "ngtcp2.lib"),
    'NGTCP2_CRYPTO_LIBRARY': os.path.join(INSTALL, "ngtcp2", "lib", "ngtcp2_crypto_boringssl.lib"),
    'NGHTTP3_LIBRARY': os.path.join(INSTALL, "nghttp3", "lib", "nghttp3.lib"),
    'ZSTD_LIBRARY': os.path.join(INSTALL, "zstd", "lib", "zstd_static.lib"),
}

print("EXISTS checks (what CMake sees):")
for name, path in checks.items():
    exists = os.path.exists(path)
    sz = os.path.getsize(path) if exists else 0
    print(f"  {'[OK]' if exists else '[MISS]'} {name}: {path} ({sz:,} bytes)")

# Now check what the CMakeCache says about OPENSSL_LIBRARIES
cache = os.path.join(BASE, "build", "curl-dll", "CMakeCache.txt")
if os.path.exists(cache):
    lines = open(cache, encoding='utf-8', errors='replace').readlines()
    for l in lines:
        if 'OPENSSL_LIBRARIES' in l and 'ADVANCED' not in l:
            print(f"\n  CMakeCache: {l.strip()}")
    
    # Check the CMake variable type - UNINITIALIZED means it was set with -D
    # but FindOpenSSL didn't find it formally
    for l in lines:
        if 'OPENSSL_FOUND' in l:
            print(f"  {l.strip()}")
        if 'OpenSSL_FOUND' in l:
            print(f"  {l.strip()}")

#!/usr/bin/env python3
"""Verify DLL actual exports using Python ctypes as fallback"""
import os, re, subprocess, sys, json

BASE = r"d:\curl-impersonate-8.20.0"
DLL_PATH = os.path.join(BASE, "output", "libcurl-impersonate.dll")
REF_DLL = r"d:\curl-impersonate-8.1.1\win_build\output\libcurl-impersonate-chrome.dll"
DEF_USED = os.path.join(BASE, "deps", "curl-8.20.0", "lib", "libcurl.def")
CONFIG_H = os.path.join(BASE, "build", "curl-dll", "lib", "curl_config.h")

def get_exports_via_dumpbin(dll_path):
    """Get DLL exports using dumpbin via cmd"""
    try:
        # Use cmd /c to run dumpbin.bat
        r = subprocess.run(
            ["cmd", "/c", "dumpbin", "/exports", dll_path],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace'
        )
        exports = []
        for line in r.stdout.split('\n'):
            m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', line)
            if m:
                exports.append(m.group(4))
        return exports, r.stdout
    except Exception as e:
        return [], str(e)

def parse_def(path):
    syms = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(';') and not line.startswith('LIBRARY') and not line.startswith('EXPORTS') and not line.startswith('#'):
                name = re.sub(r'\s*@\d+\s*$', '', line).strip()
                if name and re.match(r'^[A-Za-z_]', name):
                    syms.append(name)
    return syms

def categorize(syms):
    cats = {}
    for s in syms:
        if s.startswith('curl_') or s.startswith('CURL'):
            p = 'curl'
        elif s.startswith('nghttp2_'):
            p = 'nghttp2'
        elif s.startswith('nghttp3_'):
            p = 'nghttp3'
        elif s.startswith('ngtcp2_'):
            p = 'ngtcp2'
        elif s.startswith('brotli_') or s.startswith('Brotli'):
            p = 'brotli'
        elif s.startswith('ZSTD_'):
            p = 'zstd'
        elif s.startswith('cJSON'):
            p = 'cJSON'
        elif any(s.startswith(x) for x in ['SSL_','SSL_CTX','SSL_SESSION']):
            p = 'SSL'
        elif s.startswith('EVP_'):
            p = 'EVP'
        elif s.startswith('X509_'):
            p = 'X509'
        elif s.startswith('BIO_'):
            p = 'BIO'
        elif s.startswith('CRYPTO_'):
            p = 'CRYPTO'
        elif any(s.startswith(x) for x in ['inflate','deflate','uncompress','compress','gz','zlib','crc32','adler']):
            p = 'zlib'
        elif any(s.startswith(x) for x in ['RSA_','EC_','BN_','ERR_','OBJ_','HMAC_','AES_','ASN1','PKCS','PEM_','DH_','DSA_','ENGINE_','MD5','NID_','RAND_','OPENSSL','sk_','lh_','CBS','BUF_','CONF_','POLICY','SESS','bssl','i2d_','d2i_','BCM_','CBB_']):
            p = 'BoringSSL-other'
        elif s.startswith('Curl_') or s.startswith('Curl_'):
            p = 'curl-internal'
        elif s.startswith('??') or s.startswith('?'):
            p = 'C++-mangled'
        else:
            p = 'other'
        cats.setdefault(p, []).append(s)
    return cats

print("=" * 70)
print(" curl-impersonate-8.20.0 DLL Export Verification")
print("=" * 70)

# 1. Parse .def file used by build
def_syms = parse_def(DEF_USED)
print(f"\n[1] .def file used by build: {DEF_USED}")
print(f"    Total symbols: {len(def_syms)}")
def_cats = categorize(def_syms)
for cat, items in sorted(def_cats.items(), key=lambda x: -len(x[1])):
    print(f"    {cat:20s}: {len(items):4d}")

# 2. Get actual DLL exports
print(f"\n[2] DLL exports: {DLL_PATH}")
exports, dump_output = get_exports_via_dumpbin(DLL_PATH)
if exports:
    print(f"    Total exports: {len(exports)}")
    dll_cats = categorize(exports)
    for cat, items in sorted(dll_cats.items(), key=lambda x: -len(x[1])):
        print(f"    {cat:20s}: {len(items):4d}")
    
    # 3. Compare .def vs actual DLL
    print(f"\n[3] .def vs DLL comparison:")
    def_set = set(def_syms)
    dll_set = set(exports)
    only_in_def = def_set - dll_set
    only_in_dll = dll_set - def_set
    in_both = def_set & dll_set
    print(f"    In both: {len(in_both)}")
    print(f"    Only in .def (not exported): {len(only_in_def)}")
    print(f"    Only in DLL (not in .def): {len(only_in_dll)}")
    
    if only_in_dll:
        dll_extra_cats = categorize(list(only_in_dll))
        print(f"    Extra DLL exports by category:")
        for cat, items in sorted(dll_extra_cats.items(), key=lambda x: -len(x[1])):
            print(f"      {cat:20s}: {len(items)}")
            for s in items[:3]:
                print(f"        - {s}")
    
    if only_in_def:
        def_missing_cats = categorize(list(only_in_def))
        print(f"    Missing from DLL by category:")
        for cat, items in sorted(def_missing_cats.items(), key=lambda x: -len(x[1])):
            print(f"      {cat:20s}: {len(items)}")
            for s in items[:5]:
                print(f"        - {s}")
else:
    print(f"    Failed to get exports: {dump_output[:200]}")
    print(f"    Falling back to .def file analysis only")

# 4. Key library coverage check
print(f"\n[4] Key library export coverage:")
lib_checks = {
    'nghttp2': 'nghttp2_',
    'nghttp3': 'nghttp3_',
    'ngtcp2': 'ngtcp2_',
    'zstd': 'ZSTD_',
    'brotli': 'brotli_',
    'cJSON': 'cJSON',
    'zlib': ('inflate','deflate','uncompress','compress'),
    'BoringSSL-SSL': 'SSL_',
    'BoringSSL-EVP': 'EVP_',
}

if exports:
    check_source = exports
    source_name = "DLL exports"
else:
    check_source = def_syms
    source_name = ".def file"

print(f"    Source: {source_name}")
for lib, prefix in lib_checks.items():
    if isinstance(prefix, tuple):
        count = sum(1 for s in check_source if any(s.startswith(p) for p in prefix))
    else:
        count = sum(1 for s in check_source if s.startswith(prefix))
    status = "OK" if count > 0 else "MISSING"
    print(f"    [{status:7s}] {lib:20s}: {count} exports")

# 5. curl API completeness
print(f"\n[5] curl API completeness:")
curl_syms = [s for s in (exports if exports else def_syms) if s.startswith('curl_') or s.startswith('CURL')]

key_apis = [
    'curl_easy_init', 'curl_easy_setopt', 'curl_easy_perform',
    'curl_easy_cleanup', 'curl_easy_getinfo', 'curl_easy_reset',
    'curl_easy_duphandle', 'curl_easy_recv', 'curl_easy_send',
    'curl_easy_pause', 'curl_easy_strerror', 'curl_easy_escape',
    'curl_easy_unescape', 'curl_easy_header', 'curl_easy_nextheader',
    'curl_multi_init', 'curl_multi_add_handle', 'curl_multi_perform',
    'curl_multi_poll', 'curl_multi_wait', 'curl_multi_fdset',
    'curl_multi_info_read', 'curl_multi_remove_handle', 'curl_multi_cleanup',
    'curl_multi_strerror', 'curl_multi_socket_action', 'curl_multi_setopt',
    'curl_multi_wakeup', 'curl_share_init', 'curl_share_setopt',
    'curl_share_cleanup', 'curl_url', 'curl_url_cleanup', 'curl_url_dup',
    'curl_url_get', 'curl_url_set', 'curl_ws_recv', 'curl_ws_send',
    'curl_ws_meta', 'curl_mime_init', 'curl_mime_free', 'curl_mime_addpart',
    'curl_mime_name', 'curl_mime_data', 'curl_mime_filedata',
    'curl_mime_encoder', 'curl_version', 'curl_version_info',
    'curl_global_init', 'curl_global_cleanup', 'curl_global_sslset',
    'curl_slist_append', 'curl_slist_free_all', 'curl_getdate',
    'curl_easy_option_by_id', 'curl_easy_option_by_name',
    'curl_easy_option_next',
    # Impersonate-specific
    'curl_easy_impersonate', 'curl_easy_impersonate_customized',
    'curl_easy_impersonate_list', 'curl_easy_impersonate_register',
]

found = [a for a in key_apis if a in curl_syms]
missing = [a for a in key_apis if a not in curl_syms]
print(f"    Found: {len(found)}/{len(key_apis)}")
if missing:
    print(f"    Missing:")
    for m in missing:
        print(f"      - {m}")

# 6. Compare with 8.1.1 reference
print(f"\n[6] Compare with 8.1.1 reference:")
if os.path.exists(REF_DLL):
    ref_exports, _ = get_exports_via_dumpbin(REF_DLL)
    if ref_exports:
        print(f"    8.20.0: {len(exports)} exports")
        print(f"    8.1.1:  {len(ref_exports)} exports")
        print(f"    Diff:   {len(exports) - len(ref_exports):+d}")
        
        only_new = set(exports) - set(ref_exports)
        only_old = set(ref_exports) - set(exports)
        
        if only_new:
            new_cats = categorize(list(only_new))
            print(f"\n    8.20.0 new exports ({len(only_new)}):")
            for cat, items in sorted(new_cats.items(), key=lambda x: -len(x[1])):
                print(f"      {cat:20s}: {len(items)}")
        
        if only_old:
            old_cats = categorize(list(only_old))
            print(f"\n    8.1.1 only exports ({len(only_old)}):")
            for cat, items in sorted(old_cats.items(), key=lambda x: -len(x[1])):
                print(f"      {cat:20s}: {len(items)}")
    else:
        print(f"    Failed to get reference DLL exports")
else:
    print(f"    Reference DLL not found: {REF_DLL}")

# 7. Functional feature summary
print(f"\n[7] Functional feature summary:")
if exports:
    features = {
        'HTTP/1.1 (curl_easy_perform)': 'curl_easy_perform' in exports,
        'HTTP/2 (nghttp2)': any(s.startswith('nghttp2_') for s in exports),
        'HTTP/3 (ngtcp2+nghttp3)': any(s.startswith('ngtcp2_') for s in exports) and any(s.startswith('nghttp3_') for s in exports),
        'TLS (BoringSSL SSL_)': any(s.startswith('SSL_') for s in exports),
        'WebSocket (curl_ws_)': 'curl_ws_recv' in exports,
        'Compression-brotli': any(s.startswith('brotli_') for s in exports),
        'Compression-zstd': any(s.startswith('ZSTD_') for s in exports),
        'Compression-zlib': any(s.startswith('inflate') for s in exports),
        'Impersonate API': 'curl_easy_impersonate' in exports,
        'Multi API': 'curl_multi_poll' in exports,
        'URL API': 'curl_url_set' in exports,
        'MIME/Form': 'curl_mime_init' in exports,
        'Headers API': 'curl_easy_header' in exports,
        'Share API': 'curl_share_init' in exports,
        'Alt-Svc': any('altsvc' in s.lower() for s in exports),
        'QUIC/HTTP3 internal': any('quic' in s.lower() for s in exports),
    }
    for feat, present in features.items():
        print(f"    [{'OK' if present else 'MISSING':7s}] {feat}")
else:
    print("    Cannot verify - no DLL exports available")

print("\n" + "=" * 70)
print(" Verification Complete")
print("=" * 70)

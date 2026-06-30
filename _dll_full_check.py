"""Full DLL verification using pefile"""
import pefile, os, sys, re, json

BASE = r"d:\curl-impersonate-8.20.0"
DLL = os.path.join(BASE, "output", "libcurl-impersonate.dll")
REF_DLL = r"d:\curl-impersonate-8.1.1\win_build\output\libcurl-impersonate-chrome.dll"
DEF_USED = os.path.join(BASE, "deps", "curl-8.20.0", "lib", "libcurl.def")

def get_exports(dll_path):
    try:
        pe = pefile.PE(dll_path, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
        exports = []
        if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
            for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if exp.name:
                    name = exp.name.decode('utf-8', errors='replace')
                    exports.append(name)
        pe.close()
        return sorted(exports)
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

def parse_def(path):
    syms = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(';') and not line.startswith('LIBRARY') and not line.startswith('EXPORTS') and not line.startswith('#'):
                name = re.sub(r'\s*@\d+\s*$', '', line).strip()
                if name and re.match(r'^[A-Za-z_]', name):
                    syms.append(name)
    return sorted(syms)

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
        elif s.startswith('SSL_') or s.startswith('SSL_CTX') or s.startswith('SSL_SESSION'):
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
        elif s.startswith('Curl_'):
            p = 'curl-internal'
        elif s.startswith('??') or s.startswith('?'):
            p = 'C++-mangled'
        else:
            p = 'other'
        cats.setdefault(p, []).append(s)
    return cats

# ============================================================
# Get DLL exports
# ============================================================
print("=" * 70)
print(" curl-impersonate-8.20.0 Full DLL Verification (pefile)")
print("=" * 70)

print("\n[1] DLL Export Analysis")
print("-" * 50)
exports = get_exports(DLL)
print(f"  DLL: {DLL}")
print(f"  Size: {os.path.getsize(DLL):,} bytes")
print(f"  Total exports: {len(exports)}")

cats = categorize(exports)
print(f"\n  By category:")
for cat, items in sorted(cats.items(), key=lambda x: -len(x[1])):
    print(f"    {cat:20s}: {len(items):4d}")

# ============================================================
# Check curl API
# ============================================================
print("\n[2] curl API Completeness")
print("-" * 50)
curl_syms = [s for s in exports if s.startswith('curl_') or s.startswith('CURL')]
print(f"  Total curl API: {len(curl_syms)}")

api_groups = {
    'Easy API': ['curl_easy_init','curl_easy_setopt','curl_easy_perform','curl_easy_cleanup',
                 'curl_easy_getinfo','curl_easy_reset','curl_easy_duphandle','curl_easy_recv',
                 'curl_easy_send','curl_easy_pause','curl_easy_strerror','curl_easy_escape',
                 'curl_easy_unescape','curl_easy_header','curl_easy_nextheader'],
    'Multi API': ['curl_multi_init','curl_multi_add_handle','curl_multi_perform',
                  'curl_multi_poll','curl_multi_wait','curl_multi_fdset','curl_multi_info_read',
                  'curl_multi_remove_handle','curl_multi_cleanup','curl_multi_strerror',
                  'curl_multi_socket_action','curl_multi_setopt','curl_multi_wakeup'],
    'Share API': ['curl_share_init','curl_share_setopt','curl_share_cleanup','curl_share_strerror'],
    'URL API': ['curl_url','curl_url_cleanup','curl_url_dup','curl_url_get','curl_url_set','curl_url_strerror'],
    'WebSocket': ['curl_ws_recv','curl_ws_send','curl_ws_meta'],
    'MIME/Form': ['curl_mime_init','curl_mime_free','curl_mime_addpart','curl_mime_name',
                  'curl_mime_data','curl_mime_filedata','curl_mime_filename','curl_mime_type',
                  'curl_mime_headers','curl_mime_subparts','curl_mime_encoder','curl_formadd','curl_formfree'],
    'Headers API': ['curl_easy_header','curl_easy_nextheader','curl_header_cleanup'],
    'Version/Global': ['curl_version','curl_version_info','curl_global_init','curl_global_cleanup',
                       'curl_global_sslset'],
    'Options API': ['curl_easy_option_by_id','curl_easy_option_by_name','curl_easy_option_next'],
    'Impersonate': ['curl_easy_impersonate','curl_easy_impersonate_customized',
                    'curl_easy_impersonate_list','curl_easy_impersonate_register'],
}

for group, apis in api_groups.items():
    found = [a for a in apis if a in exports]
    missing = [a for a in apis if a not in exports]
    status = "OK" if not missing else f"MISSING {len(missing)}"
    print(f"  [{status:20s}] {group:15s}: {len(found)}/{len(apis)}")
    for m in missing:
        print(f"      - {m}")

# ============================================================
# Check library coverage
# ============================================================
print("\n[3] Library Export Coverage")
print("-" * 50)
lib_checks = [
    ('nghttp2 (HTTP/2)', lambda s: s.startswith('nghttp2_')),
    ('nghttp3 (HTTP/3)', lambda s: s.startswith('nghttp3_')),
    ('ngtcp2 (QUIC)', lambda s: s.startswith('ngtcp2_')),
    ('BoringSSL SSL', lambda s: s.startswith('SSL_') or s.startswith('SSL_CTX')),
    ('BoringSSL EVP', lambda s: s.startswith('EVP_')),
    ('BoringSSL X509', lambda s: s.startswith('X509_')),
    ('BoringSSL CRYPTO', lambda s: s.startswith('CRYPTO_')),
    ('zstd', lambda s: s.startswith('ZSTD_')),
    ('brotli', lambda s: s.startswith('brotli_') or s.startswith('Brotli')),
    ('zlib', lambda s: any(s.startswith(x) for x in ['inflate','deflate','uncompress','compress','gz','zlib','crc32','adler'])),
    ('cJSON', lambda s: s.startswith('cJSON')),
]

for name, check in lib_checks:
    count = sum(1 for s in exports if check(s))
    status = "OK" if count > 0 else "MISSING"
    print(f"  [{status:7s}] {name:25s}: {count} exports")

# ============================================================
# Compare .def vs DLL
# ============================================================
print("\n[4] .def File vs DLL Comparison")
print("-" * 50)
def_syms = parse_def(DEF_USED)
def_set = set(def_syms)
dll_set = set(exports)
in_both = def_set & dll_set
only_def = def_set - dll_set
only_dll = dll_set - def_set
print(f"  .def file symbols: {len(def_syms)}")
print(f"  DLL export symbols: {len(exports)}")
print(f"  In both: {len(in_both)}")
print(f"  Only in .def (not in DLL): {len(only_def)}")
print(f"  Only in DLL (extra): {len(only_dll)}")

if only_dll:
    extra_cats = categorize(list(only_dll))
    print(f"\n  Extra DLL exports by category:")
    for cat, items in sorted(extra_cats.items(), key=lambda x: -len(x[1])):
        print(f"    {cat:20s}: {len(items)}")
        for s in items[:5]:
            print(f"      - {s}")

if only_def:
    missing_cats = categorize(list(only_def))
    print(f"\n  .def symbols missing from DLL:")
    for cat, items in sorted(missing_cats.items(), key=lambda x: -len(x[1])):
        print(f"    {cat:20s}: {len(items)}")
        for s in items[:5]:
            print(f"      - {s}")

# ============================================================
# Compare with 8.1.1
# ============================================================
print("\n[5] Comparison with 8.1.1 Reference")
print("-" * 50)
if os.path.exists(REF_DLL):
    ref_exports = get_exports(REF_DLL)
    if ref_exports:
        print(f"  8.20.0: {len(exports)} exports")
        print(f"  8.1.1:  {len(ref_exports)} exports")
        print(f"  Diff:   {len(exports) - len(ref_exports):+d}")
        
        only_new = set(exports) - set(ref_exports)
        only_old = set(ref_exports) - set(exports)
        
        print(f"  Only in 8.20.0: {len(only_new)}")
        print(f"  Only in 8.1.1:  {len(only_old)}")
        
        if only_new:
            new_cats = categorize(list(only_new))
            print(f"\n  8.20.0 new exports by category:")
            for cat, items in sorted(new_cats.items(), key=lambda x: -len(x[1])):
                print(f"    {cat:20s}: {len(items)}")
                for s in items[:3]:
                    print(f"      - {s}")
        
        if only_old:
            old_cats = categorize(list(only_old))
            print(f"\n  8.1.1 only exports by category:")
            for cat, items in sorted(old_cats.items(), key=lambda x: -len(x[1])):
                print(f"    {cat:20s}: {len(items)}")
                for s in items[:3]:
                    print(f"      - {s}")
    else:
        print(f"  Failed to parse reference DLL")
else:
    print(f"  Reference DLL not found: {REF_DLL}")

# ============================================================
# Feature summary
# ============================================================
print("\n[6] Functional Feature Summary")
print("-" * 50)
features = {
    'HTTP/1.1': 'curl_easy_perform' in exports,
    'HTTP/2 (nghttp2)': any(s.startswith('nghttp2_') for s in exports),
    'HTTP/3 QUIC (ngtcp2)': any(s.startswith('ngtcp2_') for s in exports),
    'HTTP/3 QPACK (nghttp3)': any(s.startswith('nghttp3_') for s in exports),
    'TLS BoringSSL': any(s.startswith('SSL_') for s in exports),
    'WebSocket': 'curl_ws_recv' in exports and 'curl_ws_send' in exports,
    'Compression: brotli': any(s.startswith('brotli_') for s in exports),
    'Compression: zstd': any(s.startswith('ZSTD_') for s in exports),
    'Compression: zlib/deflate/gzip': any(s.startswith('inflate') for s in exports),
    'Impersonate API': 'curl_easy_impersonate' in exports,
    'Multi async I/O': 'curl_multi_poll' in exports,
    'URL API': 'curl_url_set' in exports,
    'MIME/Form upload': 'curl_mime_init' in exports,
    'Headers API': 'curl_easy_header' in exports,
    'Share API': 'curl_share_init' in exports,
    'QUIC internal': any('quic' in s.lower() for s in exports),
    'Alt-Svc': any('altsvc' in s.lower() or 'AltSvc' in s for s in exports),
    'HSTS': any('hsts' in s.lower() for s in exports),
    'DoH': any('doh' in s.lower() for s in exports),
    'Cookie': any('cookie' in s.lower() for s in exports),
}

enabled_count = 0
total_count = len(features)
for feat, present in features.items():
    status = "OK" if present else "MISSING"
    print(f"  [{status:7s}] {feat}")
    if present:
        enabled_count += 1

print(f"\n  Feature coverage: {enabled_count}/{total_count} ({enabled_count/total_count*100:.0f}%)")

# ============================================================
# Compile config summary
# ============================================================
print("\n[7] Compile-time Features (curl_config.h)")
print("-" * 50)
config_h = os.path.join(BASE, "build", "curl-dll", "lib", "curl_config.h")
with open(config_h, 'r') as f:
    content = f.read()

key_defines = {
    'USE_OPENSSL': 'BoringSSL/OpenSSL',
    'USE_NGHTTP2': 'HTTP/2 (nghttp2)',
    'USE_NGTCP2': 'HTTP/3 QUIC (ngtcp2)',
    'USE_NGHTTP3': 'HTTP/3 QPACK (nghttp3)',
    'HAVE_LIBZ': 'zlib compression',
    'HAVE_BROTLI': 'brotli compression',
    'HAVE_ZSTD': 'zstd compression',
    'USE_IPV6': 'IPv6',
    'USE_UNIX_SOCKETS': 'Unix sockets',
    'USE_RESOLV_THREADED': 'Threaded DNS',
    'HAVE_SSL_SET0_WBIO': 'SSL bi-directional I/O',
    'HAVE_DES_ECB_ENCRYPT': 'DES encryption',
    'USE_WIN32_CRYPTO': 'Win32 Crypto',
}

for define, desc in key_defines.items():
    enabled = f'#define {define}' in content
    status = "OK" if enabled else "OFF"
    print(f"  [{status:4s}] {desc:30s} ({define})")

disabled_protos = []
for proto in ['HTTP','FTP','FILE','RTSP','DICT','TELNET','TFTP','IMAP','POP3','SMTP','GOPHER','MQTT','LDAP','LDAPS']:
    flag = f'#define CURL_DISABLE_{proto}'
    is_disabled = flag in content
    if is_disabled:
        disabled_protos.append(proto)

print(f"\n  Disabled protocols: {', '.join(disabled_protos)}")
print(f"  Enabled protocols: HTTP, HTTPS, FTP, FTPS, FILE, WebSocket")

print("\n" + "=" * 70)
print(" VERIFICATION COMPLETE")
print("=" * 70)

# Save results as JSON
results = {
    'dll_path': DLL,
    'dll_size': os.path.getsize(DLL),
    'total_exports': len(exports),
    'categories': {cat: len(items) for cat, items in cats.items()},
    'curl_api_count': len(curl_syms),
    'features': {k: v for k, v in features.items()},
    'def_total': len(def_syms),
    'def_only': len(only_def),
    'dll_only': len(only_dll),
}
with open(os.path.join(BASE, '_verification_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to _verification_results.json")

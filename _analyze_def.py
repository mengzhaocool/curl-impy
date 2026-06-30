#!/usr/bin/env python3
"""Analyze DLL exports from .def file + DLL via Python"""
import os, re, sys

BASE = r"d:\curl-impersonate-8.20.0"
DEF_FILE = os.path.join(BASE, "output", "libcurl-impersonate_full.def")
REF_DLL = r"d:\curl-impersonate-8.1.1\win_build\output\libcurl-impersonate-chrome.dll"

# Parse .def file
def parse_def(path):
    syms = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith(';') and not line.startswith('LIBRARY') and not line.startswith('EXPORTS') and not line.startswith('#'):
                # Remove ordinal decoration like @123
                name = re.sub(r'\s*@\d+\s*$', '', line).strip()
                if name and re.match(r'^[A-Za-z_]', name):
                    syms.append(name)
    return syms

syms = parse_def(DEF_FILE)
print(f"DEF file symbols: {len(syms)}")

# Categorize
cats = {}
for s in syms:
    if s.startswith('curl_') or s.startswith('CURL'):
        prefix = 'curl'
    elif s.startswith('nghttp2_'):
        prefix = 'nghttp2'
    elif s.startswith('nghttp3_'):
        prefix = 'nghttp3'
    elif s.startswith('ngtcp2_'):
        prefix = 'ngtcp2'
    elif s.startswith('brotli_') or s.startswith('Brotli'):
        prefix = 'brotli'
    elif s.startswith('ZSTD_'):
        prefix = 'zstd'
    elif s.startswith('cJSON') or s.startswith('cJSON_'):
        prefix = 'cJSON'
    elif s.startswith('SSL_') or s.startswith('SSL_CTX') or s.startswith('SSL_SESSION'):
        prefix = 'SSL (BoringSSL)'
    elif s.startswith('EVP_'):
        prefix = 'EVP (BoringSSL)'
    elif s.startswith('X509_'):
        prefix = 'X509 (BoringSSL)'
    elif s.startswith('BIO_'):
        prefix = 'BIO (BoringSSL)'
    elif s.startswith('CRYPTO_'):
        prefix = 'CRYPTO (BoringSSL)'
    elif s.startswith('RSA_'):
        prefix = 'RSA (BoringSSL)'
    elif s.startswith('EC_'):
        prefix = 'EC (BoringSSL)'
    elif s.startswith('BN_'):
        prefix = 'BN (BoringSSL)'
    elif s.startswith('ERR_'):
        prefix = 'ERR (BoringSSL)'
    elif s.startswith('OBJ_'):
        prefix = 'OBJ (BoringSSL)'
    elif s.startswith('HMAC_'):
        prefix = 'HMAC (BoringSSL)'
    elif s.startswith('SHA') and len(s) > 3:
        prefix = 'SHA (BoringSSL)'
    elif s.startswith('AES_'):
        prefix = 'AES (BoringSSL)'
    elif s.startswith('ASN1') or s.startswith('PKCS') or s.startswith('PEM_') or s.startswith('DH_') or s.startswith('DSA_') or s.startswith('ENGINE_') or s.startswith('MD5') or s.startswith('NID_') or s.startswith('RAND_') or s.startswith('OPENSSL') or s.startswith('sk_') or s.startswith('lh_') or s.startswith('CBS') or s.startswith('BUF_') or s.startswith('CONF_') or s.startswith('POLICY') or s.startswith('SESS') or s.startswith('bssl'):
        prefix = 'Other BoringSSL'
    elif s.startswith('inflate') or s.startswith('deflate') or s.startswith('uncompress') or s.startswith('compress') or s.startswith('gz') or s.startswith('zlib') or s.startswith('crc32') or s.startswith('adler'):
        prefix = 'zlib'
    else:
        prefix = 'other'
    cats.setdefault(prefix, []).append(s)

print("\n=== Export categories ===")
for cat, items in sorted(cats.items(), key=lambda x: -len(x[1])):
    print(f"  {cat:25s}: {len(items):4d} symbols")

# Key API checks
print("\n=== Key curl API check ===")
curl_syms = [s for s in syms if s.startswith('curl_') or s.startswith('CURL')]

key_apis = {
    'Easy': ['curl_easy_init','curl_easy_setopt','curl_easy_perform','curl_easy_cleanup',
             'curl_easy_getinfo','curl_easy_reset','curl_easy_duphandle','curl_easy_recv',
             'curl_easy_send','curl_easy_pause','curl_easy_strerror','curl_easy_escape',
             'curl_easy_unescape','curl_easy_header'],
    'Multi': ['curl_multi_init','curl_multi_add_handle','curl_multi_perform',
              'curl_multi_poll','curl_multi_wait','curl_multi_fdset','curl_multi_info_read',
              'curl_multi_remove_handle','curl_multi_cleanup','curl_multi_strerror',
              'curl_multi_socket','curl_multi_socket_action','curl_multi_setopt',
              'curl_multi_wakeup'],
    'Share': ['curl_share_init','curl_share_setopt','curl_share_cleanup','curl_share_strerror'],
    'URL': ['curl_url','curl_url_cleanup','curl_url_dup','curl_url_get','curl_url_set','curl_url_strerror'],
    'WebSocket': ['curl_ws_recv','curl_ws_send','curl_ws_meta'],
    'Header': ['curl_easy_header','curl_easy_nextheader','curl_header_cleanup'],
    'MIME/Form': ['curl_mime_init','curl_mime_free','curl_mime_addpart','curl_mime_name',
                  'curl_mime_data','curl_mime_filedata','curl_mime_filename','curl_mime_type',
                  'curl_mime_headers','curl_mime_subparts','curl_mime_encoder',
                  'curl_mime_data_cb','curl_mime_file_cb','curl_formadd','curl_formfree'],
    'Version': ['curl_version','curl_version_info'],
    'Global': ['curl_global_init','curl_global_cleanup','curl_global_sslset'],
    'Options': ['curl_easy_option_by_id','curl_easy_option_by_name','curl_easy_option_next'],
}

for cat, apis in key_apis.items():
    found = [a for a in apis if a in curl_syms]
    missing = [a for a in apis if a not in curl_syms]
    status = "OK" if not missing else "MISSING"
    print(f"  [{status:7s}] {cat:15s}: {len(found)}/{len(apis)}")
    for m in missing:
        print(f"           - MISSING: {m}")

# Library API checks
print("\n=== Library API check ===")
for lib_name, prefix in [('nghttp2','nghttp2_'), ('nghttp3','nghttp3_'), ('ngtcp2','ngtcp2_'), ('zstd','ZSTD_'), ('brotli','brotli_'), ('cJSON','cJSON')]:
    lib_syms = [s for s in syms if s.startswith(prefix)]
    print(f"  {lib_name:15s}: {len(lib_syms)} exports")

# Impersonate-specific
print("\n=== Impersonate-specific ===")
imp_syms = [s for s in syms if 'impersonate' in s.lower()]
print(f"  impersonate exports: {len(imp_syms)}")
for s in imp_syms[:20]:
    print(f"    {s}")

# SSL symbols count
print("\n=== BoringSSL coverage ===")
boringssl_cats = [k for k in cats if 'BoringSSL' in k or k in ['SSL (BoringSSL)','EVP (BoringSSL)','X509 (BoringSSL)','BIO (BoringSSL)','CRYPTO (BoringSSL)','RSA (BoringSSL)','EC (BoringSSL)','BN (BoringSSL)','ERR (BoringSSL)','OBJ (BoringSSL)','HMAC (BoringSSL)','SHA (BoringSSL)','AES (BoringSSL)']]
total_boringssl = sum(len(cats[k]) for k in boringssl_cats)
print(f"  Total BoringSSL exports: {total_boringssl}")
for k in boringssl_cats:
    print(f"    {k}: {len(cats[k])}")

# zlib coverage
zlib_syms = cats.get('zlib', [])
print(f"\n  zlib exports: {len(zlib_syms)}")

# Key features check (functional)
print("\n=== Critical features functional check ===")
# These are essential for curl-impersonate
critical = {
    'curl_easy_setopt': 'Easy API setup',
    'curl_easy_perform': 'Easy API execution',
    'curl_easy_getinfo': 'Get response info',
    'curl_multi_poll': 'Multi async I/O',
    'curl_ws_recv': 'WebSocket receive',
    'curl_ws_send': 'WebSocket send',
    'curl_url_set': 'URL parsing',
    'curl_mime_init': 'MIME/form upload',
    'curl_easy_header': 'Headers API',
    'curl_version_info': 'Version info',
}
for sym, desc in critical.items():
    present = sym in syms
    print(f"  [{'OK' if present else 'MISSING':7s}] {sym:25s} - {desc}")

# Check HTTP/3 key functions
print("\n=== HTTP/3 support chain ===")
h3_syms = [s for s in syms if 'quic' in s.lower() or 'h3' in s.lower() or s.startswith('ngtcp2_') or s.startswith('nghttp3_')]
print(f"  HTTP/3 related exports: {len(h3_syms)}")
for s in sorted(h3_syms)[:30]:
    print(f"    {s}")

# Summary
print("\n=== SUMMARY ===")
print(f"  Total exports in .def: {len(syms)}")
print(f"  curl API: {len(curl_syms)}")
print(f"  BoringSSL: {total_boringssl}")
print(f"  nghttp2: {len(cats.get('nghttp2',[]))}")
print(f"  nghttp3: {len(cats.get('nghttp3',[]))}")
print(f"  ngtcp2: {len(cats.get('ngtcp2',[]))}")
print(f"  brotli: {len(cats.get('brotli',[]))}")
print(f"  zstd: {len(cats.get('zstd',[]))}")
print(f"  zlib: {len(cats.get('zlib',[]))}")
print(f"  cJSON: {len(cats.get('cJSON',[]))}")

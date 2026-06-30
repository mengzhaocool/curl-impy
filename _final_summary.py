#!/usr/bin/env python3
"""Final DLL summary"""
import subprocess, sys, os, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
cur_dll = r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate.dll'

r = subprocess.run([DUMPBIN, '/exports', cur_dll], capture_output=True, encoding='utf-8', errors='replace')
exports = set()
for l in r.stdout.split('\n'):
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
    if m:
        exports.add(m.group(4))

# Dependents
r2 = subprocess.run([DUMPBIN, '/dependents', cur_dll], capture_output=True, encoding='utf-8', errors='replace')

print("=" * 70)
print("FINAL DLL EXPORT SUMMARY - libcurl-impersonate.dll (8.20.0)")
print("=" * 70)
print(f"DLL size: {os.path.getsize(cur_dll):,} bytes ({os.path.getsize(cur_dll)/1024/1024:.1f} MB)")
print(f"Total exports: {len(exports)}")
print(f"Static lib: {os.path.getsize(r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate.lib'):,} bytes")
print(f"Import lib: {os.path.getsize(r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate_imp.lib'):,} bytes")
print()

# Group counts
def count(pred):
    return len([e for e in exports if pred(e)])

groups = [
    ("libcurl (curl_* + impersonate)", lambda e: e.startswith('curl_') or 'impersonate' in e),
    ("BoringSSL libssl (SSL_*)", lambda e: e.startswith('SSL_') or e.startswith('SSL_CTX_') or e.startswith('SSL_SESSION_')),
    ("BoringSSL libcrypto", lambda e: any(e.startswith(p) for p in [
        'EVP_','BIO_','X509_','RSA_','BN_','EC_','ECDH_','ECDSA_','ASN1_','PEM_',
        'OBJ_','ERR_','CRYPTO_','HMAC_','AES_','OPENSSL_','RAND_','ENGINE_','PKCS',
        'OCSP_','CMS_','DH_','DSA_','SHA','CBS_','CBB_','GENERAL_','DES_','i2d_','d2i_',
        'kBoringSSL','AUTHORITY_','BASIC_','DIST_POINT','ISSUER','NAME','NID','NOTICERE',
        'POLICY','PROXY','PKEY','SCT','SPKI','TS_','UI_','X509V3'])),
    ("brotli (BrotliDecoder* + BrotliEncoder*)", lambda e: e.startswith('Brotli')),
    ("zlib (deflate/inflate/compress/crc32/gz)", lambda e: any(e.startswith(p) for p in [
        'deflate','inflate','compress','uncompress','crc32','adler32','gz','zlib','z_'])),
    ("nghttp2 (HTTP/2)", lambda e: e.startswith('nghttp2_')),
    ("nghttp3 (HTTP/3)", lambda e: e.startswith('nghttp3_')),
    ("ngtcp2 (QUIC)", lambda e: e.startswith('ngtcp2_')),
    ("zstd (compression)", lambda e: e.startswith('ZSTD_')),
    ("cJSON (JSON)", lambda e: e.startswith('cJSON')),
]

total = 0
for name, pred in groups:
    c = count(pred)
    total += c
    print(f"  {name:50s}: {c:5d}")

other = len(exports) - total
print(f"  {'other':50s}: {other:5d}")

print()
print("DLL dependencies (system DLLs only):")
for l in r2.stdout.split('\n'):
    if '.dll' in l.lower() or '.DLL' in l:
        print(f"  {l.strip()}")

print()
print("Comparison with 8.1.1:")
ref_dll = r'd:\curl-impersonate-8.1.1\win_build\output\libcurl-impersonate-chrome.dll'
if os.path.exists(ref_dll):
    r3 = subprocess.run([DUMPBIN, '/exports', ref_dll], capture_output=True, encoding='utf-8', errors='replace')
    ref_exports = set()
    for l in r3.stdout.split('\n'):
        m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
        if m:
            ref_exports.add(m.group(4))
    
    only_in_811 = ref_exports - exports
    only_in_820 = exports - ref_exports
    
    print(f"  8.1.1:  {len(ref_exports):5d} exports, {os.path.getsize(ref_dll)/1024/1024:.1f} MB")
    print(f"  8.20.0: {len(exports):5d} exports, {os.path.getsize(cur_dll)/1024/1024:.1f} MB")
    print(f"  Only in 8.1.1 (removed/changed): {len(only_in_811)}")
    print(f"  Only in 8.20.0 (new): {len(only_in_820)}")
    print(f"  Net change: +{len(exports) - len(ref_exports)}")
else:
    print("  Reference 8.1.1 DLL not found for comparison")

# Verify important APIs
print()
print("Important API verification:")
important = [
    'curl_easy_init', 'curl_easy_setopt', 'curl_easy_perform', 'curl_easy_cleanup',
    'curl_easy_impersonate', 'curl_easy_impersonate_register',
    'SSL_CTX_new', 'SSL_new', 'SSL_connect', 'SSL_read', 'SSL_write',
    'SSL_CTX_set_cipher_list', 'SSL_CTX_set_alpn_protos',
    'EVP_EncryptInit_ex', 'EVP_DecryptInit_ex', 'EVP_DigestInit_ex',
    'BIO_new', 'BIO_read', 'BIO_write',
    'X509_free', 'PEM_read_X509',
    'BrotliDecoderDecompress', 'BrotliEncoderCompress',
    'deflate', 'inflate', 'compress', 'crc32', 'zlibVersion',
    'nghttp2_session_client_new', 'nghttp2_submit_request',
    'nghttp3_conn_new', 'ngtcp2_conn_new',
    'ZSTD_compress', 'ZSTD_decompress',
    'cJSON_Parse', 'cJSON_Delete',
]
all_ok = True
for sym in important:
    found = sym in exports
    if not found:
        # Check similar names
        similar = [e for e in exports if sym.split('_')[0] in e][:3]
        status = f"MISSING (similar: {similar})"
        all_ok = False
    else:
        status = "OK"
    # Only print failures
    if not found:
        print(f"  {sym}: {status}")
if all_ok:
    print("  All important APIs found!")

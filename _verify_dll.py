#!/usr/bin/env python3
"""Verify new DLL exports"""
import subprocess, sys, os, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
BASE = r'd:\curl-impersonate-8.20.0'

dll_path = os.path.join(BASE, 'output', 'libcurl-impersonate.dll')
print(f"DLL size: {os.path.getsize(dll_path):,} bytes ({os.path.getsize(dll_path)/1024/1024:.1f} MB)")

r = subprocess.run([DUMPBIN, '/exports', dll_path], capture_output=True, encoding='utf-8', errors='replace')
exports = []
for l in r.stdout.split('\n'):
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
    if m:
        exports.append(m.group(4))

print(f"Total exports: {len(exports)}")
print()

# Count by prefix
def count_prefix(prefix):
    return len([e for e in exports if e.startswith(prefix)])

print("=" * 60)
print("EXPORT COUNTS BY LIBRARY")
print("=" * 60)

curl_count = count_prefix('curl_')
imp_count = len([e for e in exports if 'impersonate' in e])
ssl_count = count_prefix('SSL_') + count_prefix('SSL_CTX_') + count_prefix('SSL_SESSION_')
crypto_prefixes = ['EVP_', 'BIO_', 'X509_', 'RSA_', 'BN_', 'EC_', 'ECDH_', 'ECDSA_',
                   'ASN1_', 'PEM_', 'OBJ_', 'ERR_', 'CRYPTO_', 'HMAC_', 'AES_',
                   'OPENSSL_', 'RAND_', 'ENGINE_', 'PKCS', 'OCSP_', 'CMS_', 'DH_', 'DSA_']
crypto_count = sum(count_prefix(p) for p in crypto_prefixes)
# Also SHA which doesn't have underscore
sha_count = len([e for e in exports if e.startswith('SHA') and e[3:4] in ['_', '1', '2', '3', '0', '2']])
crypto_count += sha_count

brotli_count = count_prefix('BrotliDecoder') + count_prefix('BrotliEncoder')
zlib_count = count_prefix('deflate') + count_prefix('inflate') + count_prefix('compress') + count_prefix('uncompress') + count_prefix('crc32') + count_prefix('adler32') + count_prefix('gz') + count_prefix('zlib') + count_prefix('z_')
nghttp2_count = count_prefix('nghttp2_')
nghttp3_count = count_prefix('nghttp3_')
ngtcp2_count = count_prefix('ngtcp2_')
zstd_count = count_prefix('ZSTD_')
cjson_count = count_prefix('cJSON')

print(f"  libcurl:             {curl_count + imp_count} (curl:{curl_count} + impersonate:{imp_count})")
print(f"  BoringSSL libssl:    {ssl_count}")
print(f"  BoringSSL libcrypto: {crypto_count}")
print(f"  brotli:              {brotli_count}")
print(f"  zlib:                {zlib_count}")
print(f"  nghttp2:             {nghttp2_count}")
print(f"  nghttp3:             {nghttp3_count}")
print(f"  ngtcp2:              {ngtcp2_count}")
print(f"  zstd:                {zstd_count}")
print(f"  cJSON:               {cjson_count}")
print()

# Detail for crypto
print("--- Crypto detail ---")
for p in crypto_prefixes:
    c = count_prefix(p)
    if c > 0:
        print(f"  {p}: {c}")
sha_count_detail = len([e for e in exports if e.startswith('SHA')])
if sha_count_detail:
    print(f"  SHA*: {sha_count_detail}")

# Verify DLL still works
print()
print("=" * 60)
print("FUNCTIONAL TEST")
print("=" * 60)

# Check specific important symbols
important = [
    'curl_easy_init', 'curl_easy_setopt', 'curl_easy_perform', 'curl_easy_cleanup',
    'curl_easy_impersonate', 'curl_easy_impersonate_register',
    'SSL_CTX_new', 'SSL_new', 'SSL_connect', 'SSL_read', 'SSL_write',
    'EVP_EncryptInit_ex', 'EVP_DecryptInit_ex', 'EVP_DigestInit_ex',
    'BIO_new', 'BIO_read', 'BIO_write',
    'X509_free', 'X509_new',
    'BrotliDecoderDecompress', 'BrotliEncoderCompress',
    'deflate', 'inflate', 'compress', 'crc32',
    'nghttp2_session_new', 'nghttp2_submit_request',
    'nghttp3_conn_new',
    'ngtcp2_conn_new',
    'ZSTD_compress', 'ZSTD_decompress',
    'cJSON_Parse',
]

missing_important = []
for sym in important:
    if sym not in exports:
        missing_important.append(sym)

if missing_important:
    print(f"MISSING important symbols: {missing_important}")
else:
    print("All important symbols found!")

# Test with the test exe
print()
print("Testing with test_xweb_fingerprint.exe...")
import shutil
shutil.copy2(dll_path, os.path.join(BASE, 'libcurl-impersonate.dll'))

#!/usr/bin/env python3
"""Complete DLL export statistics"""
import subprocess, sys, os, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
BASE = r'd:\curl-impersonate-8.20.0'

# Get DLL exports
r = subprocess.run([DUMPBIN, '/exports', os.path.join(BASE, 'output', 'libcurl-impersonate.dll')], 
                   capture_output=True, encoding='utf-8', errors='replace')

exports = []
for l in r.stdout.split('\n'):
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
    if m:
        exports.append(m.group(4))

print(f"Total DLL exports: {len(exports)}")
print(f"DLL size: {os.path.getsize(os.path.join(BASE, 'output', 'libcurl-impersonate.dll')):,} bytes")
print()

# Detailed categorization
categories = {
    'curl_easy_*': [],
    'curl_multi_*': [],
    'curl_url_*': [],
    'curl_share_*': [],
    'curl_global_*': [],
    'curl_version*': [],
    'curl_slist*': [],
    'curl_form*': [],
    'curl_mime*': [],
    'curl_ws_*': [],
    'curl_impersonate': [],
    'curl_ (other)': [],
    'SSL_*': [],
    'SSL_CTX_*': [],
    'SSL_SESSION_*': [],
    'EVP_*': [],
    'BIO_*': [],
    'X509_*': [],
    'RSA_*': [],
    'BN_*': [],
    'DH_*': [],
    'DSA_*': [],
    'EC_*': [],
    'ECDH_*': [],
    'ECDSA_*': [],
    'ASN1_*': [],
    'PEM_*': [],
    'OBJ_*': [],
    'ERR_*': [],
    'CRYPTO_*': [],
    'HMAC_*': [],
    'SHA*': [],
    'AES_*': [],
    'OPENSSL_*': [],
    'RAND_*': [],
    'ENGINE_*': [],
    'PKCS*': [],
    'OCSP_*': [],
    'CMS_*': [],
    'BrotliDecoder*': [],
    'BrotliEncoder*': [],
    'Brotli* (other)': [],
    'deflate*': [],
    'inflate*': [],
    'compress*': [],
    'uncompress*': [],
    'crc32*': [],
    'adler32*': [],
    'gz*': [],
    'z_*': [],
    'zlib*': [],
    'nghttp2_*': [],
    'nghttp3_*': [],
    'ngtcp2_*': [],
    'other': [],
}

for name in exports:
    matched = False
    for prefix in sorted(categories.keys(), key=len, reverse=True):
        if prefix.endswith('*'):
            actual_prefix = prefix[:-1]
            if name.startswith(actual_prefix):
                categories[prefix].append(name)
                matched = True
                break
        elif prefix.endswith(' (other)'):
            continue
        elif name.startswith(prefix):
            categories[prefix].append(name)
            matched = True
            break
    if not matched:
        categories['other'].append(name)

# Print summary
print("=" * 60)
print("DLL EXPORT SUMMARY BY CATEGORY")
print("=" * 60)

# Group by library
print("\n--- libcurl ---")
curl_total = 0
for k in ['curl_easy_*', 'curl_multi_*', 'curl_url_*', 'curl_share_*', 'curl_global_*',
          'curl_version*', 'curl_slist*', 'curl_form*', 'curl_mime*', 'curl_ws_*',
          'curl_impersonate', 'curl_ (other)']:
    if categories[k]:
        print(f"  {k}: {len(categories[k])}")
        curl_total += len(categories[k])
print(f"  TOTAL curl: {curl_total}")

print("\n--- BoringSSL libssl ---")
ssl_total = 0
for k in ['SSL_*', 'SSL_CTX_*', 'SSL_SESSION_*']:
    if categories[k]:
        print(f"  {k}: {len(categories[k])}")
        ssl_total += len(categories[k])
print(f"  TOTAL SSL: {ssl_total}")

print("\n--- BoringSSL libcrypto ---")
crypto_total = 0
for k in ['EVP_*', 'BIO_*', 'X509_*', 'RSA_*', 'BN_*', 'DH_*', 'DSA_*', 'EC_*', 'ECDH_*',
          'ECDSA_*', 'ASN1_*', 'PEM_*', 'OBJ_*', 'ERR_*', 'CRYPTO_*', 'HMAC_*', 'SHA*',
          'AES_*', 'OPENSSL_*', 'RAND_*', 'ENGINE_*', 'PKCS*', 'OCSP_*', 'CMS_*']:
    if categories[k]:
        print(f"  {k}: {len(categories[k])}")
        crypto_total += len(categories[k])
print(f"  TOTAL crypto: {crypto_total}")

print("\n--- brotli ---")
brotli_total = 0
for k in ['BrotliDecoder*', 'BrotliEncoder*', 'Brotli* (other)']:
    if categories[k]:
        print(f"  {k}: {len(categories[k])}")
        brotli_total += len(categories[k])
print(f"  TOTAL brotli: {brotli_total}")

print("\n--- zlib ---")
zlib_total = 0
for k in ['deflate*', 'inflate*', 'compress*', 'uncompress*', 'crc32*', 'adler32*', 'gz*', 'z_*', 'zlib*']:
    if categories[k]:
        print(f"  {k}: {len(categories[k])}")
        zlib_total += len(categories[k])
print(f"  TOTAL zlib: {zlib_total}")

print("\n--- nghttp2 ---")
print(f"  nghttp2_*: {len(categories['nghttp2_*'])}")
print(f"\n--- nghttp3 ---")
print(f"  nghttp3_*: {len(categories['nghttp3_*'])}")
print(f"\n--- ngtcp2 ---")
print(f"  ngtcp2_*: {len(categories['ngtcp2_*'])}")

print(f"\n--- other ---")
print(f"  other: {len(categories['other'])}")
if categories['other']:
    for s in sorted(categories['other'])[:20]:
        print(f"    {s}")
    if len(categories['other']) > 20:
        print(f"    ... and {len(categories['other'])-20} more")

# Compare with reference 8.1.1 if available
ref_dll = r'd:\curl-impersonate-8.1.1\output\libcurl-impersonate.dll'
if os.path.exists(ref_dll):
    print("\n" + "=" * 60)
    print("COMPARISON WITH REFERENCE 8.1.1 DLL")
    print("=" * 60)
    r2 = subprocess.run([DUMPBIN, '/exports', ref_dll], capture_output=True, encoding='utf-8', errors='replace')
    ref_exports = set()
    for l in r2.stdout.split('\n'):
        m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
        if m:
            ref_exports.add(m.group(4))
    
    print(f"Reference DLL exports: {len(ref_exports)}")
    print(f"Current DLL exports: {len(set(exports))}")
    
    only_in_ref = ref_exports - set(exports)
    only_in_cur = set(exports) - ref_exports
    print(f"Only in reference: {len(only_in_ref)}")
    print(f"Only in current: {len(only_in_cur)}")
    
    if only_in_ref:
        print("\n  Missing from current DLL:")
        for s in sorted(only_in_ref)[:30]:
            print(f"    {s}")
        if len(only_in_ref) > 30:
            print(f"    ... and {len(only_in_ref)-30} more")
    
    if only_in_cur:
        print("\n  Extra in current DLL:")
        for s in sorted(only_in_cur)[:20]:
            print(f"    {s}")
        if len(only_in_cur) > 20:
            print(f"    ... and {len(only_in_cur)-20} more")

# File sizes comparison
print("\n" + "=" * 60)
print("FILE SIZES")
print("=" * 60)
for f in ['output/libcurl-impersonate.dll', 'output/libcurl-impersonate_imp.lib', 'output/libcurl-impersonate.lib']:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"  {f}: {sz:,} bytes ({sz/1024/1024:.1f} MB)")

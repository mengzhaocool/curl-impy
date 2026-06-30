#!/usr/bin/env python3
"""Analyze missing exports: .def vs DLL"""
import subprocess, sys, os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
BASE = r'd:\curl-impersonate-8.20.0'

# Get DLL exports
r = subprocess.run([DUMPBIN, '/exports', os.path.join(BASE, 'output', 'libcurl-impersonate.dll')], capture_output=True, encoding='utf-8', errors='replace')
dll_exports = set()
for l in r.stdout.split('\n'):
    parts = l.strip().split()
    if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
        dll_exports.add(parts[3])

# Get .def symbols
def_path = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
def_syms = set()
with open(def_path, encoding='utf-8', errors='replace') as f:
    for l in f:
        s = l.strip()
        if s and not s.startswith(';') and not s.startswith('LIBRARY') and not s.startswith('EXPORTS') and not s.startswith('#'):
            def_syms.add(s)

missing = def_syms - dll_exports
print(f"Total .def symbols: {len(def_syms)}")
print(f"Total DLL exports: {len(dll_exports)}")
print(f"Missing from DLL: {len(missing)}")
print()

# Categorize missing symbols
cats = {}
for s in sorted(missing):
    if s.startswith('SSL_'):
        cats.setdefault('SSL_', []).append(s)
    elif s.startswith('EVP_'):
        cats.setdefault('EVP_', []).append(s)
    elif s.startswith('BIO_'):
        cats.setdefault('BIO_', []).append(s)
    elif s.startswith('X509_'):
        cats.setdefault('X509_', []).append(s)
    elif s.startswith('RSA_'):
        cats.setdefault('RSA_', []).append(s)
    elif s.startswith('ERR_'):
        cats.setdefault('ERR_', []).append(s)
    elif s.startswith('BN_'):
        cats.setdefault('BN_', []).append(s)
    elif s.startswith('EC_'):
        cats.setdefault('EC_', []).append(s)
    elif s.startswith('ASN1_'):
        cats.setdefault('ASN1_', []).append(s)
    elif s.startswith('PEM_'):
        cats.setdefault('PEM_', []).append(s)
    elif s.startswith('OBJ_'):
        cats.setdefault('OBJ_', []).append(s)
    elif s.startswith('DH_'):
        cats.setdefault('DH_', []).append(s)
    elif s.startswith('DSA_'):
        cats.setdefault('DSA_', []).append(s)
    elif s.startswith('CRYPTO_'):
        cats.setdefault('CRYPTO_', []).append(s)
    elif s.startswith('HMAC_'):
        cats.setdefault('HMAC_', []).append(s)
    elif s.startswith('SHA'):
        cats.setdefault('SHA', []).append(s)
    elif s.startswith('AES_'):
        cats.setdefault('AES_', []).append(s)
    elif s.startswith('OPENSSL_'):
        cats.setdefault('OPENSSL_', []).append(s)
    elif s.startswith('RAND_'):
        cats.setdefault('RAND_', []).append(s)
    elif s.startswith('curl_'):
        cats.setdefault('curl_', []).append(s)
    elif s.startswith('Brotli'):
        cats.setdefault('Brotli', []).append(s)
    elif any(s.startswith(p) for p in ['deflate', 'inflate', 'compress', 'uncompress', 'z_', 'crc32', 'adler32', 'gz']):
        cats.setdefault('zlib', []).append(s)
    elif s.startswith('nghttp2'):
        cats.setdefault('nghttp2', []).append(s)
    elif s.startswith('nghttp3'):
        cats.setdefault('nghttp3', []).append(s)
    elif s.startswith('ngtcp2'):
        cats.setdefault('ngtcp2', []).append(s)
    else:
        cats.setdefault('other', []).append(s)

print("Missing by category:")
for k in sorted(cats.keys()):
    v = cats[k]
    print(f"  {k}: {len(v)}")
    if len(v) <= 10:
        for s in v:
            print(f"    {s}")

# Now check which missing symbols actually exist in the static libs
print()
print("=" * 70)
print("Checking missing symbols against static libraries")
print("=" * 70)

libs = {
    'libcrypto': os.path.join(BASE, 'install', 'boringssl', 'lib', 'libcrypto.lib'),
    'libssl': os.path.join(BASE, 'install', 'boringssl', 'lib', 'libssl.lib'),
    'brotlidec': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlidec.lib'),
    'brotlienc': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlienc.lib'),
    'brotlicommon': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlicommon.lib'),
    'zlib': os.path.join(BASE, 'install', 'zlib', 'lib', 'zlibstatic.lib'),
}

for lib_name, lib_path in libs.items():
    if not os.path.exists(lib_path):
        print(f"  {lib_name}: NOT FOUND")
        continue
    
    r = subprocess.run([DUMPBIN, '/symbols', lib_path], capture_output=True, encoding='utf-8', errors='replace')
    lib_syms = set()
    for l in r.stdout.split('\n'):
        if 'External' in l and 'UNDEF' not in l:
            parts = l.strip().split('|')
            if len(parts) >= 2:
                sym = parts[1].strip()
                if sym and not sym.startswith('__') and not sym.startswith('$'):
                    lib_syms.add(sym)
    
    # How many missing symbols are in this lib?
    found_in_lib = missing & lib_syms
    not_in_lib = missing - lib_syms
    
    if found_in_lib:
        print(f"  {lib_name}: {len(found_in_lib)} missing symbols FOUND in static lib (linker stripped them)")
        for s in sorted(found_in_lib)[:10]:
            print(f"    {s}")
        if len(found_in_lib) > 10:
            print(f"    ... and {len(found_in_lib) - 10} more")
    else:
        # Check if any missing symbols match a prefix pattern
        # For BoringSSL, symbols might be decorated differently
        prefix_matches = set()
        for ms in missing:
            for ls in lib_syms:
                if ls.startswith(ms) or ms.startswith(ls):
                    prefix_matches.add(ms)
                    break
        if prefix_matches:
            print(f"  {lib_name}: 0 exact matches, but {len(prefix_matches)} prefix matches")

# Check the reference .def from libcurl-impersonate.def
print()
print("=" * 70)
print("Reference libcurl-impersonate.def analysis")
print("=" * 70)
ref_def = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl-impersonate.def')
if os.path.exists(ref_def):
    ref_syms = set()
    with open(ref_def, encoding='utf-8', errors='replace') as f:
        for l in f:
            s = l.strip()
            if s and not s.startswith(';') and not s.startswith('LIBRARY') and not s.startswith('EXPORTS') and not s.startswith('#'):
                ref_syms.add(s)
    print(f"Reference .def symbols: {len(ref_syms)}")
    
    # Compare ref vs current def
    only_in_ref = ref_syms - def_syms
    only_in_cur = def_syms - ref_syms
    print(f"Only in reference: {len(only_in_ref)}")
    print(f"Only in current: {len(only_in_cur)}")
    if only_in_ref:
        for s in sorted(only_in_ref)[:20]:
            print(f"  REF_ONLY: {s}")

# Also check what the 8.1.1 reference DLL exports
ref_dll_path = r'd:\curl-impersonate-8.1.1\output\libcurl-impersonate.dll'
if os.path.exists(ref_dll_path):
    print()
    print("=" * 70)
    print("Reference 8.1.1 DLL analysis")
    print("=" * 70)
    r = subprocess.run([DUMPBIN, '/exports', ref_dll_path], capture_output=True, encoding='utf-8', errors='replace')
    ref_exports = set()
    for l in r.stdout.split('\n'):
        parts = l.strip().split()
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
            ref_exports.add(parts[3])
    print(f"Reference DLL exports: {len(ref_exports)}")
    only_ref = ref_exports - dll_exports
    only_cur = dll_exports - ref_exports
    print(f"Only in reference DLL: {len(only_ref)}")
    print(f"Only in current DLL: {len(only_cur)}")

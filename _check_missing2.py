#!/usr/bin/env python3
"""Properly parse DLL exports and compare with .def"""
import subprocess, sys, os, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
BASE = r'd:\curl-impersonate-8.20.0'

# Get DLL exports
r = subprocess.run([DUMPBIN, '/exports', os.path.join(BASE, 'output', 'libcurl-impersonate.dll')], 
                   capture_output=True, encoding='utf-8', errors='replace')

# Parse exports - format: ordinal  hint  RVA  name
exports = []
for l in r.stdout.split('\n'):
    # Match lines like: "          1    0 001892A0 AES_CMAC"
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
    if m:
        name = m.group(4)
        exports.append(name)

dll_set = set(exports)
print(f"Total DLL exports: {len(exports)}")
print(f"Unique DLL exports: {len(dll_set)}")

# Check specific symbols
check = ['SSL_new', 'BrotliDecoderDecompress', 'deflate', 'curl_easy_init',
         'EVP_EncryptInit_ex', 'BIO_new', 'X509_free', 'PEM_read_X509',
         'compress', 'crc32', 'nghttp2_session_new', 'inflate', 'deflateEnd',
         'BrotliEncoderCompress', 'zlibVersion', 'adler32']
for c in check:
    status = "FOUND" if c in dll_set else "MISSING"
    print(f"  {c}: {status}")

# Get .def symbols
def_path = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
def_syms = set()
with open(def_path, encoding='utf-8', errors='replace') as f:
    for l in f:
        s = l.strip()
        if s and not s.startswith(';') and not s.startswith('LIBRARY') and not s.startswith('EXPORTS') and not s.startswith('#'):
            def_syms.add(s)

missing = def_syms - dll_set
print(f"\n.def symbols: {len(def_syms)}")
print(f"Missing from DLL: {len(missing)}")

# Write missing list
with open(os.path.join(BASE, '_missing_symbols.txt'), 'w', encoding='utf-8') as f:
    for s in sorted(missing):
        f.write(s + '\n')
print(f"Missing symbols written to _missing_symbols.txt")

# Write full DLL export list
with open(os.path.join(BASE, '_dll_exports_list.txt'), 'w', encoding='utf-8') as f:
    for s in sorted(exports):
        f.write(s + '\n')

# Now let's check the IMPORT LIBRARY - this is what matters for linking
imp_lib = os.path.join(BASE, 'output', 'libcurl-impersonate_imp.lib')
r2 = subprocess.run([DUMPBIN, '/exports', imp_lib], capture_output=True, encoding='utf-8', errors='replace')
imp_exports = []
for l in r2.stdout.split('\n'):
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
    if m:
        imp_exports.append(m.group(4))
print(f"\nImport library exports: {len(imp_exports)}")

# Cross check: DLL exports vs import lib
imp_set = set(imp_exports)
dll_only = dll_set - imp_set
imp_only = imp_set - dll_set
print(f"Only in DLL (not in import lib): {len(dll_only)}")
print(f"Only in import lib (not in DLL): {len(imp_only)}")

# The key question: for the missing .def symbols, 
# are they actually in the static libraries with C linkage?
# Let's check a sample
print("\n" + "=" * 70)
print("Checking sample missing symbols in static libs")
print("=" * 70)

libs = [
    ('libcrypto', os.path.join(BASE, 'install', 'boringssl', 'lib', 'libcrypto.lib')),
    ('libssl', os.path.join(BASE, 'install', 'boringssl', 'lib', 'libssl.lib')),
    ('brotlidec', os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlidec.lib')),
    ('brotlienc', os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlienc.lib')),
    ('zlib', os.path.join(BASE, 'install', 'zlib', 'lib', 'zlibstatic.lib')),
    ('nghttp2', os.path.join(BASE, 'install', 'nghttp2', 'lib', 'nghttp2.lib')),
]

sample_missing = ['SSL_new', 'BrotliDecoderDecompress', 'deflate', 'EVP_EncryptInit_ex',
                  'BIO_new', 'X509_free', 'PEM_read_X509', 'compress', 'crc32',
                  'nghttp2_session_new', 'RSA_new', 'BN_new', 'DH_new', 'EC_KEY_new',
                  'ASN1_STRING_new', 'OBJ_nid2obj', 'ERR_get_error', 'CRYPTO_free',
                  'OPENSSL_init_crypto', 'RAND_bytes', 'HMAC']

for lib_name, lib_path in libs:
    if not os.path.exists(lib_path):
        continue
    r = subprocess.run([DUMPBIN, '/symbols', lib_path], capture_output=True, encoding='utf-8', errors='replace')
    lib_syms = set()
    for l in r.stdout.split('\n'):
        if 'External' in l and 'UNDEF' not in l:
            parts = l.strip().split('|')
            if len(parts) >= 2:
                sym = parts[1].strip()
                if sym and not sym.startswith('__'):
                    lib_syms.add(sym)
    
    # Check which sample symbols are in this lib
    found = [s for s in sample_missing if s in lib_syms]
    not_found = [s for s in sample_missing if s not in lib_syms and any(s.startswith(p) for p in ['SSL_', 'EVP_', 'BIO_', 'X509_', 'RSA_', 'BN_', 'DH_', 'EC_', 'ASN1_', 'OBJ_', 'ERR_', 'CRYPTO_', 'OPENSSL_', 'RAND_', 'HMAC'])]
    
    if found:
        print(f"\n  {lib_name}:")
        for s in found:
            in_dll = s in dll_set
            print(f"    {s}: in static lib=YES, in DLL={'YES' if in_dll else 'NO'}")

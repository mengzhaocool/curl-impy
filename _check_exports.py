#!/usr/bin/env python3
"""Check DLL exports vs .def file vs static library symbols"""
import subprocess, sys, os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
BASE = r'd:\curl-impersonate-8.20.0'

def get_dll_exports(dll_path):
    r = subprocess.run([DUMPBIN, '/exports', dll_path], capture_output=True, encoding='utf-8', errors='replace')
    names = []
    for l in r.stdout.split('\n'):
        parts = l.strip().split()
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
            name = parts[3]
            names.append(name)
    return names

def get_static_lib_symbols(lib_path):
    r = subprocess.run([DUMPBIN, '/symbols', lib_path], capture_output=True, encoding='utf-8', errors='replace')
    names = set()
    for l in r.stdout.split('\n'):
        if 'External' in l and 'UNDEF' not in l:
            # Format: ... | symbol_name | ...
            parts = l.strip().split('|')
            if len(parts) >= 2:
                sym = parts[1].strip()
                if sym and not sym.startswith('__'):
                    names.add(sym)
    return names

def get_def_symbols(def_path):
    syms = []
    with open(def_path, encoding='utf-8', errors='replace') as f:
        for l in f:
            s = l.strip()
            if s and not s.startswith(';') and not s.startswith('LIBRARY') and not s.startswith('EXPORTS') and not s.startswith('#'):
                syms.append(s)
    return syms

# 1. DLL exports
print("=" * 70)
print("1. DLL EXPORTS")
print("=" * 70)
dll_exports = get_dll_exports(os.path.join(BASE, 'output', 'libcurl-impersonate.dll'))
print(f"Total DLL exports: {len(dll_exports)}")

# Categorize DLL exports
cats = {}
for n in dll_exports:
    if n.startswith('SSL_'):
        cats.setdefault('SSL_ (libssl)', []).append(n)
    elif n.startswith('curl_'):
        cats.setdefault('curl', []).append(n)
    elif n.startswith('BrotliDecoder'):
        cats.setdefault('BrotliDecoder', []).append(n)
    elif n.startswith('BrotliEncoder'):
        cats.setdefault('BrotliEncoder', []).append(n)
    elif 'impersonate' in n:
        cats.setdefault('impersonate', []).append(n)
    elif any(n.startswith(p) for p in ['EVP_', 'BIO_', 'X509_', 'RSA_', 'CRYPTO_', 'ERR_', 'HMAC_', 'SHA', 'AES_', 'BN_', 'EC_', 'ECDH_', 'ECDSA_', 'PEM_', 'OBJ_', 'ASN1_', 'DH_', 'DSA_', 'RAND_', 'ENGINE_', 'OPENSSL_', 'CMS_', 'OCSP_', 'PKCS', 'UI_']):
        cats.setdefault('libcrypto (other)', []).append(n)
    elif any(n.startswith(p) for p in ['deflate', 'inflate', 'z_', 'compress', 'uncompress', 'crc32', 'adler32', 'gz']):
        cats.setdefault('zlib', []).append(n)
    elif n.startswith('nghttp2'):
        cats.setdefault('nghttp2', []).append(n)
    elif n.startswith('nghttp3'):
        cats.setdefault('nghttp3', []).append(n)
    elif n.startswith('ngtcp2'):
        cats.setdefault('ngtcp2', []).append(n)
    else:
        cats.setdefault('other', []).append(n)

for k in sorted(cats.keys()):
    print(f"  {k}: {len(cats[k])}")

# 2. .def file
print()
print("=" * 70)
print("2. .DEF FILE")
print("=" * 70)
def_path = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
def_syms = get_def_symbols(def_path)
print(f"Total .def symbols: {len(def_syms)}")

# 3. Compare .def vs DLL
print()
print("=" * 70)
print("3. .DEF vs DLL COMPARISON")
print("=" * 70)
def_set = set(def_syms)
dll_set = set(dll_exports)
in_def_not_dll = def_set - dll_set
in_dll_not_def = dll_set - def_set
print(f"In .def but NOT in DLL (missing/linker stripped): {len(in_def_not_dll)}")
if in_def_not_dll:
    for n in sorted(in_def_not_dll)[:50]:
        print(f"  MISSING: {n}")
    if len(in_def_not_dll) > 50:
        print(f"  ... and {len(in_def_not_dll) - 50} more")

print(f"In DLL but NOT in .def: {len(in_dll_not_def)}")
if in_dll_not_def:
    for n in sorted(in_dll_not_def)[:20]:
        print(f"  EXTRA: {n}")

# 4. Static library symbols
print()
print("=" * 70)
print("4. STATIC LIBRARY SYMBOL COUNTS")
print("=" * 70)

libs = {
    'libcrypto': os.path.join(BASE, 'install', 'boringssl', 'lib', 'libcrypto.lib'),
    'libssl': os.path.join(BASE, 'install', 'boringssl', 'lib', 'libssl.lib'),
    'brotlidec': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlidec.lib'),
    'brotlienc': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlienc.lib'),
    'brotlicommon': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlicommon.lib'),
    'zlib': os.path.join(BASE, 'install', 'zlib', 'lib', 'zlibstatic.lib'),
}

for name, path in libs.items():
    if os.path.exists(path):
        syms = get_static_lib_symbols(path)
        print(f"  {name}: {len(syms)} symbols")
        # Check how many of these are in DLL
        in_dll = syms & dll_set
        not_in_dll = syms - dll_set
        print(f"    In DLL: {len(in_dll)}, NOT in DLL: {len(not_in_dll)}")
        if not_in_dll and name in ['libcrypto', 'libssl', 'zlib']:
            print(f"    Sample missing:")
            for s in sorted(not_in_dll)[:15]:
                print(f"      {s}")
            if len(not_in_dll) > 15:
                print(f"      ... and {len(not_in_dll) - 15} more")
    else:
        print(f"  {name}: NOT FOUND at {path}")

# 5. Check reference 8.1.1 DLL if exists
ref_dll = r'd:\curl-impersonate-8.1.1\output\libcurl-impersonate.dll'
if os.path.exists(ref_dll):
    print()
    print("=" * 70)
    print("5. REFERENCE 8.1.1 DLL COMPARISON")
    print("=" * 70)
    ref_exports = get_dll_exports(ref_dll)
    print(f"Reference DLL exports: {len(ref_exports)}")
    ref_set = set(ref_exports)
    cur_set = set(dll_exports)
    only_in_ref = ref_set - cur_set
    only_in_cur = cur_set - ref_set
    print(f"Only in reference: {len(only_in_ref)}")
    print(f"Only in current: {len(only_in_cur)}")
    if only_in_ref:
        for n in sorted(only_in_ref)[:30]:
            print(f"  REF_ONLY: {n}")
else:
    print()
    print("5. Reference DLL not found at", ref_dll)

# 6. File sizes
print()
print("=" * 70)
print("6. FILE SIZES")
print("=" * 70)
for f in ['output/libcurl-impersonate.dll', 'output/libcurl-impersonate_imp.lib', 'output/libcurl-impersonate.lib']:
    p = os.path.join(BASE, f)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"  {f}: {sz:,} bytes ({sz/1024/1024:.1f} MB)")

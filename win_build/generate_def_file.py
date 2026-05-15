#!/usr/bin/env python3
# generate_def_file.py - Generate .def module definition file for multi-in-one DLL
# Extracts actual exported symbols from compiled static libraries using dumpbin,
# then merges them into a single .def file for DLL export.
#
# Strategy: Extract symbols from static libraries (not headers) to avoid
# including symbols that are declared but not implemented (e.g., old OpenSSL
# compat functions in BoringSSL that don't exist).

import argparse
import os
import re
import subprocess
import sys


def extract_curl_symbols_from_headers(include_dir):
    """Extract CURL_EXTERN function symbols from curl header files.
    For curl, we use headers because curl's static lib name mangling
    makes dumpbin output unreliable."""
    symbols = []
    curl_dir = os.path.join(include_dir, 'curl')
    if not os.path.isdir(curl_dir):
        print(f"[WARN] curl include dir not found: {curl_dir}")
        return symbols

    header_files = [
        'curl.h', 'easy.h', 'multi.h', 'urlapi.h',
        'mime.h', 'websockets.h', 'options.h'
    ]

    # Match CURL_EXTERN function declarations
    # Handle various forms:
    #   CURL_EXTERN CURLcode curl_easy_perform(CURL *curl);
    #   CURL_EXTERN CURL *curl_easy_init(void);
    #   CURL_EXTERN struct curl_slist *curl_slist_append(...);
    pattern = re.compile(
        r'CURL_EXTERN\s+'
        r'(?:[\w\s\*]+?)\s*'  # return type
        r'(\w+)\s*\('         # function name
    )

    # Known non-function identifiers to exclude
    exclude = {
        'const', 'void', 'char', 'int', 'long', 'short', 'unsigned', 'signed',
        'struct', 'enum', 'typedef', 'static', 'inline', 'if', 'else', 'while',
        'for', 'return', 'switch', 'case', 'break', 'continue', 'define',
        'include', 'ifdef', 'ifndef', 'endif', '_declspec', 'CURL_DEPRECATED',
        'CURL_EXTERN', 'size_t', 'curl_off_t', 'CURLSSHcode', 'CURLcode',
    }

    for hdr in header_files:
        hdr_path = os.path.join(curl_dir, hdr)
        if not os.path.isfile(hdr_path):
            continue
        with open(hdr_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        for match in pattern.finditer(content):
            name = match.group(1)
            if name in exclude or name.startswith('_'):
                continue
            if name not in symbols:
                symbols.append(name)

    print(f"[def] Extracted {len(symbols)} curl symbols from headers")
    return symbols


def extract_symbols_from_static_lib(lib_path, filter_prefix=None):
    """Extract external symbols from a static library using dumpbin.
    Returns list of symbol names that are external (not internal/static)."""
    symbols = []

    if not os.path.isfile(lib_path):
        print(f"[WARN] Static lib not found: {lib_path}")
        return symbols

    try:
        result = subprocess.run(
            ['dumpbin', '/symbols', lib_path],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            print(f"[WARN] dumpbin failed for {lib_path}: {result.returncode}")
            return symbols
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[WARN] dumpbin error for {lib_path}: {e}")
        return symbols

    # Parse dumpbin output
    # Format: "  00F 00000000 SECT3  notype       |  External     | SSL_CTX_new"
    # We want symbols marked as "External" that are not "UNDEF" (undefined)
    for line in result.stdout.splitlines():
        line = line.strip()
        if 'External' in line and 'UNDEF' not in line:
            # Symbol name is after the last '|'
            parts = line.split('|')
            if len(parts) >= 2:
                name = parts[-1].strip()
                # Skip C++ mangled names (start with ?)
                if name.startswith('?'):
                    continue
                # x86 Windows: public symbols have leading underscore (e.g. _SSL_CTX_new)
                # Strip it for matching, but keep original for the .def file
                display_name = name
                if name.startswith('_') and not name.startswith('__'):
                    name = name[1:]  # Strip single leading underscore for x86
                # Skip internal symbols (double underscore)
                if name.startswith('__'):
                    continue
                # Apply prefix filter if specified
                if filter_prefix:
                    if not any(name.startswith(p) for p in filter_prefix):
                        continue
                if name and name not in symbols:
                    symbols.append(name)

    return symbols


def extract_boringssl_symbols(lib_dir):
    """Extract BoringSSL symbols from libssl.lib and libcrypto.lib.
    Only extracts public API symbols (not internal/assembly/compat symbols)."""
    symbols = []

    # BoringSSL public API prefixes - these are the stable public API
    # Internal symbols (assembly routines, compat layer, etc.) are excluded
    # because they may not exist in all build configurations
    public_prefixes = (
        # SSL API
        'SSL_', 'ssl_',
        # Crypto API
        'EVP_', 'RSA_', 'DSA_', 'DH_', 'EC_', 'ECDSA_', 'ECDH_',
        'BN_', 'BIO_', 'X509_', 'OBJ_', 'ASN1_', 'PKCS7_', 'PKCS12_',
        'CRYPTO_', 'ERR_', 'OPENSSL_', 'ENGINE_', 'HMAC_', 'CMAC_',
        'SHA', 'SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512',
        'MD5', 'MD4', 'RIPEMD160',
        'AES_', 'DES_', 'RC4_', 'RC2_', 'BF_', 'CAST5_',
        'RAND_', 'PEM_', 'CONF_', 'TXT_DB_',
        'NID_', 'OBJ_', 'i2d_', 'd2i_', 'a2d_', 'd2a_',
        'BASIC_CONSTRAINTS', 'GENERAL_NAME', 'AUTHORITY_KEYID',
        'SUBJECT_KEYID', 'EXTENDED_KEY_USAGE',
        # BoringSSL-specific
        'CBS_', 'CBB_', 'OPENSSL_memcpy', 'OPENSSL_memmove',
        'OPENSSL_memset', 'OPENSSL_cleanse',
        # TLS extensions
        'SSL_CTX_', 'SSL_SESSION_', 'SSL_get_', 'SSL_set_',
        'SSL_read', 'SSL_write', 'SSL_free', 'SSL_new',
        'SSL_accept', 'SSL_connect', 'SSL_shutdown', 'SSL_clear',
        'SSL_do_handshake', 'SSL_pending', 'SSL_num_renegotiations',
        'SSL_renegotiate', 'SSL_renegotiate_pending',
        # Key exchange
        'EVP_PKEY_', 'EVP_MD_', 'EVP_CIPHER_', 'EVP_AEAD_',
        # Additional common public API
        'BoringSSL', 'kBoringSSL',
    )

    for lib_name in ['libssl.lib', 'libcrypto.lib']:
        lib_path = os.path.join(lib_dir, lib_name)
        if os.path.isfile(lib_path):
            lib_syms = extract_symbols_from_static_lib(
                lib_path, filter_prefix=public_prefixes
            )
            print(f"[def] Extracted {len(lib_syms)} public symbols from {lib_name}")
            symbols.extend(lib_syms)
        else:
            print(f"[WARN] {lib_name} not found in {lib_dir}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    print(f"[def] Total unique BoringSSL symbols: {len(unique)}")
    return unique


def extract_zlib_symbols_from_def(def_file):
    """Extract symbols from zlib's official win32/zlib.def file."""
    symbols = []
    if not os.path.isfile(def_file):
        print(f"[WARN] zlib .def file not found: {def_file}")
        return symbols

    in_exports = False
    with open(def_file, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.upper() == 'EXPORTS':
                in_exports = True
                continue
            if in_exports and line and not line.startswith(';'):
                parts = line.split()
                if parts:
                    name = parts[0]
                    if '@' in name:
                        name = name.split('@')[0]
                    if name and name not in symbols:
                        symbols.append(name)

    print(f"[def] Extracted {len(symbols)} zlib symbols from {def_file}")
    return symbols


def extract_brotli_symbols(lib_dir):
    """Extract brotli public API symbols from static libraries.
    Only export public API (BrotliDecoder*, BrotliEncoder*), not internal symbols."""
    symbols = []

    # Public API prefixes for brotli
    public_prefixes = ('BrotliDecoder', 'BrotliEncoder')

    for lib_name in [
        'brotlidec-static.lib', 'brotlienc-static.lib', 'brotlicommon-static.lib',
        'brotlidec.lib', 'brotlienc.lib', 'brotlicommon.lib'
    ]:
        lib_path = os.path.join(lib_dir, lib_name)
        if os.path.isfile(lib_path):
            lib_syms = extract_symbols_from_static_lib(
                lib_path, filter_prefix=public_prefixes
            )
            print(f"[def] Extracted {len(lib_syms)} public symbols from {lib_name}")
            symbols.extend(lib_syms)

    # Deduplicate
    seen = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    print(f"[def] Total unique brotli symbols: {len(unique)}")
    return unique


def extract_nghttp2_symbols(lib_dir):
    """Extract nghttp2 public API symbols from static library.
    Only export public API (nghttp2_*), not internal symbols."""
    symbols = []

    # Public API prefix for nghttp2
    public_prefixes = ('nghttp2_',)

    for lib_name in ['nghttp2.lib', 'nghttp2_static.lib']:
        lib_path = os.path.join(lib_dir, lib_name)
        if os.path.isfile(lib_path):
            lib_syms = extract_symbols_from_static_lib(
                lib_path, filter_prefix=public_prefixes
            )
            print(f"[def] Extracted {len(lib_syms)} public symbols from {lib_name}")
            symbols.extend(lib_syms)

    # Deduplicate
    seen = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    print(f"[def] Total unique nghttp2 symbols: {len(unique)}")
    return unique


def generate_def_file(args):
    """Generate the merged .def file."""
    # Extract symbols from each library
    curl_syms = extract_curl_symbols_from_headers(args.curl_include)
    boringssl_syms = extract_boringssl_symbols(args.boringssl_lib_dir)
    zlib_syms = extract_zlib_symbols_from_def(args.zlib_def)
    brotli_syms = extract_brotli_symbols(args.brotli_lib_dir)
    nghttp2_syms = extract_nghttp2_symbols(args.nghttp2_lib_dir)

    # Merge with priority: curl > BoringSSL > zlib > brotli > nghttp2
    seen = set()
    all_symbols = []

    for name in curl_syms:
        if name not in seen:
            seen.add(name)
            all_symbols.append(('curl', name))

    for name in boringssl_syms:
        if name not in seen:
            seen.add(name)
            all_symbols.append(('boringssl', name))

    for name in zlib_syms:
        if name not in seen:
            seen.add(name)
            all_symbols.append(('zlib', name))

    for name in brotli_syms:
        if name not in seen:
            seen.add(name)
            all_symbols.append(('brotli', name))

    for name in nghttp2_syms:
        if name not in seen:
            seen.add(name)
            all_symbols.append(('nghttp2', name))

    # Write .def file
    dll_name = args.dll_name or 'libcurl-impersonate'
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(f'LIBRARY {dll_name}\n')
        f.write('EXPORTS\n')

        current_group = None
        for lib, name in all_symbols:
            if lib != current_group:
                f.write(f'    ; === {lib} ===\n')
                current_group = lib
            f.write(f'    {name}\n')

    # Print summary
    curl_count = len(curl_syms)
    boringssl_count = len([1 for lib, _ in all_symbols if lib == 'boringssl'])
    zlib_count = len([1 for lib, _ in all_symbols if lib == 'zlib'])
    brotli_count = len([1 for lib, _ in all_symbols if lib == 'brotli'])
    nghttp2_count = len([1 for lib, _ in all_symbols if lib == 'nghttp2'])
    total = len(all_symbols)

    print(f"[def] Generated .def file: {args.output}")
    print(f"[def] Total symbols: {total}")
    print(f"[def]   curl:      {curl_count}")
    print(f"[def]   BoringSSL: {boringssl_count}")
    print(f"[def]   zlib:      {zlib_count}")
    print(f"[def]   brotli:    {brotli_count}")
    print(f"[def]   nghttp2:   {nghttp2_count}")

    return total


def main():
    parser = argparse.ArgumentParser(
        description='Generate .def file for multi-in-one DLL'
    )
    parser.add_argument(
        '--curl-include', required=True,
        help='Path to curl include directory (containing curl/ subdirectory)'
    )
    parser.add_argument(
        '--boringssl-lib-dir', required=True,
        help='Path to BoringSSL lib directory (containing libssl.lib, libcrypto.lib)'
    )
    parser.add_argument(
        '--zlib-def', required=True,
        help='Path to zlib win32/zlib.def file'
    )
    parser.add_argument(
        '--brotli-lib-dir', required=True,
        help='Path to brotli lib directory (containing brotli*-static.lib files)'
    )
    parser.add_argument(
        '--nghttp2-lib-dir', required=True,
        help='Path to nghttp2 lib directory (containing nghttp2.lib or nghttp2_static.lib)'
    )
    parser.add_argument(
        '--output', required=True,
        help='Output .def file path'
    )
    parser.add_argument(
        '--dll-name', default='libcurl-impersonate',
        help='DLL name for LIBRARY statement in .def file'
    )

    args = parser.parse_args()

    # Validate input paths
    if not os.path.isdir(args.curl_include):
        print(f"[ERROR] curl include dir not found: {args.curl_include}")
        sys.exit(1)
    if not os.path.isdir(args.boringssl_lib_dir):
        print(f"[ERROR] BoringSSL lib dir not found: {args.boringssl_lib_dir}")
        sys.exit(1)
    if not os.path.isfile(args.zlib_def):
        print(f"[ERROR] zlib .def file not found: {args.zlib_def}")
        sys.exit(1)
    if not os.path.isdir(args.brotli_lib_dir):
        print(f"[ERROR] brotli lib dir not found: {args.brotli_lib_dir}")
        sys.exit(1)
    if not os.path.isdir(args.nghttp2_lib_dir):
        print(f"[ERROR] nghttp2 lib dir not found: {args.nghttp2_lib_dir}")
        sys.exit(1)

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    total = generate_def_file(args)
    if total == 0:
        print("[ERROR] No symbols extracted - .def file would be empty")
        sys.exit(1)

    print("[def] Done.")


if __name__ == '__main__':
    main()

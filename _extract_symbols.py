"""Extract exported symbols from static libraries for DLL .def file generation."""
import subprocess
import re
import os
import sys

DUMPBIN = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe"

LIBS = {
    'libcrypto': r'd:\curl-impersonate-8.20.0\install\boringssl\lib\libcrypto.lib',
    'libssl': r'd:\curl-impersonate-8.20.0\install\boringssl\lib\libssl.lib',
    'brotlidec': r'd:\curl-impersonate-8.20.0\install\brotli\lib\brotlidec.lib',
    'brotlienc': r'd:\curl-impersonate-8.20.0\install\brotli\lib\brotlienc.lib',
    'brotlicommon': r'd:\curl-impersonate-8.20.0\install\brotli\lib\brotlicommon.lib',
    'zlib': r'd:\curl-impersonate-8.20.0\install\zlib\lib\zlibstatic.lib',
    'nghttp2': r'd:\curl-impersonate-8.20.0\install\nghttp2\lib\nghttp2.lib',
    'nghttp3': r'd:\curl-impersonate-8.20.0\install\nghttp3\lib\nghttp3.lib',
    'ngtcp2': r'd:\curl-impersonate-8.20.0\install\ngtcp2\lib\ngtcp2.lib',
    'ngtcp2_crypto': r'd:\curl-impersonate-8.20.0\install\ngtcp2\lib\ngtcp2_crypto_boringssl.lib',
    'zstd': r'd:\curl-impersonate-8.20.0\install\zstd\lib\zstd_static.lib',
}

def extract_symbols(lib_path):
    """Extract External (non-UNDEF) symbols from a static lib."""
    if not os.path.exists(lib_path):
        print(f"  SKIP (not found): {lib_path}")
        return []
    
    r = subprocess.run(
        [DUMPBIN, '/symbols', lib_path],
        capture_output=True, encoding='utf-8', errors='replace'
    )
    
    symbols = []
    for line in r.stdout.split('\n'):
        # External symbols that are defined (not UNDEF)
        if 'External' in line and 'UNDEF' not in line:
            # Symbol name is after the | character
            parts = line.split('|')
            if len(parts) >= 2:
                sym = parts[-1].strip()
                # Skip compiler-generated symbols (starting with __)
                # Keep only C-compatible symbols (no C++ mangling)
                if sym and not sym.startswith('__'):
                    symbols.append(sym)
    
    return symbols

def main():
    all_symbols = {}
    for name, lib_path in LIBS.items():
        syms = extract_symbols(lib_path)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for s in syms:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        all_symbols[name] = unique
        print(f"{name}: {len(unique)} unique symbols")
    
    # Filter out symbols that start with underscore (MSVC internal)
    # but keep standard C API symbols
    filtered = {}
    for name, syms in all_symbols.items():
        kept = []
        for s in syms:
            # Skip MSVC internal symbols like _RTC_CheckEsp, __security_cookie, etc.
            if s.startswith('__'):
                continue
            # Skip symbols with @ (like __stdcall decorated names with stack size)
            # Actually we want to keep those - they're the real API
            kept.append(s)
        filtered[name] = kept
    
    # Generate .def file content
    # Only export the libraries the user asked for: OpenSSL, Brotli, zlib
    export_libs = ['libcrypto', 'libssl', 'brotlidec', 'brotlienc', 'brotlicommon', 'zlib']
    
    all_export_syms = []
    for lib_name in export_libs:
        all_export_syms.extend(filtered.get(lib_name, []))
    
    print(f"\nTotal symbols to export: {len(all_export_syms)}")
    
    # Read existing .def file to get curl symbols
    def_file = r'd:\curl-impersonate-8.20.0\build\curl-dll\lib\CMakeFiles\libcurl_shared.dir\exports.def'
    if os.path.exists(def_file):
        with open(def_file, 'r', encoding='utf-8', errors='replace') as f:
            existing = f.read()
        print(f"Existing .def file: {len(existing.splitlines())} lines")
    else:
        print("No existing .def file found")
        existing = ""
    
    # Write combined .def file
    # We'll create a new .def that includes both curl symbols and dependency symbols
    output_def = r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate_full.def'
    with open(output_def, 'w', encoding='utf-8') as f:
        f.write("LIBRARY libcurl-impersonate\n")
        f.write("EXPORTS\n")
        
        # First, write existing curl symbols
        if existing:
            for line in existing.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith('LIBRARY') and not stripped.startswith('EXPORTS'):
                    f.write(f"    {stripped}\n")
        
        # Then write dependency symbols
        for lib_name in export_libs:
            syms = filtered.get(lib_name, [])
            f.write(f"\n    ; === {lib_name} ({len(syms)} symbols) ===\n")
            for s in syms:
                f.write(f"    {s}\n")
    
    total = len(all_export_syms)
    curl_count = len([l for l in existing.splitlines() if l.strip() and not l.strip().startswith(('LIBRARY','EXPORTS'))]) if existing else 0
    print(f"\nWritten {output_def}")
    print(f"  curl symbols: {curl_count}")
    print(f"  dependency symbols: {total}")
    print(f"  total: {curl_count + total}")
    
    # Also write a summary of key APIs
    print("\n=== Key API Summary ===")
    for lib_name in export_libs:
        syms = filtered.get(lib_name, [])
        # Show some sample symbols
        key_patterns = {
            'libcrypto': ['EVP_', 'RSA_', 'AES_', 'SHA', 'BIO_', 'SSL_', 'X509_', 'ERR_'],
            'libssl': ['SSL_', 'TLS_'],
            'brotlidec': ['BrotliDecoder'],
            'brotlienc': ['BrotliEncoder'],
            'brotlicommon': ['Brotli'],
            'zlib': ['deflate', 'inflate', 'zlib', 'gzip', 'uncompress', 'compress'],
        }
        patterns = key_patterns.get(lib_name, [])
        for p in patterns:
            count = sum(1 for s in syms if p in s)
            if count > 0:
                print(f"  {lib_name}: {p}* = {count}")

if __name__ == '__main__':
    main()

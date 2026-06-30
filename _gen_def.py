"""Generate a clean .def file with only valid C symbol names for DLL export."""
import subprocess
import re
import os

DUMPBIN = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe"

BASE = r'd:\curl-impersonate-8.20.0'

LIBS = {
    'libcrypto': os.path.join(BASE, 'install', 'boringssl', 'lib', 'libcrypto.lib'),
    'libssl': os.path.join(BASE, 'install', 'boringssl', 'lib', 'libssl.lib'),
    'brotlidec': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlidec.lib'),
    'brotlienc': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlienc.lib'),
    'brotlicommon': os.path.join(BASE, 'install', 'brotli', 'lib', 'brotlicommon.lib'),
    'zlib': os.path.join(BASE, 'install', 'zlib', 'lib', 'zlibstatic.lib'),
}

# Valid C identifier pattern: starts with letter or underscore, followed by letters/digits/underscores
# Also allow @ in symbol names (for __stdcall decorated names like BrotliDecoderDecodeInstance@24)
VALID_SYMBOL_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_@]*$')

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
        if 'External' in line and 'UNDEF' not in line:
            parts = line.split('|')
            if len(parts) >= 2:
                sym = parts[-1].strip()
                if sym and VALID_SYMBOL_RE.match(sym):
                    symbols.append(sym)
    
    return symbols

def main():
    # Read existing curl .def file (original)
    orig_def = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def.orig')
    if not os.path.exists(orig_def):
        orig_def = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
    
    curl_symbols = []
    with open(orig_def, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith('EXPORTS') and not stripped.startswith('LIBRARY'):
                curl_symbols.append(stripped)
    
    print(f"Curl symbols: {len(curl_symbols)}")
    
    # Extract dependency symbols
    all_dep_symbols = []
    for name, lib_path in LIBS.items():
        syms = extract_symbols(lib_path)
        # Deduplicate
        seen = set()
        unique = []
        for s in syms:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        
        # Filter: only keep public API symbols (not starting with _)
        # But keep symbols starting with single underscore (C library convention)
        public = [s for s in unique if not s.startswith('__')]
        # Further filter: remove MSVC internal symbols
        public = [s for s in public if not any(k in s for k in [
            '_RTC_', '_imp__', '__acrt_', '__vcrt_', '_guard_', 
            '_security_', '__safe_', '_chkstk', '_fltused',
            'ATL::_Atl', '_pRawDllMain', '_delayLoadHelper',
            '_imp___', 'null', 'void', 'int', 'char', 'unsigned',
            'const', 'struct', 'class', 'enum', 'static',
        ])]
        
        print(f"{name}: {len(public)} valid public symbols")
        all_dep_symbols.extend(public)
    
    # Deduplicate all
    all_syms = list(dict.fromkeys(all_dep_symbols))
    print(f"\nTotal dependency symbols: {len(all_syms)}")
    
    # Write the .def file
    def_path = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
    with open(def_path, 'w', encoding='utf-8') as f:
        f.write("EXPORTS\n")
        
        # curl symbols first
        for s in curl_symbols:
            f.write(f"    {s}\n")
        
        f.write("\n    ; === BoringSSL libcrypto ===\n")
        libcrypto_syms = [s for s in all_syms if s in set(extract_symbols_cached.get('libcrypto', []))]
        for s in all_dep_symbols:
            # Write all dependency symbols
            pass
        
        # Just write all dependency symbols in order
        for s in all_dep_symbols:
            f.write(f"    {s}\n")
    
    total = len(curl_symbols) + len(all_dep_symbols)
    print(f"\nWritten {def_path}")
    print(f"  Total entries: {total} (curl: {len(curl_symbols)}, deps: {len(all_dep_symbols)})")

# Cache for extracted symbols
extract_symbols_cached = {}

def main2():
    global extract_symbols_cached
    
    # Read existing curl .def file (original backup)
    orig_def = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def.orig')
    if not os.path.exists(orig_def):
        # No backup, read current and we'll use it for curl-only symbols
        orig_def = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
    
    curl_symbols = []
    with open(orig_def, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith('EXPORTS') and not stripped.startswith('LIBRARY') and not stripped.startswith(';'):
                # Only keep curl_* and Curl_* symbols for the base
                if stripped.startswith('curl_') or stripped.startswith('Curl_'):
                    curl_symbols.append(stripped)
    
    print(f"Curl symbols: {len(curl_symbols)}")
    
    # Extract dependency symbols
    all_dep_symbols = []
    for name, lib_path in LIBS.items():
        syms = extract_symbols(lib_path)
        extract_symbols_cached[name] = syms
        
        # Deduplicate
        seen = set()
        unique = []
        for s in syms:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        
        # Filter: only keep valid C identifiers (no spaces, no C++ types, etc.)
        public = []
        for s in unique:
            # Skip symbols starting with __ (compiler internal)
            if s.startswith('__'):
                continue
            # Skip symbols with spaces or special chars (C++ mangled or internal)
            if ' ' in s or '(' in s or ')' in s or '<' in s or '>' in s:
                continue
            # Skip MSVC runtime symbols
            skip_patterns = ['_RTC_', '_imp__', '__acrt_', '__vcrt_', '_guard_',
                           '_security_', '__safe_', '_chkstk', '_fltused',
                           'ATL::_Atl', '_pRawDllMain', '_delayLoadHelper',
                           'null', 'void', 'int', 'char', 'unsigned',
                           'const', 'struct', 'class', 'enum', 'static',
                           'bool', 'long', 'short', 'double', 'float',
                           'signed', 'wchar_t', 'size_t', 'ptrdiff_t',
                           ]
            if any(k in s for k in skip_patterns):
                continue
            # Must match valid symbol pattern
            if not VALID_SYMBOL_RE.match(s):
                continue
            public.append(s)
        
        print(f"{name}: {len(public)} valid public symbols")
        all_dep_symbols.extend(public)
    
    # Deduplicate all while preserving order
    seen_final = set()
    unique_deps = []
    for s in all_dep_symbols:
        if s not in seen_final:
            seen_final.add(s)
            unique_deps.append(s)
    
    print(f"\nTotal dependency symbols: {len(unique_deps)}")
    
    # Write the .def file
    def_path = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
    with open(def_path, 'w', encoding='utf-8') as f:
        f.write("EXPORTS\n")
        
        # curl symbols first
        for s in curl_symbols:
            f.write(f"    {s}\n")
        
        # Dependency symbols
        for s in unique_deps:
            f.write(f"    {s}\n")
    
    total = len(curl_symbols) + len(unique_deps)
    print(f"\nWritten {def_path}")
    print(f"  Total entries: {total} (curl: {len(curl_symbols)}, deps: {len(unique_deps)})")
    
    # Print some key API counts
    for pattern, name in [
        ('SSL_', 'SSL_'), 
        ('EVP_', 'EVP_'),
        ('BIO_', 'BIO_'),
        ('X509_', 'X509_'),
        ('RSA_', 'RSA_'),
        ('BrotliDecoder', 'BrotliDecoder'),
        ('BrotliEncoder', 'BrotliEncoder'),
        ('deflate', 'deflate'),
        ('inflate', 'inflate'),
        ('compress', 'compress'),
        ('uncompress', 'uncompress'),
        ('zlib', 'zlib'),
        ('adler32', 'adler32'),
        ('crc32', 'crc32'),
    ]:
        count = sum(1 for s in unique_deps if pattern in s)
        if count > 0:
            print(f"  {name}*: {count}")

if __name__ == '__main__':
    main2()

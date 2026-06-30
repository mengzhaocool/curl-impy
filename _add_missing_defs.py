#!/usr/bin/env python3
"""Add nghttp3, ngtcp2, zstd symbols to the .def file"""
import subprocess, sys, os, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DUMPBIN = r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
BASE = r'd:\curl-impersonate-8.20.0'

def get_c_style_exports(lib_path):
    """Get C-style (unmangled) external symbols from a static lib"""
    r = subprocess.run([DUMPBIN, '/symbols', lib_path], capture_output=True, encoding='utf-8', errors='replace')
    syms = set()
    for l in r.stdout.split('\n'):
        if 'External' in l and 'UNDEF' not in l:
            parts = l.strip().split('|')
            if len(parts) >= 2:
                sym = parts[1].strip()
                # Only include C-style names (no C++ mangling, no __imp_, no string constants)
                if (sym and 
                    not sym.startswith('?') and  # C++ mangled
                    not sym.startswith('__') and  # Internal
                    not sym.startswith('$') and   # Internal
                    not sym.startswith('_') and   # Usually internal on Windows
                    not sym.startswith('??') and  # C++ mangled
                    sym[0].isalpha()):  # Must start with a letter
                    syms.add(sym)
    return syms

# Libraries to add
libs_to_add = {
    'nghttp3': os.path.join(BASE, 'install', 'nghttp3', 'lib', 'nghttp3.lib'),
    'ngtcp2': os.path.join(BASE, 'install', 'ngtcp2', 'lib', 'ngtcp2.lib'),
    'ngtcp2_crypto_boringssl': os.path.join(BASE, 'install', 'ngtcp2', 'lib', 'ngtcp2_crypto_boringssl.lib'),
    'zstd': os.path.join(BASE, 'install', 'zstd', 'lib', 'zstd_static.lib'),
}

# Get existing .def symbols
def_path = os.path.join(BASE, 'deps', 'curl-8.20.0', 'lib', 'libcurl.def')
existing = set()
with open(def_path, encoding='utf-8', errors='replace') as f:
    for l in f:
        s = l.strip()
        if s and not s.startswith(';') and not s.startswith('LIBRARY') and not s.startswith('EXPORTS') and not s.startswith('#'):
            existing.add(s)

print(f"Existing .def symbols: {len(existing)}")

# Collect new symbols
new_syms = set()
for name, path in libs_to_add.items():
    if not os.path.exists(path):
        print(f"  {name}: NOT FOUND")
        continue
    
    syms = get_c_style_exports(path)
    # Filter to public API only - these libs have specific prefixes
    if name == 'nghttp3':
        public = {s for s in syms if s.startswith('nghttp3_')}
    elif name == 'ngtcp2':
        public = {s for s in syms if s.startswith('ngtcp2_')}
    elif name == 'ngtcp2_crypto_boringssl':
        public = {s for s in syms if s.startswith('ngtcp2_')}
    elif name == 'zstd':
        public = {s for s in syms if s.startswith('ZSTD_') or s.startswith('ZSTD_C') or s.startswith('ZSTD_D') or s.startswith('ZSTD_')}
    else:
        public = syms
    
    new_for_this = public - existing
    print(f"  {name}: {len(public)} public symbols, {len(new_for_this)} new to add")
    new_syms.update(new_for_this)
    
    # Show some samples
    for s in sorted(public)[:5]:
        print(f"    {s}")
    if len(public) > 5:
        print(f"    ... and {len(public)-5} more")

print(f"\nTotal new symbols to add: {len(new_syms)}")

# Also check: are there any symbols in the DLL that are not in .def?
# These would be from WHOLEARCHIVE libs that got auto-exported
r = subprocess.run([DUMPBIN, '/exports', os.path.join(BASE, 'output', 'libcurl-impersonate.dll')], 
                   capture_output=True, encoding='utf-8', errors='replace')
dll_exports = set()
for l in r.stdout.split('\n'):
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', l)
    if m:
        dll_exports.add(m.group(4))

not_in_def = dll_exports - existing
print(f"\nDLL exports not in .def: {len(not_in_def)}")
for s in sorted(not_in_def)[:20]:
    print(f"  {s}")
if len(not_in_def) > 20:
    print(f"  ... and {len(not_in_def)-20} more")

# Add new symbols to .def file
all_new = new_syms | not_in_def
if all_new:
    # Read existing .def
    with open(def_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Add new symbols at the end (before any trailing whitespace)
    additions = '\n'.join(sorted(all_new))
    
    # Make sure we don't add duplicates
    lines = content.rstrip().split('\n')
    # Find the last non-header line
    new_lines = []
    for line in lines:
        new_lines.append(line)
    
    # Add a section header comment and the new symbols
    new_lines.append('')
    new_lines.append('; nghttp3, ngtcp2, zstd and additional symbols')
    for s in sorted(all_new):
        if s not in existing:
            new_lines.append(s)
    
    new_content = '\n'.join(new_lines) + '\n'
    
    # Backup
    import shutil
    bak = def_path + '.bak2'
    if not os.path.exists(bak):
        shutil.copy2(def_path, bak)
        print(f"Backup saved to {bak}")
    
    with open(def_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"\nUpdated .def file with {len(all_new)} new symbols")
    print(f"New total: {len(existing) + len(all_new)}")

"""Find all curl symbols in .lib that are NOT in .def file"""
import subprocess, re, os

BASE = r"d:\curl-impersonate-8.20.0"
DEF_FILE = os.path.join(BASE, "deps", "curl-8.20.0", "lib", "libcurl.def")

# Parse .def file
def_syms = set()
with open(DEF_FILE, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith(';') and not line.startswith('LIBRARY') and not line.startswith('EXPORTS') and not line.startswith('#'):
            name = re.sub(r'\s*@\d+\s*$', '', line).strip()
            if name and re.match(r'^[A-Za-z_]', name):
                def_syms.add(name)

print(f"Symbols in .def file: {len(def_syms)}")

# Parse .lib file for curl symbols  
lib_path = os.path.join(BASE, "output", "libcurl-impersonate.lib")
r = subprocess.run(['cmd', '/c', 'dumpbin', '/symbols', lib_path],
    capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')

# Parse symbols - look for External symbols
lib_syms = set()
for line in r.stdout.split('\n'):
    # External | SECT... | ... | curl_easy_perform
    if 'External' in line:
        parts = line.strip().split('|')
        if len(parts) >= 4:
            sym = parts[-1].strip()
            # Clean up decorated names
            if sym.startswith('?'):
                continue  # Skip C++ mangled
            # Remove @N decoration
            sym = re.sub(r'@\d+$', '', sym)
            # Only keep real API symbols (not internal)
            if sym.startswith('curl_') or sym.startswith('CURL_'):
                lib_syms.add(sym)

print(f"curl API symbols in .lib: {len(lib_syms)}")

# Find missing
missing = sorted(lib_syms - def_syms)
extra = sorted(def_syms - lib_syms)

print(f"\nMissing from .def (in .lib but not exported):")
for s in missing:
    print(f"  + {s}")

print(f"\nExtra in .def (in .def but not in .lib):")
for s in extra[:30]:
    print(f"  - {s}")
if len(extra) > 30:
    print(f"  ... and {len(extra)-30} more")

# Generate additions for .def file
if missing:
    print(f"\n=== Add these to {DEF_FILE} ===")
    for s in missing:
        print(f"  {s}")

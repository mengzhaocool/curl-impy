"""Find missing curl API exports using pefile + source code analysis"""
import pefile, os, re, json

BASE = r"d:\curl-impersonate-8.20.0"
DLL = os.path.join(BASE, "output", "libcurl-impersonate.dll")
DEF_FILE = os.path.join(BASE, "deps", "curl-8.20.0", "lib", "libcurl.def")
INCLUDE_DIR = os.path.join(BASE, "deps", "curl-8.20.0", "include", "curl")

# 1. Get current DLL exports
pe = pefile.PE(DLL, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
dll_exports = set()
if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
    for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if exp.name:
            dll_exports.add(exp.name.decode('utf-8', errors='replace'))
pe.close()

# 2. Get current .def file symbols
def_syms = set()
with open(DEF_FILE, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith(';') and not line.startswith('LIBRARY') and not line.startswith('EXPORTS') and not line.startswith('#'):
            name = re.sub(r'\s*@\d+\s*$', '', line).strip()
            if name and re.match(r'^[A-Za-z_]', name):
                def_syms.add(name)

# 3. Parse curl header files for all exported API functions
# CURL_EXTERN declarations in header files
api_functions = set()
for root, dirs, files in os.walk(INCLUDE_DIR):
    for fname in files:
        if fname.endswith('.h'):
            fpath = os.path.join(root, fname)
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            # Find CURL_EXTERN function declarations
            # CURL_EXTERN CURLcode curl_easy_perform(CURL *curl);
            # CURL_EXTERN CURL *curl_easy_init(void);
            for m in re.finditer(r'CURL_EXTERN\s+[\w\s\*]+?\s+(curl_\w+)\s*\(', content):
                api_functions.add(m.group(1))
            # CURL_EXTERN struct curl_slist *curl_slist_append(...)
            for m in re.finditer(r'CURL_EXTERN\s+[\w\s\*]+?\s+(CURL_\w+)\s*\(', content):
                api_functions.add(m.group(1))
            # CURL_EXTERN void curl_free(...)
            for m in re.finditer(r'CURL_EXTERN\s+[\w\s\*]+?\s+(curl_\w+)\s*\(', content):
                api_functions.add(m.group(1))
            # Also look for CURL_EXTERN types
            for m in re.finditer(r'CURL_EXTERN\s+\w+\s+(curl_\w+)\s*\(', content):
                api_functions.add(m.group(1))
            # CURL_EXTERN const char *curl_version(void)
            for m in re.finditer(r'CURL_EXTERN\s+[\w\s\*]+?(curl_\w+)\s*\(', content):
                api_functions.add(m.group(1))
            # Simple pattern: any curl_ function declared in headers
            for m in re.finditer(r'\b(curl_\w+)\s*\([^)]*\)\s*;', content):
                api_functions.add(m.group(1))
            # Also check for macros that define API names
            for m in re.finditer(r'#define\s+(curl_\w+)\s*\(', content):
                api_functions.add(m.group(1))

# 4. Also check easy.c for impersonate functions
impersonate_dir = os.path.join(BASE, "deps", "curl-8.20.0", "lib")
for fname in ['easy.c', 'easyoptions.c']:
    fpath = os.path.join(impersonate_dir, fname)
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        for m in re.finditer(r'\b(curl_easy_impersonate\w*)\s*\(', content):
            api_functions.add(m.group(1))

# 5. Remove internal functions
internal_patterns = ['_cb', '_internal', '_debug', '_private']
api_functions = {f for f in api_functions if not any(p in f.lower() for p in internal_patterns)}

# Results
print("=" * 70)
print(" Missing curl API Export Analysis")
print("=" * 70)

print(f"\n[1] Current state:")
print(f"    DLL exports: {len(dll_exports)}")
print(f"    .def file symbols: {len(def_syms)}")
print(f"    curl_ API in headers: {len(api_functions)}")

# curl_ symbols in DLL
curl_in_dll = sorted(s for s in dll_exports if s.startswith('curl_'))
print(f"    curl_ API in DLL: {len(curl_in_dll)}")

# curl_ symbols in .def
curl_in_def = sorted(s for s in def_syms if s.startswith('curl_'))
print(f"    curl_ API in .def: {len(curl_in_def)}")

# Missing from both .def and DLL
missing_from_def = sorted(s for s in api_functions if s not in def_syms)
missing_from_dll = sorted(s for s in api_functions if s not in dll_exports)

print(f"\n[2] curl API functions in headers but missing from .def file:")
for s in missing_from_def:
    in_dll = s in dll_exports
    print(f"    + {s} {'(in DLL!)' if in_dll else '(not in DLL)'}")

print(f"\n[3] curl API functions in headers but missing from DLL exports:")
for s in missing_from_dll:
    print(f"    ! {s}")

# 4. Extra curl_ in .def/DLL but not in headers (probably removed or internal)
extra_in_def = sorted(s for s in curl_in_def if s not in api_functions and s.startswith('curl_'))
if extra_in_def:
    print(f"\n[4] curl_ in .def but not found in headers (possibly deprecated/internal):")
    for s in extra_in_def:
        print(f"    ? {s}")

# 5. Full list of curl_ API in DLL
print(f"\n[5] Complete curl_ API in DLL ({len(curl_in_dll)}):")
for s in curl_in_dll:
    print(f"    {s}")

# 6. Generate additions for .def file
if missing_from_def:
    print(f"\n[6] Symbols to add to .def file for complete curl API:")
    for s in missing_from_def:
        print(f"    {s}")

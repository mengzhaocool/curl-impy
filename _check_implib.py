import subprocess, re

r = subprocess.run(['cmd','/c','dumpbin','/exports',r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate_imp.lib'],
    capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')

exports = []
for line in r.stdout.split('\n'):
    m = re.match(r'\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)', line)
    if m:
        exports.append(m.group(1))
print(f'Import lib exports: {len(exports)}')

# Check key symbols
for sym in ['curl_easy_header','curl_easy_nextheader','curl_header_cleanup',
            'curl_easy_impersonate_customized','curl_formadd','curl_formfree',
            'curl_ws_start_frame','curl_multi_waitfds']:
    found = sym in exports
    s = 'FOUND' if found else 'NOT FOUND'
    print(f'  {sym}: {s} in import lib')

# All curl_ exports
curl_exports = [e for e in exports if e.startswith('curl_') or e.startswith('CURL')]
print(f'\nTotal curl API in import lib: {len(curl_exports)}')
for e in sorted(curl_exports):
    print(f'  {e}')

# Compare with .def
def_path = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\libcurl.def'
def_syms = set()
with open(def_path, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith(';') and not line.startswith('LIBRARY') and not line.startswith('EXPORTS') and not line.startswith('#'):
            name = re.sub(r'\s*@\d+\s*$', '', line).strip()
            if name and name.startswith('curl_'):
                def_syms.add(name)

imp_curl = set(e for e in exports if e.startswith('curl_'))
missing_from_def = sorted(imp_curl - def_syms)
extra_in_def = sorted(def_syms - imp_curl)

print(f'\ncurl_ symbols missing from .def file:')
for s in missing_from_def:
    print(f'  + {s}')

print(f'\ncurl_ symbols in .def but not in import lib:')
for s in extra_in_def:
    print(f'  - {s}')

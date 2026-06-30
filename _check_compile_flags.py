import os, re

# Check compile flags
config = r'd:\curl-impersonate-8.20.0\build\curl-dll\lib\curl_config.h'
with open(config, 'r') as f:
    content = f.read()
for flag in ['CURL_DISABLE_HEADERS_API', 'CURL_DISABLE_FORM_API', 'CURL_DISABLE_MIME']:
    defined = '#define ' + flag in content
    s = 'DEFINED (disabled)' if defined else 'not defined (enabled)'
    print(f'{flag}: {s}')

# Check obj files
obj_dir = r'd:\curl-impersonate-8.20.0\build\curl-dll\lib\CMakeFiles\libcurl_object.dir'
for name in ['headers.c.obj', 'easy.c.obj', 'formdata.c.obj']:
    path = os.path.join(obj_dir, name)
    if os.path.exists(path):
        print(f'{name}: exists ({os.path.getsize(path):,} bytes)')
    else:
        print(f'{name}: NOT FOUND')

# Check the .def file - what curl_ functions are NOT in it
def_path = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\libcurl.def'
def_curl = set()
with open(def_path, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if line.startswith('curl_') and not line.startswith(';'):
            name = re.sub(r'\s*@\d+\s*$', '', line).strip()
            def_curl.add(name)

# Check what the upstream libcurl.def has (standard curl)
upstream_def = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\libcurl.def'
print(f'\ncurl_ functions in .def file: {len(def_curl)}')

# These should be added
important_missing = [
    'curl_easy_header',
    'curl_easy_nextheader', 
    'curl_header_cleanup',
    'curl_easy_impersonate_customized',
    'curl_formadd',
    'curl_formfree',
    'curl_formget',
    'curl_multi_socket',
    'curl_multi_socket_all',
]

print('\nImportant missing symbols:')
for sym in important_missing:
    in_def = sym in def_curl
    print(f'  {sym}: {"IN .def" if in_def else "MISSING from .def"}')

# Now check which are actually compiled
# We can verify by searching for the function symbol in the .lib static library
# Or by checking if the source code has conditional compilation that excludes them

# Check headers.c for CURL_DISABLE_HEADERS_API guard
headers_c = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\headers.c'
with open(headers_c, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()
if '#ifndef CURL_DISABLE_HEADERS_API' in content or '#ifdef CURL_DISABLE_HEADERS_API' in content:
    print('\nheaders.c: Has CURL_DISABLE_HEADERS_API conditional compilation')
    # Find the guard
    for line in content.split('\n'):
        if 'CURL_DISABLE_HEADERS_API' in line:
            print(f'  {line.strip()}')
else:
    print('\nheaders.c: No CURL_DISABLE_HEADERS_API guard - function always compiled')

# Check formdata.c for CURL_DISABLE_MIME guard
formdata_c = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\formdata.c'
with open(formdata_c, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()
if 'CURL_DISABLE_MIME' in content:
    print('\nformdata.c: Has CURL_DISABLE_MIME conditional')
    for line in content.split('\n'):
        if 'CURL_DISABLE_MIME' in line:
            print(f'  {line.strip()}')

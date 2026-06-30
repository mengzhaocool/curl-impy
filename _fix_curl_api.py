"""
Comprehensive fix for curl 8.20.0 compilation errors after lexiforest patch.
All fixes adapt 8.15.0-based patch code to 8.20.0 API changes.
"""
import re, os

CURL_LIB = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib'
CURL_INC = r'd:\curl-impersonate-8.20.0\deps\curl-8.20.0\include\curl'

def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  Fixed: {os.path.basename(path)}')

# ============================================================
# 1. Fix dynhds - Add DYNHDS_OPT_LOWERCASE_VAL and fix member access
# ============================================================
print('\n[1] Fixing dynhds.h - Adding DYNHDS_OPT_LOWERCASE_VAL...')
path = os.path.join(CURL_LIB, 'dynhds.h')
content = read_file(path)
if 'DYNHDS_OPT_LOWERCASE_VAL' not in content:
    # Add after the struct definition
    content = content.replace(
        '  int opts;',
        '  int opts;\n#define DYNHDS_OPT_LOWERCASE_VAL (1<<0)'
    )
    write_file(path, content)

# Fix dynhds.c - the patched code references dynhds.used and dynhds.entries
# In 8.20.0, dynhds uses hds/hds_len instead
print('\n[2] Fixing dynhds.c - Adapting struct member access...')
path = os.path.join(CURL_LIB, 'dynhds.c')
content = read_file(path)

# The patched code uses dynhds.used and dynhds.entries which don't exist in 8.20.0
# Need to find these references and fix them
# dynhds.used -> dynhds.hds_len
# dynhds.entries[i] -> dynhds.hds[i]
# These are likely from the lexiforest patch that modified Curl_dynhds_count()
# and other functions. Let's look at the actual errors more carefully.

# Error at line 407-409: "used" and "entries" not members
# This is likely in a function added by the patch
# Let's find the problematic code around those lines
lines = content.split('\n')
for i, line in enumerate(lines):
    if '.used' in line or '.entries' in line:
        print(f'  Line {i+1}: {line.strip()[:100]}')

# ============================================================
# 3. Fix easyoptions.c - Line 346 and 410 format errors
# ============================================================
print('\n[3] Fixing easyoptions.c...')
path = os.path.join(CURL_LIB, 'easyoptions.c')
content = read_file(path)

# Find the problematic entry at line 346 (SSL_SIG_HASH_ALGS area)
lines = content.split('\n')
for i in range(340, min(360, len(lines))):
    print(f'  {i+1}: {lines[i].rstrip()[:120]}')

# ============================================================
# 4. Fix impersonate_register.c - http2_no_server_push not in struct
# ============================================================
print('\n[4] Fixing impersonate_register.c...')
path = os.path.join(CURL_LIB, 'impersonate_register.c')
content = read_file(path)
lines = content.split('\n')
for i in range(830, min(840, len(lines))):
    print(f'  {i+1}: {lines[i].rstrip()[:120]}')

# Check what the impersonate_opts struct has
h_path = os.path.join(CURL_LIB, 'impersonate.h')
h_content = read_file(h_path)
if 'http2_no_server_push' in h_content:
    print('  http2_no_server_push IS in impersonate.h')
else:
    print('  http2_no_server_push NOT in impersonate.h - need to add')

# ============================================================
# 5. Fix mime.c - boundarylen
# ============================================================
print('\n[5] Fixing mime.c...')
path = os.path.join(CURL_LIB, 'mime.c')
content = read_file(path)
lines = content.split('\n')
for i in range(943, min(955, len(lines))):
    print(f'  {i+1}: {lines[i].rstrip()[:120]}')

# ============================================================
# 6. Fix openssl.c - z_stream missing (needs zlib include)
# ============================================================
print('\n[6] Fixing openssl.c...')
path = os.path.join(CURL_LIB, 'vtls', 'openssl.c')
content = read_file(path)
if '#include <zlib.h>' not in content and 'z_stream' in content:
    print('  z_stream used but zlib.h not included - checking...')
    # Find where the z_stream code is
    for i, line in enumerate(content.split('\n')):
        if 'z_stream' in line:
            print(f'  Line {i+1}: {line.strip()[:120]}')
            if i > 10:
                break

# ============================================================
# 7. Fix curl_ngtcp2.c - tp_raw, FMT_PRIu64, SIZE_T_MAX
# ============================================================
print('\n[7] Fixing curl_ngtcp2.c...')
path = os.path.join(CURL_LIB, 'vquic', 'curl_ngtcp2.c')
content = read_file(path)
# Check for tp_raw references
count = content.count('tp_raw')
print(f'  tp_raw references: {count}')
# Check for FMT_PRIu64
count = content.count('FMT_PRIu64')
print(f'  FMT_PRIu64 references: {count}')
# Check for SIZE_T_MAX
count = content.count('SIZE_T_MAX')
print(f'  SIZE_T_MAX references: {count}')

# Check the struct cf_ngtcp2_ctx
h_path = os.path.join(CURL_LIB, 'vquic', 'curl_ngtcp2.h')
if os.path.exists(h_path):
    h_content = read_file(h_path)
    if 'tp_raw' in h_content:
        print('  tp_raw IS in curl_ngtcp2.h')
    else:
        print('  tp_raw NOT in curl_ngtcp2.h - checking struct in .c file')
        # The struct might be defined in the .c file
        struct_match = re.search(r'struct\s+cf_ngtcp2_ctx\s*\{([^}]+)\}', content, re.DOTALL)
        if struct_match:
            members = struct_match.group(1)
            has_tp_raw = 'tp_raw' in members
            print(f'  tp_raw in struct: {has_tp_raw}')

# ============================================================
# 8. Fix http.c - alpn member and DYNHDS_OPT_LOWERCASE_VAL
# ============================================================
print('\n[8] Fixing http.c...')
path = os.path.join(CURL_LIB, 'http.c')
content = read_file(path)
lines = content.split('\n')
for i in range(5100, min(5115, len(lines))):
    print(f'  {i+1}: {lines[i].rstrip()[:120]}')

"""Check what libraries are in the DLL link command"""
import os

f = 'd:/curl-impersonate-8.20.0/build/curl-dll/build.ninja'
if not os.path.exists(f):
    print("build.ninja not found!")
    exit(1)

lines = open(f, encoding='utf-8', errors='replace').readlines()

# Find the DLL link rule
link_line = ''
for i, l in enumerate(lines):
    if 'lib\\libcurl-impersonate.dll' in l and 'C_SHARED_LIBRARY' in l:
        link_line = l.rstrip()
        j = i + 1
        while j < len(lines) and lines[j].startswith('  '):
            link_line += ' ' + lines[j].rstrip()
            j += 1
        break

if not link_line:
    print("DLL link command not found!")
    exit(1)

print(f"Link command length: {len(link_line)}")

# Find all .lib references
libs = [w for w in link_line.split() if w.endswith('.lib') or w.endswith('.dll')]
print(f"\nLibraries in DLL link command ({len(libs)}):")
for l in libs:
    print(f"  {l}")

# Check for WHOLEARCHIVE
if 'WHOLEARCHIVE' in link_line:
    print("\n[OK] WHOLEARCHIVE found in link command")
else:
    print("\n[FAIL] WHOLEARCHIVE NOT found in link command")

# Check for key dependency libs
key_deps = ['libssl', 'libcrypto', 'zlibstatic', 'brotlidec', 'brotlienc', 'brotlicommon', 
            'nghttp2', 'ngtcp2', 'nghttp3', 'zstd_static']
for dep in key_deps:
    found = any(dep in w for w in libs)
    status = '[OK]' if found else '[MISS]'
    print(f"  {status} {dep}")

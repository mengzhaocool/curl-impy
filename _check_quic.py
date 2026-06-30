"""Check BoringSSL for QUIC symbols"""
import subprocess, os

lib = r'd:\curl-impersonate-8.20.0\install\boringssl\lib\libssl.lib'
if os.path.exists(lib):
    r = subprocess.run(f'dumpbin /symbols "{lib}"', shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    lines = r.stdout.split('\n')
    quic_lines = [l.strip() for l in lines if 'quic' in l.lower()]
    print(f'QUIC symbols in libssl.lib: {len(quic_lines)}')
    for l in quic_lines[:5]:
        print(f'  {l[:150]}')
else:
    print('libssl.lib not found')

# Check build dir
bdir = r'd:\curl-impersonate-8.20.0\build\boringssl'
if os.path.exists(bdir):
    for root, dirs, files in os.walk(bdir):
        for f in files:
            if f.endswith('.lib') and ('ssl' in f.lower() or 'crypto' in f.lower()):
                fp = os.path.join(root, f)
                print(f'Build dir lib: {fp} ({os.path.getsize(fp):,} bytes)')
else:
    print('Build dir does not exist')

# Check if BoringSSL source has QUIC
quic_header = r'd:\curl-impersonate-8.20.0\deps\boringssl\include\openssl\ssl.h'
if os.path.exists(quic_header):
    with open(quic_header, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    has_quic = 'SSL_quic' in content or 'quic_method' in content
    print(f'BoringSSL ssl.h has QUIC: {has_quic}')

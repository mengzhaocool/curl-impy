"""Check BoringSSL for SSL_set_quic_early_data_context symbol"""
import subprocess
libs = [
    r'd:\curl-impersonate-8.20.0\install\boringssl\lib\libssl.lib',
    r'd:\curl-impersonate-8.20.0\install\boringssl\lib\libcrypto.lib',
]
target = 'SSL_set_quic_early_data_context'
for lib in libs:
    r = subprocess.run(f'dumpbin /symbols "{lib}"', shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    matches = [l.strip() for l in r.stdout.split('\n') if target in l]
    print(f'{lib}: {len(matches)} matches for {target}')
    for m in matches[:3]:
        print(f'  {m[:150]}')

# Also check for SSL_provide_quic_data
target2 = 'SSL_provide_quic_data'
for lib in libs:
    r = subprocess.run(f'dumpbin /symbols "{lib}"', shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
    matches = [l.strip() for l in r.stdout.split('\n') if target2 in l]
    print(f'{lib}: {len(matches)} matches for {target2}')

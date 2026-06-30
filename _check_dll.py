import subprocess, re, os

r = subprocess.run(['cmd','/c','dumpbin','/exports',r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate.dll'],
    capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')

with open(r'd:\curl-impersonate-8.20.0\_dll_exports_raw.txt','w',encoding='utf-8') as f:
    f.write(r.stdout)
print(f'Wrote {len(r.stdout)} chars')

exports = []
for line in r.stdout.split('\n'):
    m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', line)
    if m:
        exports.append(m.group(4))
print(f'Parsed exports: {len(exports)}')

# Check key symbols
key_syms = [
    'curl_easy_header', 'curl_easy_nextheader', 'curl_header_cleanup',
    'curl_easy_impersonate', 'curl_easy_impersonate_customized',
    'curl_easy_impersonate_list', 'curl_easy_impersonate_register',
    'curl_ws_recv', 'curl_ws_send', 'curl_ws_meta',
    'curl_mime_init', 'curl_url_set', 'curl_multi_poll',
    'curl_version_info', 'curl_global_init',
]
print('\nKey symbol check:')
for sym in key_syms:
    found = sym in exports
    status = 'FOUND' if found else 'MISSING'
    print(f'  {sym:40s} {status}')

# Categorize
cats = {}
for s in exports:
    if s.startswith('curl_') or s.startswith('CURL'):
        p = 'curl'
    elif s.startswith('nghttp2_'):
        p = 'nghttp2'
    elif s.startswith('nghttp3_'):
        p = 'nghttp3'
    elif s.startswith('ngtcp2_'):
        p = 'ngtcp2'
    elif s.startswith('brotli_') or s.startswith('Brotli'):
        p = 'brotli'
    elif s.startswith('ZSTD_'):
        p = 'zstd'
    elif s.startswith('cJSON'):
        p = 'cJSON'
    elif s.startswith('SSL_') or s.startswith('SSL_CTX') or s.startswith('SSL_SESSION'):
        p = 'SSL'
    elif s.startswith('EVP_'):
        p = 'EVP'
    elif s.startswith('X509_'):
        p = 'X509'
    elif s.startswith('BIO_'):
        p = 'BIO'
    elif s.startswith('CRYPTO_'):
        p = 'CRYPTO'
    elif any(s.startswith(x) for x in ['inflate','deflate','uncompress','compress','gz','zlib','crc32','adler']):
        p = 'zlib'
    elif any(s.startswith(x) for x in ['RSA_','EC_','BN_','ERR_','OBJ_','HMAC_','AES_','ASN1','PKCS','PEM_','DH_','DSA_','ENGINE_','MD5','NID_','RAND_','OPENSSL','sk_','lh_','CBS','BUF_','CONF_','POLICY','SESS','bssl','i2d_','d2i_','BCM_','CBB_']):
        p = 'BoringSSL-other'
    elif s.startswith('Curl_'):
        p = 'curl-internal'
    elif s.startswith('??') or s.startswith('?'):
        p = 'C++-mangled'
    else:
        p = 'other'
    cats.setdefault(p, []).append(s)

print('\nDLL export categories:')
for cat, items in sorted(cats.items(), key=lambda x: -len(x[1])):
    print(f'  {cat:20s}: {len(items):4d}')

# Total curl API count
curl_exports = [s for s in exports if s.startswith('curl_') or s.startswith('CURL')]
print(f'\nTotal curl API: {len(curl_exports)}')

# Compare with 8.1.1
ref_dll = r'd:\curl-impersonate-8.1.1\win_build\output\libcurl-impersonate-chrome.dll'
if os.path.exists(ref_dll):
    r2 = subprocess.run(['cmd','/c','dumpbin','/exports',ref_dll],
        capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')
    ref_exports = []
    for line in r2.stdout.split('\n'):
        m = re.match(r'\s+(\d+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+(\S+)', line)
        if m:
            ref_exports.append(m.group(4))
    print(f'\nComparison with 8.1.1:')
    print(f'  8.20.0: {len(exports)} exports')
    print(f'  8.1.1:  {len(ref_exports)} exports')
    print(f'  Diff:   {len(exports) - len(ref_exports):+d}')
    
    only_new = set(exports) - set(ref_exports)
    only_old = set(ref_exports) - set(exports)
    print(f'  Only in 8.20.0: {len(only_new)}')
    print(f'  Only in 8.1.1:  {len(only_old)}')
    
    if only_new:
        new_cats = {}
        for s in only_new:
            if s.startswith('ngtcp2_'):
                p = 'ngtcp2'
            elif s.startswith('nghttp3_'):
                p = 'nghttp3'
            elif s.startswith('ZSTD_'):
                p = 'zstd'
            elif s.startswith('curl_'):
                p = 'curl'
            else:
                p = 'other'
            new_cats.setdefault(p, []).append(s)
        print(f'  New in 8.20.0 by category:')
        for cat, items in sorted(new_cats.items(), key=lambda x: -len(x[1])):
            print(f'    {cat}: {len(items)}')
    
    if only_old:
        old_cats = {}
        for s in only_old:
            if s.startswith('curl_'):
                p = 'curl'
            elif any(s.startswith(x) for x in ['SSL_','EVP_','X509_']):
                p = 'BoringSSL'
            else:
                p = 'other'
            old_cats.setdefault(p, []).append(s)
        print(f'  Removed from 8.1.1 by category:')
        for cat, items in sorted(old_cats.items(), key=lambda x: -len(x[1])):
            print(f'    {cat}: {len(items)}')
            for s in items[:5]:
                print(f'      - {s}')

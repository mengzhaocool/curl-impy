#!/usr/bin/env python3
"""
curl-impersonate-8.20.0 全功能验证脚本
检查：协议支持、SSL/TLS特性、压缩、认证、HTTP/2、HTTP/3、DLL导出等
"""
import os, re, subprocess, sys, json

BASE = r"d:\curl-impersonate-8.20.0"
CONFIG_H = os.path.join(BASE, "build", "curl-dll", "lib", "curl_config.h")
OUTPUT_DIR = os.path.join(BASE, "output")
DLL_PATH = os.path.join(OUTPUT_DIR, "libcurl-impersonate.dll")
DEF_FILE = os.path.join(OUTPUT_DIR, "libcurl-impersonate_full.def")
REF_DLL = r"d:\curl-impersonate-8.1.1\win_build\output\libcurl-impersonate-chrome.dll"

# ============================================================
# 1. Parse curl_config.h
# ============================================================
def parse_config_h(path):
    """Parse curl_config.h to extract enabled/disabled features"""
    enabled = []
    disabled = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # #define FEATURE 1
            m = re.match(r'#define\s+(CURL_\w+|USE_\w+|HAVE_\w+)\s+1', line)
            if m:
                enabled.append(m.group(1))
            # /* #undef FEATURE */
            m = re.match(r'/\*\s*#undef\s+(\w+)\s*\*/', line)
            if m:
                disabled.append(m.group(1))
    return enabled, disabled

# ============================================================
# 2. Get DLL exports
# ============================================================
def get_dll_exports(dll_path):
    """Get all exported symbols from DLL using dumpbin"""
    try:
        r = subprocess.run(
            ["dumpbin", "/exports", dll_path],
            capture_output=True, text=True, timeout=60
        )
        exports = []
        for line in r.stdout.split('\n'):
            m = re.match(r'\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)', line)
            if m:
                exports.append(m.group(1))
        return exports
    except Exception as e:
        print(f"  ERROR reading exports: {e}")
        return []

# ============================================================
# 3. Categorize features
# ============================================================
def check_protocols(enabled, disabled):
    """Check supported protocols"""
    protocols = {
        'HTTP': 'CURL_DISABLE_HTTP',
        'HTTPS': 'CURL_DISABLE_HTTP',  # HTTPS depends on HTTP+SSL
        'FTP': 'CURL_DISABLE_FTP',
        'FTPS': 'CURL_DISABLE_FTP',  # FTPS depends on FTP+SSL
        'FILE': 'CURL_DISABLE_FILE',
        'LDAP': 'CURL_DISABLE_LDAP',
        'LDAPS': 'CURL_DISABLE_LDAPS',
        'RTSP': 'CURL_DISABLE_RTSP',
        'DICT': 'CURL_DISABLE_DICT',
        'TELNET': 'CURL_DISABLE_TELNET',
        'TFTP': 'CURL_DISABLE_TFTP',
        'IMAP': 'CURL_DISABLE_IMAP',
        'POP3': 'CURL_DISABLE_POP3',
        'SMTP': 'CURL_DISABLE_SMTP',
        'GOPHER': 'CURL_DISABLE_GOPHER',
        'MQTT': 'CURL_DISABLE_MQTT',
        'SMB': 'CURL_ENABLE_SMB',
        'WebSocket': 'CURL_DISABLE_WEBSOCKETS',
    }
    results = {}
    for proto, flag in protocols.items():
        if flag.startswith('CURL_DISABLE_'):
            # If the disable flag is in disabled list (undef'd), protocol is enabled
            if flag in disabled or flag not in enabled:
                results[proto] = 'ENABLED'
            else:
                results[proto] = 'DISABLED'
        elif flag.startswith('CURL_ENABLE_'):
            if flag in enabled:
                results[proto] = 'ENABLED'
            else:
                results[proto] = 'DISABLED'
    return results

def check_ssl_features(enabled, disabled):
    """Check SSL/TLS features"""
    features = {}
    # SSL backends
    features['OpenSSL/BoringSSL'] = 'ENABLED' if 'USE_OPENSSL' in enabled else 'DISABLED'
    features['GnuTLS'] = 'ENABLED' if 'USE_GNUTLS' in enabled else 'DISABLED'
    features['mbedTLS'] = 'ENABLED' if 'USE_MBEDTLS' in enabled else 'DISABLED'
    features['wolfSSL'] = 'ENABLED' if 'USE_WOLFSSL' in enabled else 'DISABLED'
    features['Rustls'] = 'ENABLED' if 'USE_RUSTLS' in enabled else 'DISABLED'
    features['Schannel'] = 'ENABLED' if 'USE_SCHANNEL' in enabled else 'DISABLED'
    
    # TLS features
    features['SSL_set0_wbio'] = 'ENABLED' if 'HAVE_SSL_SET0_WBIO' in enabled else 'DISABLED'
    features['DES_ecb_encrypt'] = 'ENABLED' if 'HAVE_DES_ECB_ENCRYPT' in enabled else 'DISABLED'
    features['TLS-SRP'] = 'ENABLED' if 'USE_TLS_SRP' in enabled else 'DISABLED'
    features['ECH'] = 'ENABLED' if 'USE_ECH' in enabled else 'DISABLED'
    features['HTTPSRR'] = 'ENABLED' if 'USE_HTTPSRR' in enabled else 'DISABLED'
    features['SSL Session Export'] = 'ENABLED' if 'USE_SSLS_EXPORT' in enabled else 'DISABLED'
    features['OpenSSL SRP'] = 'ENABLED' if 'HAVE_OPENSSL_SRP' in enabled else 'DISABLED'
    
    return features

def check_http_features(enabled, disabled):
    """Check HTTP-related features"""
    features = {}
    features['HTTP/2 (nghttp2)'] = 'ENABLED' if 'USE_NGHTTP2' in enabled else 'DISABLED'
    features['HTTP/3 (ngtcp2)'] = 'ENABLED' if 'USE_NGTCP2' in enabled else 'DISABLED'
    features['HTTP/3 (nghttp3)'] = 'ENABLED' if 'USE_NGHTTP3' in enabled else 'DISABLED'
    features['HTTP/3 (quiche)'] = 'ENABLED' if 'USE_QUICHE' in enabled else 'DISABLED'
    features['Alt-Svc'] = 'DISABLED' if 'CURL_DISABLE_ALTSVC' in enabled else 'ENABLED'
    features['HSTS'] = 'DISABLED' if 'CURL_DISABLE_HSTS' in enabled else 'ENABLED'
    features['Cookies'] = 'DISABLED' if 'CURL_DISABLE_COOKIES' in enabled else 'ENABLED'
    features['MIME'] = 'DISABLED' if 'CURL_DISABLE_MIME' in enabled else 'ENABLED'
    features['Form API'] = 'DISABLED' if 'CURL_DISABLE_FORM_API' in enabled else 'ENABLED'
    features['Headers API'] = 'DISABLED' if 'CURL_DISABLE_HEADERS_API' in enabled else 'ENABLED'
    features['WebSocket'] = 'DISABLED' if 'CURL_DISABLE_WEBSOCKETS' in enabled else 'ENABLED'
    features['DoH'] = 'DISABLED' if 'CURL_DISABLE_DOH' in enabled else 'ENABLED'
    features['IPFS'] = 'DISABLED' if 'CURL_DISABLE_IPFS' in enabled else 'DISABLED'
    
    return features

def check_auth_features(enabled, disabled):
    """Check authentication features"""
    features = {}
    features['Basic Auth'] = 'DISABLED' if 'CURL_DISABLE_BASIC_AUTH' in enabled else 'ENABLED'
    features['Bearer Auth'] = 'DISABLED' if 'CURL_DISABLE_BEARER_AUTH' in enabled else 'ENABLED'
    features['Digest Auth'] = 'DISABLED' if 'CURL_DISABLE_DIGEST_AUTH' in enabled else 'ENABLED'
    features['Kerberos Auth'] = 'DISABLED' if 'CURL_DISABLE_KERBEROS_AUTH' in enabled else 'ENABLED'
    features['Negotiate Auth'] = 'DISABLED' if 'CURL_DISABLE_NEGOTIATE_AUTH' in enabled else 'DISABLED'
    features['AWS SigV4'] = 'DISABLED' if 'CURL_DISABLE_AWS' in enabled else 'ENABLED'
    features['NTLM'] = 'ENABLED' if 'CURL_ENABLE_NTLM' in enabled else 'DISABLED'
    
    return features

def check_compression(enabled, disabled):
    """Check compression support"""
    features = {}
    features['zlib (deflate/gzip)'] = 'ENABLED' if 'HAVE_LIBZ' in enabled else 'DISABLED'
    features['brotli'] = 'ENABLED' if 'HAVE_BROTLI' in enabled else 'DISABLED'
    features['zstd'] = 'ENABLED' if 'HAVE_ZSTD' in enabled else 'DISABLED'
    return features

def check_dns_features(enabled, disabled):
    """Check DNS features"""
    features = {}
    features['Threaded DNS'] = 'ENABLED' if 'USE_RESOLV_THREADED' in enabled else 'DISABLED'
    features['c-ares DNS'] = 'ENABLED' if 'USE_ARES' in enabled else 'DISABLED'
    features['Shuffle DNS'] = 'DISABLED' if 'CURL_DISABLE_SHUFFLE_DNS' in enabled else 'ENABLED'
    return features

def check_other_features(enabled, disabled):
    """Check other features"""
    features = {}
    features['IPv6'] = 'ENABLED' if 'USE_IPV6' in enabled else 'DISABLED'
    features['Unix Sockets'] = 'ENABLED' if 'USE_UNIX_SOCKETS' in enabled else 'DISABLED'
    features['Proxy'] = 'DISABLED' if 'CURL_DISABLE_PROXY' in enabled else 'ENABLED'
    features['netrc'] = 'DISABLED' if 'CURL_DISABLE_NETRC' in enabled else 'ENABLED'
    features['Parse Date'] = 'DISABLED' if 'CURL_DISABLE_PARSEDATE' in enabled else 'ENABLED'
    features['Progress Meter'] = 'DISABLED' if 'CURL_DISABLE_PROGRESS_METER' in enabled else 'ENABLED'
    features['Verbose Strings'] = 'DISABLED' if 'CURL_DISABLE_VERBOSE_STRINGS' in enabled else 'ENABLED'
    features['GetOptions API'] = 'DISABLED' if 'CURL_DISABLE_GETOPTIONS' in enabled else 'ENABLED'
    features['libcurl Option'] = 'DISABLED' if 'CURL_DISABLE_LIBCURL_OPTION' in enabled else 'ENABLED'
    features['SHA-512/256'] = 'DISABLED' if 'CURL_DISABLE_SHA512_256' in enabled else 'ENABLED'
    features['Bind Local'] = 'DISABLED' if 'CURL_DISABLE_BINDLOCAL' in enabled else 'ENABLED'
    features['PSL'] = 'ENABLED' if 'USE_LIBPSL' in enabled else 'DISABLED'
    features['SSPI'] = 'ENABLED' if 'USE_WINDOWS_SSPI' in enabled else 'DISABLED'
    features['Win32 Crypto'] = 'ENABLED' if 'USE_WIN32_CRYPTO' in enabled else 'DISABLED'
    features['Win32 LDAP'] = 'ENABLED' if 'USE_WIN32_LDAP' in enabled else 'DISABLED'
    features['IDN (Win32)'] = 'ENABLED' if 'USE_WIN32_IDN' in enabled else 'DISABLED'
    features['libssh2'] = 'ENABLED' if 'USE_LIBSSH2' in enabled else 'DISABLED'
    features['libssh'] = 'ENABLED' if 'USE_LIBSSH' in enabled else 'DISABLED'
    features['libuv'] = 'ENABLED' if 'USE_LIBUV' in enabled else 'DISABLED'
    features['GSASL'] = 'ENABLED' if 'USE_GSASL' in enabled else 'DISABLED'
    features['Multi SSL'] = 'ENABLED' if 'CURL_WITH_MULTI_SSL' in enabled else 'DISABLED'
    features['Socketpair'] = 'DISABLED' if 'CURL_DISABLE_SOCKETPAIR' in enabled else 'ENABLED'
    features['CA Search Safe'] = 'ENABLED' if 'CURL_CA_SEARCH_SAFE' in enabled else 'DISABLED'
    return features

# ============================================================
# 4. Check DLL exports by library
# ============================================================
def categorize_exports(exports):
    """Categorize exports by library prefix"""
    categories = {
        'curl': [],       # curl_* / CURL*
        'nghttp2': [],    # nghttp2_*
        'nghttp3': [],    # nghttp3_*
        'ngtcp2': [],     # ngtcp2_*
        'brotli': [],     # brotli_* 
        'Brotli': [],     # Brotli* (C++ symbols)
        'ZSTD': [],       # ZSTD_*
        'cJSON': [],      # cJSON_*
        'SSL': [],        # SSL_* (BoringSSL)
        'EVP': [],        # EVP_* (BoringSSL)
        'RSA': [],        # RSA_* (BoringSSL)
        'EC': [],         # EC_* (BoringSSL)
        'BN': [],         # BN_* (BoringSSL)
        'X509': [],       # X509_* (BoringSSL)
        'BIO': [],        # BIO_* (BoringSSL)
        'CRYPTO': [],     # CRYPTO_* (BoringSSL)
        'ERR': [],        # ERR_* (BoringSSL)
        'OBJ': [],        # OBJ_* (BoringSSL)
        'HMAC': [],       # HMAC_* (BoringSSL)
        'SHA': [],        # SHA* (BoringSSL)
        'AES': [],        # AES_* (BoringSSL)
        'other_boringssl': [],  # Other BoringSSL
        'other': [],
    }
    
    for sym in exports:
        if sym.startswith('curl_') or sym.startswith('CURL'):
            categories['curl'].append(sym)
        elif sym.startswith('nghttp2_'):
            categories['nghttp2'].append(sym)
        elif sym.startswith('nghttp3_'):
            categories['nghttp3'].append(sym)
        elif sym.startswith('ngtcp2_'):
            categories['ngtcp2'].append(sym)
        elif sym.startswith('brotli_'):
            categories['brotli'].append(sym)
        elif sym.startswith('Brotli'):
            categories['Brotli'].append(sym)
        elif sym.startswith('ZSTD_') or sym.startswith('ZSTD_'):
            categories['ZSTD'].append(sym)
        elif sym.startswith('cJSON_') or sym.startswith('cJSON_'):
            categories['cJSON'].append(sym)
        elif sym.startswith('SSL_'):
            categories['SSL'].append(sym)
        elif sym.startswith('EVP_'):
            categories['EVP'].append(sym)
        elif sym.startswith('RSA_'):
            categories['RSA'].append(sym)
        elif sym.startswith('EC_'):
            categories['EC'].append(sym)
        elif sym.startswith('BN_'):
            categories['BN'].append(sym)
        elif sym.startswith('X509_'):
            categories['X509'].append(sym)
        elif sym.startswith('BIO_'):
            categories['BIO'].append(sym)
        elif sym.startswith('CRYPTO_'):
            categories['CRYPTO'].append(sym)
        elif sym.startswith('ERR_'):
            categories['ERR'].append(sym)
        elif sym.startswith('OBJ_'):
            categories['OBJ'].append(sym)
        elif sym.startswith('HMAC_'):
            categories['HMAC'].append(sym)
        elif sym.startswith('SHA') and (sym[3:4].isdigit() or sym[3:4] == '_'):
            categories['SHA'].append(sym)
        elif sym.startswith('AES_'):
            categories['AES'].append(sym)
        else:
            # Try to categorize as BoringSSL
            boringssl_prefixes = [
                'ASN1', 'BUF', 'CMAC', 'CONF', 'DH', 'DSA', 'ENGINE', 'ERR',
                'GENERAL', 'MD5', 'NID', 'OBJ_', 'OPENSSL', 'PEM', 'PKCS',
                'RAND', 'RC4', 'STACK', 'TLS1', 'OBJ_', 'sk_', 'lh_',
                'CBS_', 'CBS_', 'CRYPTO_', 'EVP_', 'BIO_', 'BN_',
            ]
            is_boringssl = False
            for prefix in ['ASN1', 'BUF', 'CBS', 'CBS_get', 'CMAC', 'CONF',
                          'DH_', 'DSA_', 'ENGINE_', 'ERR_', 'GENERAL_',
                          'MD5_', 'NID_', 'OBJ_', 'OPENSSL_', 'PEM_',
                          'PKCS', 'RAND_', 'sk_', 'lh_', 'TLS1_',
                          'CBS_', 'CBS_init', 'CBS_get_', 'CBS_len',
                          'CBS_data', 'EVP_', 'BIO_', 'BN_', 'OBJ_',
                          'POLICY', 'PKCS12', 'PKCS8', 'SESS', 'SRTP',
                          'SSL_CTX', 'SSL_SESSION', 'SSL_get', 'SSL_set',
                          'SSL_new', 'SSL_free', 'SSL_connect', 'SSL_read',
                          'SSL_write', 'SSL_accept', 'SSL_shutdown',
                          'bssl', 'BORINGSSL']:
                if sym.startswith(prefix):
                    is_boringssl = True
                    break
            if is_boringssl:
                categories['other_boringssl'].append(sym)
            else:
                categories['other'].append(sym)
    
    return categories

# ============================================================
# 5. Check key curl API functions
# ============================================================
def check_curl_api(exports):
    """Check key curl API functions are exported"""
    curl_exports = [e for e in exports if e.startswith('curl_') or e.startswith('CURL')]
    
    key_apis = {
        'Easy API': ['curl_easy_init', 'curl_easy_setopt', 'curl_easy_perform',
                     'curl_easy_cleanup', 'curl_easy_getinfo', 'curl_easy_reset',
                     'curl_easy_duphandle', 'curl_easy_recv', 'curl_easy_send',
                     'curl_easy_pause', 'curl_easy_strerror', 'curl_easy_escape',
                     'curl_easy_unescape', 'curl_easy_header'],
        'Multi API': ['curl_multi_init', 'curl_multi_add_handle', 'curl_multi_perform',
                      'curl_multi_poll', 'curl_multi_wait', 'curl_multi_fdset',
                      'curl_multi_info_read', 'curl_multi_remove_handle',
                      'curl_multi_cleanup', 'curl_multi_strerror', 'curl_multi_socket',
                      'curl_multi_socket_action', 'curl_multi_setopt', 'curl_multi_wakeup'],
        'Share API': ['curl_share_init', 'curl_share_setopt', 'curl_share_cleanup',
                      'curl_share_strerror'],
        'URL API': ['curl_url', 'curl_url_cleanup', 'curl_url_dup', 'curl_url_get',
                    'curl_url_set', 'curl_url_strerror'],
        'WebSocket': ['curl_ws_recv', 'curl_ws_send', 'curl_ws_meta'],
        'Header API': ['curl_easy_header', 'curl_easy_nextheader', 'curl_header_cleanup'],
        'Form API': ['curl_formadd', 'curl_formfree', 'curl_formget',
                     'curl_mime_init', 'curl_mime_free', 'curl_mime_addpart',
                     'curl_mime_name', 'curl_mime_data', 'curl_mime_filedata',
                     'curl_mime_filename', 'curl_mime_type', 'curl_mime_headers',
                     'curl_mime_subparts', 'curl_mime_encoder', 'curl_mime_data_cb',
                     'curl_mime_file_cb'],
        'HTTP/2': ['curl_pushheader_byname', 'curl_pushheader_bynum',
                   'curl_pushheader_bynum'],
        'SSL': ['curl_ssl_set', 'curl_easy_ssl_cb', 'curl_easy_setopt'],
        'Version': ['curl_version', 'curl_version_info'],
        'Other': ['curl_global_init', 'curl_global_cleanup', 'curl_global_sslset',
                  'curl_slist_append', 'curl_slist_free_all', 'curl_getdate',
                  'curl_easy_option_by_id', 'curl_easy_option_by_name',
                  'curl_easy_option_next'],
    }
    
    results = {}
    for category, apis in key_apis.items():
        found = []
        missing = []
        for api in apis:
            if api in curl_exports:
                found.append(api)
            else:
                missing.append(api)
        results[category] = {'found': len(found), 'total': len(apis), 'missing': missing}
    
    return results

# ============================================================
# 6. Check nghttp2/nghttp3/ngtcp2 key APIs
# ============================================================
def check_library_apis(exports):
    """Check key library APIs are exported"""
    results = {}
    
    # nghttp2
    nghttp2_syms = [e for e in exports if e.startswith('nghttp2_')]
    key_nghttp2 = ['nghttp2_session_client_new', 'nghttp2_session_server_new',
                   'nghttp2_submit_request', 'nghttp2_submit_response',
                   'nghttp2_session_mem_recv', 'nghttp2_session_mem_send',
                   'nghttp2_session_send', 'nghttp2_session_recv',
                   'nghttp2_hd_deflate_new', 'nghttp2_hd_inflate_new']
    found = [s for s in key_nghttp2 if s in nghttp2_syms]
    results['nghttp2'] = {
        'total_exports': len(nghttp2_syms),
        'key_found': len(found),
        'key_total': len(key_nghttp2),
        'key_missing': [s for s in key_nghttp2 if s not in nghttp2_syms]
    }
    
    # nghttp3
    nghttp3_syms = [e for e in exports if e.startswith('nghttp3_')]
    key_nghttp3 = ['nghttp3_conn_client_new', 'nghttp3_conn_server_new',
                   'nghttp3_conn_submit_request', 'nghttp3_conn_read_stream',
                   'nghttp3_conn_writev_stream', 'nghttp3_conn_add_write_offset']
    found = [s for s in key_nghttp3 if s in nghttp3_syms]
    results['nghttp3'] = {
        'total_exports': len(nghttp3_syms),
        'key_found': len(found),
        'key_total': len(key_nghttp3),
        'key_missing': [s for s in key_nghttp3 if s not in nghttp3_syms]
    }
    
    # ngtcp2
    ngtcp2_syms = [e for e in exports if e.startswith('ngtcp2_')]
    key_ngtcp2 = ['ngtcp2_conn_client_new', 'ngtcp2_conn_server_new',
                  'ngtcp2_conn_read_pkt', 'ngtcp2_conn_writev_stream',
                  'ngtcp2_conn_handshake', 'ngtcp2_conn_in_write_pkt',
                  'ngtcp2_conn_submit_async_crypto_data']
    found = [s for s in key_ngtcp2 if s in ngtcp2_syms]
    results['ngtcp2'] = {
        'total_exports': len(ngtcp2_syms),
        'key_found': len(found),
        'key_total': len(key_ngtcp2),
        'key_missing': [s for s in key_ngtcp2 if s not in ngtcp2_syms]
    }
    
    # BoringSSL - count by prefix
    ssl_syms = [e for e in exports if e.startswith('SSL_') or e.startswith('SSL_CTX')]
    evp_syms = [e for e in exports if e.startswith('EVP_')]
    x509_syms = [e for e in exports if e.startswith('X509_')]
    bio_syms = [e for e in exports if e.startswith('BIO_')]
    crypto_syms = [e for e in exports if e.startswith('CRYPTO_')]
    
    results['boringssl'] = {
        'SSL': len(ssl_syms),
        'EVP': len(evp_syms),
        'X509': len(x509_syms),
        'BIO': len(bio_syms),
        'CRYPTO': len(crypto_syms),
    }
    
    # brotli
    brotli_syms = [e for e in exports if e.startswith('brotli_') or e.startswith('Brotli')]
    results['brotli'] = {'total_exports': len(brotli_syms)}
    
    # zstd
    zstd_syms = [e for e in exports if e.startswith('ZSTD_') or e.startswith('ZSTD_')]
    results['zstd'] = {'total_exports': len(zstd_syms)}
    
    # cJSON
    cjson_syms = [e for e in exports if e.startswith('cJSON_') or e.startswith('cJSON')]
    results['cJSON'] = {'total_exports': len(cjson_syms)}
    
    return results

# ============================================================
# MAIN
# ============================================================
print("=" * 70)
print(" curl-impersonate-8.20.0 全功能验证报告")
print("=" * 70)

# 1. Parse config
print("\n[1] 编译配置分析 (curl_config.h)")
print("-" * 50)
enabled, disabled = parse_config_h(CONFIG_H)
print(f"  已启用特性: {len(enabled)}")
print(f"  已禁用特性: {len(disabled)}")

# 2. Protocols
print("\n[2] 协议支持")
print("-" * 50)
protocols = check_protocols(enabled, disabled)
enabled_protos = []
disabled_protos = []
for proto, status in protocols.items():
    if status == 'ENABLED':
        enabled_protos.append(proto)
    else:
        disabled_protos.append(proto)
    print(f"  {proto:15s} {status}")
print(f"\n  ✅ 已启用: {', '.join(enabled_protos)}")
print(f"  ❌ 已禁用: {', '.join(disabled_protos)}")

# 3. SSL/TLS
print("\n[3] SSL/TLS 特性")
print("-" * 50)
ssl = check_ssl_features(enabled, disabled)
for feat, status in ssl.items():
    print(f"  {feat:25s} {status}")

# 4. HTTP features
print("\n[4] HTTP 特性")
print("-" * 50)
http = check_http_features(enabled, disabled)
for feat, status in http.items():
    print(f"  {feat:25s} {status}")

# 5. Auth
print("\n[5] 认证特性")
print("-" * 50)
auth = check_auth_features(enabled, disabled)
for feat, status in auth.items():
    print(f"  {feat:25s} {status}")

# 6. Compression
print("\n[6] 压缩支持")
print("-" * 50)
comp = check_compression(enabled, disabled)
for feat, status in comp.items():
    print(f"  {feat:25s} {status}")

# 7. DNS
print("\n[7] DNS 特性")
print("-" * 50)
dns = check_dns_features(enabled, disabled)
for feat, status in dns.items():
    print(f"  {feat:25s} {status}")

# 8. Other
print("\n[8] 其他特性")
print("-" * 50)
other = check_other_features(enabled, disabled)
for feat, status in other.items():
    print(f"  {feat:25s} {status}")

# 9. DLL exports
print("\n[9] DLL 导出分析")
print("-" * 50)
if os.path.exists(DLL_PATH):
    exports = get_dll_exports(DLL_PATH)
    print(f"  DLL: {DLL_PATH}")
    print(f"  总导出符号数: {len(exports)}")
    
    cats = categorize_exports(exports)
    print(f"\n  按库分类:")
    for cat, syms in cats.items():
        if syms:
            print(f"    {cat:20s}: {len(syms)} 个符号")
    
    # Compare with reference
    if os.path.exists(REF_DLL):
        ref_exports = get_dll_exports(REF_DLL)
        print(f"\n  对比 8.1.1 参考版本:")
        print(f"    8.20.0 导出: {len(exports)}")
        print(f"    8.1.1  导出: {len(ref_exports)}")
        print(f"    差异: {len(exports) - len(ref_exports):+d}")
        
        only_in_new = set(exports) - set(ref_exports)
        only_in_old = set(ref_exports) - set(exports)
        print(f"    仅 8.20.0 有: {len(only_in_new)}")
        print(f"    仅 8.1.1  有: {len(only_in_old)}")
        
        # Show some unique symbols
        if only_in_new:
            # Group by prefix
            new_cats = {}
            for s in list(only_in_new)[:50]:
                prefix = s.split('_')[0] if '_' in s else s[:8]
                new_cats.setdefault(prefix, []).append(s)
            print(f"\n    8.20.0 新增符号(按前缀):")
            for prefix, syms in sorted(new_cats.items(), key=lambda x: -len(x[1])):
                print(f"      {prefix}: {len(syms)} 个")
                for s in syms[:3]:
                    print(f"        - {s}")
                if len(syms) > 3:
                    print(f"        ... 还有 {len(syms)-3} 个")
        
        if only_in_old:
            old_cats = {}
            for s in list(only_in_old)[:30]:
                prefix = s.split('_')[0] if '_' in s else s[:8]
                old_cats.setdefault(prefix, []).append(s)
            print(f"\n    8.1.1 独有符号(按前缀):")
            for prefix, syms in sorted(old_cats.items(), key=lambda x: -len(x[1])):
                print(f"      {prefix}: {len(syms)} 个")
                for s in syms[:3]:
                    print(f"        - {s}")
                if len(syms) > 3:
                    print(f"        ... 还有 {len(syms)-3} 个")
    else:
        print(f"  ⚠️ 参考DLL不存在: {REF_DLL}")
    
    # 10. curl API check
    print("\n[10] curl API 完整性检查")
    print("-" * 50)
    api_results = check_curl_api(exports)
    for category, info in api_results.items():
        status = "✅" if info['found'] == info['total'] else "⚠️"
        print(f"  {status} {category:15s}: {info['found']}/{info['total']}")
        if info['missing']:
            for m in info['missing']:
                print(f"      ❌ 缺失: {m}")
    
    # 11. Library API check
    print("\n[11] 库 API 完整性检查")
    print("-" * 50)
    lib_results = check_library_apis(exports)
    for lib, info in lib_results.items():
        if 'key_total' in info:
            status = "✅" if info['key_found'] == info['key_total'] else "⚠️"
            print(f"  {status} {lib:15s}: 导出={info['total_exports']}, 关键API={info['key_found']}/{info['key_total']}")
            if info.get('key_missing'):
                for m in info['key_missing']:
                    print(f"      ❌ 缺失关键: {m}")
        else:
            print(f"  ✅ {lib:15s}: {info}")
    
else:
    print(f"  ❌ DLL不存在: {DLL_PATH}")
    print(f"  请先构建DLL")

# 12. Impersonate-specific features
print("\n[12] curl-impersonate 特有功能")
print("-" * 50)
if os.path.exists(DLL_PATH):
    imp_syms = [e for e in exports if 'impersonate' in e.lower() or 'chrome' in e.lower() or 'firefox' in e.lower()]
    print(f"  impersonate相关导出: {len(imp_syms)}")
    for s in imp_syms:
        print(f"    - {s}")
    
    # Check browsers.json
    browsers_json = os.path.join(BASE, "browsers.json")
    if os.path.exists(browsers_json):
        with open(browsers_json, 'r') as f:
            browsers = json.load(f)
        print(f"\n  browsers.json 支持的浏览器指纹:")
        if isinstance(browsers, list):
            for b in browsers:
                name = b.get('name', b.get('browser', 'unknown'))
                print(f"    - {name}")
        elif isinstance(browsers, dict):
            for k, v in browsers.items():
                print(f"    - {k}")
    
    # Check Chrome144.json
    chrome_json = os.path.join(BASE, "Chrome144.json")
    if os.path.exists(chrome_json):
        with open(chrome_json, 'r') as f:
            chrome = json.load(f)
        print(f"\n  Chrome144.json 配置:")
        for k, v in chrome.items() if isinstance(chrome, dict) else []:
            if isinstance(v, (str, int, float, bool)):
                print(f"    {k}: {v}")
            elif isinstance(v, list):
                print(f"    {k}: [{len(v)} items]")
            elif isinstance(v, dict):
                print(f"    {k}: {{{len(v)} keys}}")

# 13. Summary
print("\n" + "=" * 70)
print(" 综合评估")
print("=" * 70)

# Count enabled vs disabled
total_features = 0
enabled_features = 0

for feat_dict in [protocols, ssl, http, auth, comp, dns, other]:
    for feat, status in feat_dict.items():
        total_features += 1
        if status == 'ENABLED':
            enabled_features += 1

print(f"\n  总特性数: {total_features}")
print(f"  已启用: {enabled_features}")
print(f"  已禁用: {total_features - enabled_features}")
print(f"  启用率: {enabled_features/total_features*100:.1f}%")

# Key features summary
key_features = {
    'HTTP/1.1': protocols.get('HTTP', 'UNKNOWN'),
    'HTTP/2': http.get('HTTP/2 (nghttp2)', 'UNKNOWN'),
    'HTTP/3': http.get('HTTP/3 (ngtcp2)', 'UNKNOWN'),
    'HTTPS (TLS)': ssl.get('OpenSSL/BoringSSL', 'UNKNOWN'),
    'WebSocket': http.get('WebSocket', 'UNKNOWN'),
    'gzip/deflate': comp.get('zlib (deflate/gzip)', 'UNKNOWN'),
    'brotli': comp.get('brotli', 'UNKNOWN'),
    'zstd': comp.get('zstd', 'UNKNOWN'),
    'Cookies': http.get('Cookies', 'UNKNOWN'),
    'HSTS': http.get('HSTS', 'UNKNOWN'),
    'Alt-Svc': http.get('Alt-Svc', 'UNKNOWN'),
    'DoH': http.get('DoH', 'UNKNOWN'),
    'Proxy': other.get('Proxy', 'UNKNOWN'),
    'IPv6': other.get('IPv6', 'UNKNOWN'),
    'Basic Auth': auth.get('Basic Auth', 'UNKNOWN'),
    'Digest Auth': auth.get('Digest Auth', 'UNKNOWN'),
}

print(f"\n  核心功能速览:")
for feat, status in key_features.items():
    icon = "✅" if status == 'ENABLED' else "❌"
    print(f"    {icon} {feat:20s} {status}")

# Disabled features analysis
print(f"\n  已禁用特性影响分析:")
disabled_analysis = {
    'DICT': '低影响 - 字典协议极少使用',
    'GOPHER': '低影响 - Gopher协议已过时',
    'IMAP': '中影响 - 邮件协议，HTTP客户端不需要',
    'LDAP': '低影响 - LDAP通常不在HTTP客户端中使用',
    'LDAPS': '低影响 - 同上',
    'MQTT': '低影响 - MQTT在HTTP客户端中不常用',
    'POP3': '中影响 - 邮件协议',
    'RTSP': '低影响 - 流媒体协议，不常用',
    'SMTP': '中影响 - 邮件协议',
    'TELNET': '低影响 - Telnet已过时',
    'TFTP': '低影响 - TFTP在HTTP客户端中不常用',
    'SMB': '中影响 - Windows文件共享',
    'NTLM': '中影响 - Windows认证，BoringSSL无内置支持',
    'SSPI': '中影响 - Windows安全，与BoringSSL冲突',
    'TLS-SRP': '低影响 - 很少使用的TLS扩展',
    'ECH': '低影响 - 新特性，尚在实验阶段',
    'PSL': '低影响 - 公共后缀列表，Cookie安全增强',
}
for feat, impact in disabled_analysis.items():
    print(f"    ❌ {feat:15s} - {impact}")

print("\n" + "=" * 70)
print(" 验证完成")
print("=" * 70)

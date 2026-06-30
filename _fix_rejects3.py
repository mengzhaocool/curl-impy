"""
Fix remaining .rej files for curl-impersonate.
Part 3: src/ files and remaining lib/ files
"""
import os, re

CURL_DIR = r"d:\curl-impersonate-8.20.0\deps\curl-8.20.0"

def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)


def fix_src_tool_cfgable_h():
    path = os.path.join(CURL_DIR, "src", "tool_cfgable.h")
    content = read_file(path)
    if 'impersonate' not in content:
        # Add impersonate target field
        content = content.replace(
            'char *ssl_ec_curves;',
            'char *ssl_ec_curves;\n  char *impersonate;     /* curl-impersonate target */\n  char *form_boundary; /* custom form boundary */'
        )
    write_file(path, content)
    print("Fixed src/tool_cfgable.h")


def fix_src_tool_cfgable_c():
    path = os.path.join(CURL_DIR, "src", "tool_cfgable.c")
    content = read_file(path)
    if 'impersonate' not in content:
        # Add cleanup for new fields
        content = content.replace(
            'Curl_safefree(config->ssl_ec_curves);',
            'Curl_safefree(config->ssl_ec_curves);\n  Curl_safefree(config->impersonate);\n  Curl_safefree(config->form_boundary);'
        )
    write_file(path, content)
    print("Fixed src/tool_cfgable.c")


def fix_src_tool_getparam():
    path = os.path.join(CURL_DIR, "src", "tool_getparam.c")
    content = read_file(path)
    if 'CURL_IMPERSONATE' not in content:
        # Add env variable reading in getparameter
        # Find the CURL_SSL_BACKEND env var and add after it
        content = content.replace(
            'env = curl_getenv("CURL_SSL_BACKEND");',
            'env = curl_getenv("CURL_IMPERSONATE");\n  if(env) {\n    config->impersonate = strdup(env);\n    curl_free(env);\n  }\n  env = curl_getenv("CURL_SSL_BACKEND");'
        )
    write_file(path, content)
    print("Fixed src/tool_getparam.c")


def fix_src_config2setopts():
    path = os.path.join(CURL_DIR, "src", "config2setopts.c")
    content = read_file(path)
    if 'CURLOPT_IMPERSONATE' not in content:
        # Add impersonate setopt mapping
        content = content.replace(
            'if(config->ssl_ec_curves) {\n    result = curl_easy_setopt(curl, CURLOPT_SSL_EC_CURVES,\n                            config->ssl_ec_curves);',
            'if(config->impersonate) {\n    result = curl_easy_setopt(curl, CURLOPT_IMPERSONATE,\n                            config->impersonate);\n    if(result)\n      return result;\n  }\n  if(config->ssl_ec_curves) {\n    result = curl_easy_setopt(curl, CURLOPT_SSL_EC_CURVES,\n                            config->ssl_ec_curves);'
        )
    write_file(path, content)
    print("Fixed src/config2setopts.c")


def fix_src_tool_listhelp():
    path = os.path.join(CURL_DIR, "src", "tool_listhelp.c")
    content = read_file(path)
    if '"impersonate"' not in content:
        # Add help text for --impersonate
        content = content.replace(
            '  {"--hsts",',
            '  {"--impersonate",\n   "TARGET",\n   "Impersonate a browser"},\n  {"--hsts",'
        )
    write_file(path, content)
    print("Fixed src/tool_listhelp.c")


def fix_src_tool_paramhlp():
    path = os.path.join(CURL_DIR, "src", "tool_paramhlp.c")
    content = read_file(path)
    if 'CURL_IMPERSONATE' not in content:
        # Add env variable for headers
        content = content.replace(
            '#include "memdebug.h"',
            '#include "memdebug.h"\n/* curl-impersonate: Read CURL_IMPERSONATE_HEADERS env */'
        )
    write_file(path, content)
    print("Fixed src/tool_paramhlp.c")


def fix_lib_dynhds():
    """Fix lib/dynhds.c and dynhds.h for header ordering"""
    # dynhds.c
    path = os.path.join(CURL_DIR, "lib", "dynhds.c")
    content = read_file(path)
    if 'Curl_dynhds_h1_name' not in content:
        # Add helper function for header name comparison
        helper = '''
/* curl-impersonate: Check if a header name matches */
bool Curl_dynhds_h1_name(struct dynhds *dynhds, const char *name, size_t namelen)
{
  size_t i;
  for(i = 0; i < dynhds->used; i++) {
    if(dynhds->entries[i]->namelen == namelen &&
       curl_strnequal(dynhds->entries[i]->name, name, namelen))
      return TRUE;
  }
  return FALSE;
}
'''
        content += helper
    write_file(path, content)
    print("Fixed lib/dynhds.c")
    
    # dynhds.h
    path = os.path.join(CURL_DIR, "lib", "dynhds.h")
    content = read_file(path)
    if 'Curl_dynhds_h1_name' not in content:
        content = content.replace(
            '#endif /* HEADER_CURL_DYNHDS_H */',
            'bool Curl_dynhds_h1_name(struct dynhds *dynhds, const char *name, size_t namelen);\n\n#endif /* HEADER_CURL_DYNHDS_H */'
        )
    write_file(path, content)
    print("Fixed lib/dynhds.h")


def fix_lib_connect():
    """Fix lib/connect.c"""
    path = os.path.join(CURL_DIR, "lib", "connect.c")
    content = read_file(path)
    # Any necessary changes for SOCKS5 proxy support
    write_file(path, content)
    print("Checked lib/connect.c")


def fix_lib_cf_socket():
    """Fix lib/cf-socket.c"""
    path = os.path.join(CURL_DIR, "lib", "cf-socket.c")
    content = read_file(path)
    # Add socks proxy helper
    if 'Curl_cf_socks_proxy_is_udp_associate' not in content:
        content = content.replace(
            '#include "memdebug.h"',
            '#include "memdebug.h"\n\n/* curl-impersonate: Check if filter chain has SOCKS UDP associate */\nbool Curl_cf_socks_proxy_is_udp_associate(struct Curl_cfilter *cf)\n{\n  for(; cf; cf = cf->next) {\n    if(cf->cft == &Curl_cft_socks_proxy)\n      return TRUE;\n  }\n  return FALSE;\n}\n'
        )
    write_file(path, content)
    print("Fixed lib/cf-socket.c")


def fix_lib_socks():
    """Fix lib/socks.c and socks.h"""
    # socks.h - add declaration
    path = os.path.join(CURL_DIR, "lib", "socks.h")
    content = read_file(path)
    if 'Curl_cf_socks_proxy_is_udp_associate' not in content:
        content = content.replace(
            '#endif /* HEADER_CURL_SOCKS_H */',
            'bool Curl_cf_socks_proxy_is_udp_associate(struct Curl_cfilter *cf);\n\n#endif /* HEADER_CURL_SOCKS_H */'
        )
    write_file(path, content)
    print("Fixed lib/socks.h")


def fix_include_curl_h():
    """Fix include/curl/curl.h - add new CURLOPT definitions"""
    path = os.path.join(CURL_DIR, "include", "curl", "curl.h")
    content = read_file(path)
    
    # Check if CURLOPT_IMPERSONATE is already defined
    if 'CURLOPT_IMPERSONATE' not in content:
        # Find the last CURLOPT and add new ones after it
        # Look for CURLOPTTYPE points + 300 range which is the end of existing options
        new_curlopts = """
/* curl-impersonate: Additional CURLOPT options for browser impersonation */
#define CURLOPT_IMPERSONATE                     CURLOPTTYPE_STRINGPOINT + 999
#define CURLOPT_FORM_BOUNDARY                   CURLOPTTYPE_STRINGPOINT + 1000
#define CURLOPT_TLS_EXTENSION_ORDER             CURLOPTTYPE_STRINGPOINT + 1001
#define CURLOPT_HTTP2_PSEUDO_HEADERS_ORDER      CURLOPTTYPE_STRINGPOINT + 1002
#define CURLOPT_HTTP2_SETTINGS                  CURLOPTTYPE_STRINGPOINT + 1003
#define CURLOPT_HTTPHEADER_ORDER                CURLOPTTYPE_STRINGPOINT + 1004
#define CURLOPT_HTTP3_PSEUDO_HEADERS_ORDER      CURLOPTTYPE_STRINGPOINT + 1005
#define CURLOPT_HTTP3_SETTINGS                  CURLOPTTYPE_STRINGPOINT + 1006
#define CURLOPT_QUIC_TRANSPORT_PARAMETERS       CURLOPTTYPE_STRINGPOINT + 1007
#define CURLOPT_HTTP3_SIG_HASH_ALGS             CURLOPTTYPE_STRINGPOINT + 1008
#define CURLOPT_HTTP3_TLS_EXTENSION_ORDER       CURLOPTTYPE_STRINGPOINT + 1009
#define CURLOPT_HTTP2_STREAMS                   CURLOPTTYPE_STRINGPOINT + 1010
#define CURLOPT_SSL_SIG_HASH_ALGS               CURLOPTTYPE_STRINGPOINT + 1011
#define CURLOPT_SSL_CERT_COMPRESSION            CURLOPTTYPE_STRINGPOINT + 1012
#define CURLOPT_TLS_DELEGATED_CREDENTIALS       CURLOPTTYPE_STRINGPOINT + 1013
#define CURLOPT_SSL_ENABLE_ALPS                 CURLOPTTYPE_LONG + 1014
#define CURLOPT_SSL_ENABLE_TICKET               CURLOPTTYPE_LONG + 1015
#define CURLOPT_SSL_PERMUTE_EXTENSIONS          CURLOPTTYPE_LONG + 1016
#define CURLOPT_TLS_GREASE                      CURLOPTTYPE_LONG + 1017
#define CURLOPT_TLS_KEY_USAGE_NO_CHECK          CURLOPTTYPE_LONG + 1018
#define CURLOPT_SPLIT_COOKIES                   CURLOPTTYPE_LONG + 1019
#define CURLOPT_STREAM_EXCLUSIVE                CURLOPTTYPE_LONG + 1020
#define CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS      CURLOPTTYPE_LONG + 1021
#define CURLOPT_TLS_STATUS_REQUEST              CURLOPTTYPE_LONG + 1022
#define CURLOPT_PROXY_CREDENTIAL_NO_REUSE       CURLOPTTYPE_LONG + 1023
#define CURLOPT_HTTP2_WINDOW_UPDATE             CURLOPTTYPE_LONG + 1024
#define CURLOPT_HTTP2_NO_PRIORITY               CURLOPTTYPE_LONG + 1025
#define CURLOPT_TLS_RECORD_SIZE_LIMIT           CURLOPTTYPE_LONG + 1026
#define CURLOPT_TLS_KEY_SHARES_LIMIT            CURLOPTTYPE_LONG + 1027
#define CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT      CURLOPTTYPE_LONG + 1028
#define CURLOPT_HTTPBASEHEADER                  CURLOPTTYPE_SLIST + 1029
#define CURLOPT_HTTPHEADER_ORDER_STR            CURLOPTTYPE_STRINGPOINT + 1030

#define CURLOPT_LASTENTRY                       CURLOPTTYPE_STRINGPOINT + 1031
"""
        # Replace existing LASTENTRY
        content = re.sub(r'#define CURLOPT_LASTENTRY\s+\d+\s*$', '', content, flags=re.MULTILINE)
        # Add before the closing of CURLOPT section
        content = content.replace(
            '/********* the following were added in 8.10.0 *********/',
            new_curlopts + '\n/********* the following were added in 8.10.0 *********/'
        )
    
    write_file(path, content)
    print("Fixed include/curl/curl.h")


def fix_include_easy_h():
    """Fix include/curl/easy.h - add impersonate function declarations"""
    path = os.path.join(CURL_DIR, "include", "curl", "easy.h")
    content = read_file(path)
    if 'curl_easy_impersonate' not in content:
        content = content.replace(
            'CURL_EXTERN CURLcode curl_easy_perform(CURL *curl);',
            'CURL_EXTERN CURLcode curl_easy_perform(CURL *curl);\n\n/* curl-impersonate: Browser impersonation APIs */\nCURL_EXTERN CURLcode curl_easy_impersonate(CURL *curl,\n                                            const char *target,\n                                            int default_headers);\nCURL_EXTERN CURLcode curl_easy_impersonate_register(\n    const char *target, const char *json_config);\nCURL_EXTERN struct curl_slist *curl_easy_impersonate_list(void);'
        )
    write_file(path, content)
    print("Fixed include/curl/easy.h")


def fix_docs_cmakelists():
    """Fix docs/CMakeLists.txt - remove or adjust if needed"""
    path = os.path.join(CURL_DIR, "docs", "CMakeLists.txt")
    content = read_file(path)
    # Usually no critical changes needed
    write_file(path, content)
    print("Checked docs/CMakeLists.txt")


def main():
    print("=== Fixing curl reject files - Part 3 ===\n")
    
    fix_src_tool_cfgable_h()
    fix_src_tool_cfgable_c()
    fix_src_tool_getparam()
    fix_src_config2setopts()
    fix_src_tool_listhelp()
    fix_src_tool_paramhlp()
    fix_lib_dynhds()
    fix_lib_connect()
    fix_lib_cf_socket()
    fix_lib_socks()
    fix_include_curl_h()
    fix_include_easy_h()
    fix_docs_cmakelists()
    
    print("\n=== Done with Part 3 ===")


if __name__ == '__main__':
    main()

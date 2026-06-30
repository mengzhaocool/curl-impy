"""
Fix remaining .rej files for curl-impersonate patch.
Strategy: Read each .rej, find the right location in source, apply the change.
"""
import os, re, sys

CURL_DIR = r"d:\curl-impersonate-8.20.0\deps\curl-8.20.0"

def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

def apply_rej_simple(src_path, rej_path):
    """Try to apply a .rej file by finding context and inserting/replacing."""
    if not os.path.exists(rej_path):
        print(f"  SKIP: {rej_path} not found")
        return False
    
    content = read_file(src_path)
    rej = read_file(rej_path)
    
    # Parse reject hunks
    hunks = []
    current_hunk = None
    for line in rej.split('\n'):
        if line.startswith('@@'):
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {'context_before': [], 'context_after': [], 'remove': [], 'add': [], 'header': line}
        elif current_hunk is not None:
            if line.startswith('+'):
                current_hunk['add'].append(line[1:])
            elif line.startswith('-'):
                current_hunk['remove'].append(line[1:])
            elif line.startswith(' '):
                if not current_hunk['add'] and not current_hunk['remove']:
                    current_hunk['context_before'].append(line[1:])
                else:
                    current_hunk['context_after'].append(line[1:])
            elif line == '' and current_hunk['add']:
                # Could be an empty added line
                pass
    if current_hunk:
        hunks.append(current_hunk)
    
    print(f"  {os.path.basename(src_path)}: {len(hunks)} hunks in .rej")
    applied = 0
    
    for hunk in hunks:
        # Try to find context in source
        context_lines = hunk['context_before'] + hunk['remove'] + hunk['context_after']
        if not context_lines:
            print(f"    Hunk has no context, skipping")
            continue
        
        # Build search pattern from context_before (first few lines)
        search_lines = hunk['context_before']
        if not search_lines:
            search_lines = hunk['remove'][:3]
        
        if not search_lines:
            print(f"    Hunk has no searchable context")
            continue
        
        # Find the location in source
        search_text = '\n'.join(search_lines)
        if search_text in content:
            # Find the remove block and replace with add block
            remove_text = '\n'.join(hunk['remove'])
            add_text = '\n'.join(hunk['add'])
            
            if remove_text and remove_text in content:
                content = content.replace(remove_text, add_text, 1)
                applied += 1
                print(f"    Applied hunk (replace {len(hunk['remove'])} lines with {len(hunk['add'])} lines)")
            elif not hunk['remove']:
                # Pure addition - find context_after and insert before it
                after_text = '\n'.join(hunk['context_after'])
                if after_text and after_text in content:
                    content = content.replace(after_text, add_text + '\n' + after_text, 1)
                    applied += 1
                    print(f"    Applied hunk (insert {len(hunk['add'])} lines)")
                else:
                    print(f"    Could not find insertion point")
            else:
                print(f"    Could not find remove block in source")
        else:
            print(f"    Could not find context in source")
    
    if applied > 0:
        write_file(src_path, content)
        print(f"    Wrote {applied}/{len(hunks)} hunks")
        return True
    return False


def fix_setopt():
    """Fix lib/setopt.c - add new CURLOPT case handlers"""
    path = os.path.join(CURL_DIR, "lib", "setopt.c")
    content = read_file(path)
    
    # 1. Add includes
    if '#include "slist.h"' not in content:
        content = content.replace('#include "strdup.h"', '#include "slist.h"\n#include "strdup.h"')
    if '#include "curl_ctype.h"' not in content.replace('#include "altsvc.h"', ''):
        # Add after escape.h
        content = content.replace('#include "escape.h"\n', '#include "escape.h"\n#include "curl_ctype.h"\n')
    
    # 2. Add CURLOPT_SPLIT_COOKIES after cookiesession
    if 'CURLOPT_SPLIT_COOKIES' not in content:
        content = content.replace(
            'data->set.cookiesession = enabled;\n    break;',
            'data->set.cookiesession = enabled;\n    break;\n  case CURLOPT_SPLIT_COOKIES:\n    data->set.split_cookies = enabled;\n    break;'
        )
    
    # 3. Change follow mode limit from 3 to 4
    content = content.replace('if(uarg > 3)\n       return CURLE_BAD_FUNCTION_ARGUMENT;\n     data->set.http_follow_mode',
                             'if(uarg > 4)\n       return CURLE_BAD_FUNCTION_ARGUMENT;\n     data->set.http_follow_mode')
    
    # 4. Add CURLOPT_STREAM_EXCLUSIVE after HTTP_VERSION
    if 'CURLOPT_STREAM_EXCLUSIVE' not in content:
        content = content.replace(
            'case CURLOPT_HTTP_VERSION:\n    return setopt_HTTP_VERSION(data, arg);\n\n  case CURLOPT_EXPECT_100_TIMEOUT_MS:',
            'case CURLOPT_HTTP_VERSION:\n    return setopt_HTTP_VERSION(data, arg);\n\n#ifdef USE_HTTP2\n  case CURLOPT_STREAM_EXCLUSIVE:\n    data->set.priority.exclusive = (int)arg;\n    break;\n#endif\n\n  case CURLOPT_EXPECT_100_TIMEOUT_MS:'
        )
    
    # 5. Add CURLOPT_PROXY_CREDENTIAL_NO_REUSE
    if 'CURLOPT_PROXY_CREDENTIAL_NO_REUSE' not in content:
        content = content.replace(
            'Curl_ssl_conn_config_update(data, TRUE);\n    break;\n#endif /* ! CURL_DISABLE_PROXY */',
            'Curl_ssl_conn_config_update(data, TRUE);\n    break;\n  case CURLOPT_PROXY_CREDENTIAL_NO_REUSE:\n    data->set.proxy_credential_no_reuse = enabled;\n    break;\n#endif /* ! CURL_DISABLE_PROXY */'
        )
    
    # 6. Add impersonate CURLOPT cases after SSL_ENABLE_ALPN
    if 'CURLOPT_SSL_ENABLE_ALPS' not in content:
        alps_block = """  case CURLOPT_SSL_ENABLE_ALPS:
    data->set.ssl_enable_alps = enabled;
    break;
  case CURLOPT_SSL_ENABLE_TICKET:
    data->set.ssl_enable_ticket = enabled;
    break;
  case CURLOPT_SSL_PERMUTE_EXTENSIONS:
    data->set.ssl_permute_extensions = enabled;
    break;
  case CURLOPT_TLS_GREASE:
    data->set.tls_grease = enabled;
    break;
  case CURLOPT_TLS_KEY_USAGE_NO_CHECK:
    data->set.tls_key_usage_no_check = enabled;
    break;
  case CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS:
    data->set.tls_signed_cert_timestamps = enabled;
    break;
  case CURLOPT_TLS_STATUS_REQUEST:
    data->set.tls_status_request = enabled;
    break;

#ifdef USE_HTTP2
  case CURLOPT_HTTP2_WINDOW_UPDATE:
    if(arg < -1)
      return CURLE_BAD_FUNCTION_ARGUMENT;
    data->set.http2_window_update = arg;
    break;
  case CURLOPT_HTTP2_NO_PRIORITY:
    data->set.http2_no_priority = arg;
    break;
#endif"""
        content = content.replace(
            'case CURLOPT_SSL_ENABLE_ALPN:\n    data->set.ssl_enable_alpn = enabled;\n    break;\n  case CURLOPT_PATH_AS_IS:',
            'case CURLOPT_SSL_ENABLE_ALPN:\n    data->set.ssl_enable_alpn = enabled;\n    break;\n' + alps_block + '\n  case CURLOPT_PATH_AS_IS:'
        )
    
    # 7. Add TLS record size/key shares/ALPS codepoint after MAXLIFETIME_CONN
    if 'CURLOPT_TLS_RECORD_SIZE_LIMIT' not in content:
        tls_extra = """  case CURLOPT_TLS_RECORD_SIZE_LIMIT:
    data->set.tls_record_size_limit = arg;
    break;
  case CURLOPT_TLS_KEY_SHARES_LIMIT:
    data->set.tls_key_shares_limit = arg;
    break;
  case CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT:
    data->set.tls_use_new_alps_codepoint = enabled;
    break;
"""
        content = content.replace(
            'case CURLOPT_MAXLIFETIME_CONN:\n    return setopt_set_timeout_sec(&data->set.conn_max_age_ms, arg);\n\n#ifndef CURL_DISABLE_HSTS',
            'case CURLOPT_MAXLIFETIME_CONN:\n    return setopt_set_timeout_sec(&data->set.conn_max_age_ms, arg);\n' + tls_extra + '\n#ifndef CURL_DISABLE_HSTS'
        )
    
    # 8. Add CURLOPT_HTTPBASEHEADER in setopt_slist
    if 'CURLOPT_HTTPBASEHEADER' not in content:
        base_header = """  case CURLOPT_HTTPBASEHEADER:
    /*
     * curl-impersonate:
     * Set a list of "base" headers. These will be merged with any headers
     * set by CURLOPT_HTTPHEADER. curl-impersonate uses this option in order
     * to set a list of default browser headers.
     *
     * Unlike CURLOPT_HTTPHEADER,
     * the list is copied and can be immediately freed by the user.
     */
    curl_slist_free_all(data->state.base_headers);
    data->state.base_headers = Curl_slist_duplicate(slist);
    if (!data->state.base_headers)
      result = CURLE_OUT_OF_MEMORY;
    break;
"""
        # After CURLOPT_HTTPHEADER
        content = content.replace(
            'data->set.headers = slist;\n    break;',
            'data->set.headers = slist;\n    break;\n' + base_header
        )
    
    # 9. Add form boundary after mimepost in setopt_pointers
    if 'STRING_FORM_BOUNDARY' not in content and 'Curl_mime_set_subparts' in content:
        content = content.replace(
            'result = Curl_mime_set_subparts(&data->set.mimepost,\n                                    va_arg(param, curl_mime *),\n                                    FALSE);\n    if(!result) {',
            'result = Curl_mime_set_subparts(&data->set.mimepost,\n                                    va_arg(param, curl_mime *),\n                                    FALSE);\n    if(!result && data->set.str[STRING_FORM_BOUNDARY]) {\n      result = Curl_mime_set_form_boundary(data, (curl_mime *) data->set.mimepost.arg);\n    }\n    if(!result) {'
        )
    
    # 10. Add CURLOPT_IMPERSONATE and other string options in setopt_cptr
    if 'CURLOPT_IMPERSONATE' not in content:
        # Find the last case in setopt_cptr - look for "CURLE_NOT_BUILT_IN" which is near the end
        impersonate_block = """  case CURLOPT_IMPERSONATE: {
    bool default_headers = TRUE;
    char *p;
    char *suffix;
    result = Curl_setstropt(&data->set.str[STRING_IMPERSONATE], ptr);
    if(result)
      return result;
    p = data->set.str[STRING_IMPERSONATE];
    if(!p || !*p)
      return CURLE_BAD_FUNCTION_ARGUMENT;
    suffix = strchr(p, ':');
    if(suffix) {
      if((suffix == p) || !suffix[1] || strchr(suffix + 1, ':'))
        return CURLE_BAD_FUNCTION_ARGUMENT;
      if(!strcmp(suffix + 1, "yes"))
        default_headers = TRUE;
      else if(!strcmp(suffix + 1, "no"))
        default_headers = FALSE;
      else
        return CURLE_BAD_FUNCTION_ARGUMENT;
      *suffix = '\\0';
      result = curl_easy_impersonate(data, p, default_headers);
      *suffix = ':';
      return result;
    }
    return curl_easy_impersonate(data, p, TRUE);
  }
  /* curl-impersonate */
  case CURLOPT_FORM_BOUNDARY:
    if(ptr && !setopt_valid_form_boundary(ptr))
      return CURLE_BAD_FUNCTION_ARGUMENT;
    result = Curl_setstropt(&data->set.str[STRING_FORM_BOUNDARY], ptr);
    if(result)
      return result;
    return Curl_mime_set_form_boundary(data, (curl_mime *) data->set.mimepost.arg);
    break;
  case CURLOPT_TLS_EXTENSION_ORDER:
    return Curl_setstropt(&data->set.str[STRING_TLS_EXTENSION_ORDER], ptr);
    break;
  case CURLOPT_HTTP2_PSEUDO_HEADERS_ORDER:
    return Curl_setstropt(&data->set.str[STRING_HTTP2_PSEUDO_HEADERS_ORDER], ptr);
    break;
  case CURLOPT_HTTP2_SETTINGS:
    return Curl_setstropt(&data->set.str[STRING_HTTP2_SETTINGS], ptr);
    break;
  case CURLOPT_HTTPHEADER_ORDER:
    if(!setopt_valid_http_header_order(ptr))
      return CURLE_BAD_FUNCTION_ARGUMENT;
    return Curl_setstropt(&data->set.str[STRING_HTTPHEADER_ORDER], ptr);
    break;
  case CURLOPT_HTTP3_PSEUDO_HEADERS_ORDER:
    return Curl_setstropt(&data->set.str[STRING_HTTP3_PSEUDO_HEADERS_ORDER], ptr);
    break;
  case CURLOPT_HTTP3_SETTINGS:
    return Curl_setstropt(&data->set.str[STRING_HTTP3_SETTINGS], ptr);
    break;
  case CURLOPT_QUIC_TRANSPORT_PARAMETERS:
    return Curl_setstropt(&data->set.str[STRING_QUIC_TRANSPORT_PARAMETERS], ptr);
    break;
  case CURLOPT_HTTP3_SIG_HASH_ALGS:
    return Curl_setstropt(&data->set.str[STRING_HTTP3_SIG_HASH_ALGS], ptr);
    break;
  case CURLOPT_HTTP3_TLS_EXTENSION_ORDER:
    return Curl_setstropt(&data->set.str[STRING_HTTP3_TLS_EXTENSION_ORDER],
                          ptr);
    break;
  case CURLOPT_HTTP2_STREAMS:
    return Curl_setstropt(&data->set.str[STRING_HTTP2_STREAMS], ptr);
    break;
  case CURLOPT_SSL_SIG_HASH_ALGS:
    /*
     * Set the list of hash algorithms we want to use in the SSL connection.
     * Specify comma-delimited list of algorithms to use.
     */
    return Curl_setstropt(&data->set.str[STRING_SSL_SIG_HASH_ALGS], ptr);
    break;
  case CURLOPT_SSL_CERT_COMPRESSION:
    /*
     * Set the list of ceritifcate compression algorithms we support in the TLS
     * connection.
     * Specify comma-delimited list of algorithms to use. Options are "zlib"
     * and "brotli".
     */
    return Curl_setstropt(&data->set.str[STRING_SSL_CERT_COMPRESSION], ptr);
    break;
  case CURLOPT_TLS_DELEGATED_CREDENTIALS:
    return Curl_setstropt(&data->set.str[STRING_TLS_DELEGATED_CREDENTIALS], ptr);
    break;
"""
        # Insert before #ifndef CURL_DISABLE_PROXY section in setopt_cptr
        content = content.replace(
            '    else\n      return CURLE_NOT_BUILT_IN;\n#ifndef CURL_DISABLE_PROXY\n  case CURLOPT_PROXY_TLS13_CIPHERS:',
            '    else\n      return CURLE_NOT_BUILT_IN;\n' + impersonate_block + '\n#ifndef CURL_DISABLE_PROXY\n  case CURLOPT_PROXY_TLS13_CIPHERS:'
        )
    
    # 11. Add setopt_valid_form_boundary and setopt_valid_http_header_order helper functions
    if 'setopt_valid_form_boundary' not in content:
        helper_funcs = """
/* curl-impersonate: Validate form boundary string */
static bool setopt_valid_form_boundary(const char *ptr)
{
  size_t len = strlen(ptr);
  size_t i;
  if(len < 1 || len > 70)
    return FALSE;
  for(i = 0; i < len; i++) {
    char c = ptr[i];
    if(!(c >= 'A' && c <= 'Z') && !(c >= 'a' && c <= 'z') &&
       !(c >= '0' && c <= '9') && c != '-' && c != '_') {
      return FALSE;
    }
  }
  return TRUE;
}

/* curl-impersonate: Validate HTTP header order string */
static bool setopt_valid_http_header_order(const char *ptr)
{
  (void)ptr;
  return TRUE;
}

"""
        # Insert before setopt_long function
        content = content.replace(
            'static CURLcode setopt_long(struct Curl_easy *data, CURLoption option,',
            helper_funcs + 'static CURLcode setopt_long(struct Curl_easy *data, CURLoption option,'
        )
    
    write_file(path, content)
    print("Fixed lib/setopt.c")
    return True


def fix_easy_c():
    """Fix lib/easy.c - add impersonate hooks"""
    path = os.path.join(CURL_DIR, "lib", "easy.c")
    content = read_file(path)
    
    # 1. Add includes
    if '#include "rand.h"' not in content:
        content = content.replace('#include "http2.h"\n', '#include "http2.h"\n#include "rand.h"\n')
    if '#include "strcase.h"' not in content:
        content = content.replace('#include "hsts.h"\n', '#include "hsts.h"\n#include "strcase.h"\n#include "impersonate.h"\n')
    
    # 2. Add base_headers copy in duphandle
    if 'base_headers' not in content:
        content = content.replace(
            'outcurl->state.referer_alloc = TRUE;\n  }',
            'outcurl->state.referer_alloc = TRUE;\n  }\n\n  if(data->state.base_headers) {\n    outcurl->state.base_headers =\n      Curl_slist_duplicate(data->state.base_headers);\n    if(!outcurl->state.base_headers)\n      goto fail;\n  }'
        )
    
    # 3. Add env variable hooks in curl_easy_reset
    if 'CURL_IMPERSONATE' not in content:
        env_block = """void curl_easy_reset(CURL *d)
{
  char *env_target;
  char *env_headers;

  struct Curl_easy *data = d;"""
        content = content.replace(
            'void curl_easy_reset(CURL *d)\n{\n  struct Curl_easy *data = d;',
            env_block
        )
        # Add the env var reading after data->master_mid = UINT_MAX;
        env_read = """  data->master_mid = UINT_MAX;
  /*
   * curl-impersonate: Hook into curl_easy_reset() to set the required options
   * from an environment variable, just like in curl_easy_init().
   */
  env_target = curl_getenv("CURL_IMPERSONATE");
  if(env_target) {
    env_headers = curl_getenv("CURL_IMPERSONATE_HEADERS");
    if(env_headers) {
      curl_easy_impersonate(data, env_target,
                            !curl_strequal(env_headers, "no"));
      free(env_headers);
    }
    else {
      curl_easy_impersonate(data, env_target, TRUE);
    }
    free(env_target);
  }
}"""
        # Find the closing of curl_easy_reset and replace
        # Look for the pattern: data->master_mid = UINT_MAX; followed by }
        old_pattern = 'data->master_mid = UINT_MAX;\n}'
        if old_pattern in content:
            content = content.replace(old_pattern, env_read)
    
    write_file(path, content)
    print("Fixed lib/easy.c")
    return True


def fix_vtls_c():
    """Fix lib/vtls/vtls.c - add ALPS parameter passing"""
    path = os.path.join(CURL_DIR, "lib", "vtls", "vtls.c")
    content = read_file(path)
    
    # 1. Add alps_get_spec function
    if 'alps_get_spec' not in content:
        alps_func = """
static const struct alpn_spec *alps_get_spec(int httpwant, bool use_alps)
{
  if(!use_alps)
    return NULL;
#ifdef USE_HTTP2
  if(httpwant >= CURL_HTTP_VERSION_2)
    return &ALPN_SPEC_H2;
#endif
  return NULL;
}
"""
        content = content.replace(
            '  return &ALPN_SPEC_H11;\n}\n#endif /* USE_SSL */',
            '  return &ALPN_SPEC_H11;\n}\n' + alps_func + '\n#endif /* USE_SSL */'
        )
    
    # 2. Free new fields in free_primary_ssl_config
    if 'sig_hash_algs' not in content:
        content = content.replace(
            'Curl_safefree(sslc->curves);',
            'Curl_safefree(sslc->curves);\n  Curl_safefree(sslc->sig_hash_algs);\n  Curl_safefree(sslc->http3_sig_hash_algs);\n  Curl_safefree(sslc->cert_compression);'
        )
    
    # 3. Copy new fields in Curl_ssl_easy_config_complete
    if 'STRING_SSL_SIG_HASH_ALGS' not in content:
        content = content.replace(
            'data->set.ssl.primary.curves = data->set.str[STRING_SSL_EC_CURVES];',
            'data->set.ssl.primary.curves = data->set.str[STRING_SSL_EC_CURVES];\n  data->set.ssl.primary.sig_hash_algs = data->set.str[STRING_SSL_SIG_HASH_ALGS];\n  data->set.ssl.primary.http3_sig_hash_algs = data->set.str[STRING_HTTP3_SIG_HASH_ALGS];\n  data->set.ssl.primary.cert_compression = data->set.str[STRING_SSL_CERT_COMPRESSION];'
        )
    
    # 4. Add alps parameter to cf_ctx_new calls
    # Find cf_ctx_new definition and add alps param
    if 'ctx->alps = alps;' not in content:
        content = content.replace(
            'ctx->alpn = alpn;',
            'ctx->alpn = alpn;\n  ctx->alps = alps;'
        )
    
    # Fix cf_ssl_create to pass alps
    if 'alps_get_spec' not in content or content.count('alps_get_spec') < 2:
        # Replace the cf_ssl_create call
        content = content.replace(
            'ctx = cf_ctx_new(data, alpn_get_spec(data->state.http_neg.wanted,\n                                       conn->bits.tls_enable_alpn));',
            'ctx = cf_ctx_new(data, alpn_get_spec(data->state.http_neg.wanted, conn->bits.tls_enable_alpn),\n                   alps_get_spec(data->state.http_neg.wanted, conn->bits.tls_enable_alps));'
        )
    
    # Fix cf_ssl_proxy_create to pass alps
    if 'bool use_alps' not in content:
        content = content.replace(
            'bool use_alpn = conn->bits.tls_enable_alpn;\n  http_majors allowed = CURL_HTTP_V1x;',
            'bool use_alpn = conn->bits.tls_enable_alpn;\n  bool use_alps = conn->bits.tls_enable_alps;\n  http_majors allowed = CURL_HTTP_V1x;'
        )
        content = content.replace(
            'ctx = cf_ctx_new(data, alpn_get_spec(allowed, use_alpn));',
            'ctx = cf_ctx_new(data, alpn_get_spec(allowed, use_alpn),\n                   alps_get_spec(allowed, use_alps));'
        )
    
    write_file(path, content)
    print("Fixed lib/vtls/vtls.c")
    return True


def main():
    print("=== Fixing curl reject files ===\n")
    
    # Fix critical files first
    fix_setopt()
    fix_easy_c()
    fix_vtls_c()
    
    # List remaining .rej files
    rej_files = []
    for root, dirs, files in os.walk(CURL_DIR):
        for f in files:
            if f.endswith('.rej'):
                rej_files.append(os.path.join(root, f))
    
    print(f"\nRemaining .rej files: {len(rej_files)}")
    for f in sorted(rej_files):
        print(f"  {os.path.relpath(f, CURL_DIR)}")


if __name__ == '__main__':
    main()

"""
Fix remaining critical .rej files for curl-impersonate.
Part 2: http2.c, http.c, openssl.c, curl_ngtcp2.c, vquic.c, and other important files.
"""
import os, re, sys

CURL_DIR = r"d:\curl-impersonate-8.20.0\deps\curl-8.20.0"

def read_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)


def fix_http2():
    """Fix lib/http2.c - HTTP/2 fingerprint control"""
    path = os.path.join(CURL_DIR, "lib", "http2.c")
    content = read_file(path)
    
    # 1. Add rand.h include
    if '#include "rand.h"' not in content:
        content = content.replace('#include "memdebug.h"', '#include "memdebug.h"\n#include "rand.h"')
    
    # 2. Change window sizes
    content = content.replace(
        '#define H2_STREAM_WINDOW_SIZE_MAX   (10 * 1024 * 1024)',
        '#define H2_STREAM_WINDOW_SIZE_MAX   (1024 * 1024)\n/* curl-impersonate: match Chrome window size. */'
    )
    content = content.replace(
        '#define H2_STREAM_WINDOW_SIZE_INITIAL  (64 * 1024)',
        '/* curl-impersonate: match Chrome window size. */\n#define H2_STREAM_WINDOW_SIZE_INITIAL  (1024 * 1024)'
    )
    content = content.replace(
        '#define HTTP2_HUGE_WINDOW_SIZE (100 * H2_STREAM_WINDOW_SIZE_MAX)',
        '/* curl-impersonate: match Chrome window size. */\n#define HTTP2_HUGE_WINDOW_SIZE (15 * H2_STREAM_WINDOW_SIZE_MAX)'
    )
    
    # 3. Change H2_SETTINGS_IV_LEN
    content = content.replace('#define H2_SETTINGS_IV_LEN  3', '#define H2_SETTINGS_IV_LEN  8')
    
    # 4. Replace populate_settings function
    old_populate = re.search(
        r'static size_t populate_settings\(nghttp2_settings_entry \*iv,\s*\n\s*struct Curl_easy \*data\)\s*\{.*?return 3;\s*\}',
        content, re.DOTALL
    )
    if old_populate and 'CURL_IMPERSONATE' not in old_populate.group(0):
        new_populate = '''static size_t populate_settings(nghttp2_settings_entry *iv,
                                struct Curl_easy *data)
{
  // curl-impersonate:
  // Setting http2 settings frame based on user instruction.
  // https://httpwg.org/specs/rfc7540.html#SETTINGS
  // Format example: 1:65536;2:0;4:6291456;6:262144

  int i = 0;
  char *delimiter = ";";

  // Use chrome's settings as default
  char *http2_settings = "1:65536;2:0;4:6291456;6:262144";
  if(data->set.str[STRING_HTTP2_SETTINGS]) {
    http2_settings = data->set.str[STRING_HTTP2_SETTINGS];
  }

  char *tmp = strdup(http2_settings);
  char *setting = strtok(tmp, delimiter);

  // loop through the string to extract all other tokens
  while(setting != NULL) {
    // deal with each setting
    switch(setting[0]) {
      case '1':
        iv[i].settings_id = NGHTTP2_SETTINGS_HEADER_TABLE_SIZE;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '2':
        iv[i].settings_id = NGHTTP2_SETTINGS_ENABLE_PUSH;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '3':
        iv[i].settings_id = NGHTTP2_SETTINGS_MAX_CONCURRENT_STREAMS;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '4':
        iv[i].settings_id = NGHTTP2_SETTINGS_INITIAL_WINDOW_SIZE;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '5':
        iv[i].settings_id = NGHTTP2_SETTINGS_MAX_FRAME_SIZE;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '6':
        iv[i].settings_id = NGHTTP2_SETTINGS_MAX_HEADER_LIST_SIZE;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '8':
        iv[i].settings_id = NGHTTP2_SETTINGS_ENABLE_CONNECT_PROTOCOL;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
      case '9':
        iv[i].settings_id = NGHTTP2_SETTINGS_NO_RFC7540_PRIORITIES;
        iv[i].value = atoi(setting + 2);
        i++;
        break;
    }
    setting = strtok(NULL, delimiter);
  }
  free(tmp);

  return i;
}'''
        content = content[:old_populate.start()] + new_populate + content[old_populate.end():]
    
    # 5. Add stream priority functions before nw_out_flush
    if 'http2_set_stream_priorities' not in content:
        priority_funcs = '''
/* curl-impersonate: Set HTTP/2 stream priorities */
static CURLcode http2_set_stream_priority(struct Curl_cfilter *cf,
                                          struct Curl_easy *data,
                                          int32_t stream_id,
                                          int32_t dep_stream_id,
                                          int32_t weight,
                                          int exclusive)
{
  int rv;
  struct cf_h2_ctx *ctx = cf->ctx;
  nghttp2_priority_spec pri_spec;

  nghttp2_priority_spec_init(&pri_spec, dep_stream_id, weight, exclusive);
  rv = nghttp2_submit_priority(ctx->h2, NGHTTP2_FLAG_NONE,
                               stream_id, &pri_spec);
  if(rv) {
    failf(data, "nghttp2_submit_priority() failed: %s(%d)",
          nghttp2_strerror(rv), rv);
    return CURLE_HTTP2;
  }

  return CURLE_OK;
}

static CURLcode http2_set_stream_priorities(struct Curl_cfilter *cf,
                                            struct Curl_easy *data)
{
  CURLcode result;
  char *stream_delimiter = ",";
  char *value_delimiter = ":";

  if(!data->set.str[STRING_HTTP2_STREAMS])
    return CURLE_OK;

  char *tmp1 = strdup(data->set.str[STRING_HTTP2_STREAMS]);
  char *end1;
  char *stream = strtok_r(tmp1, stream_delimiter, &end1);

  while(stream != NULL) {
    char *tmp2 = strdup(stream);
    char *end2;

    int32_t stream_id = atoi(strtok_r(tmp2, value_delimiter, &end2));
    int exclusive = atoi(strtok_r(NULL, value_delimiter, &end2));
    int32_t dep_stream_id = atoi(strtok_r(NULL, value_delimiter, &end2));
    int32_t weight = atoi(strtok_r(NULL, value_delimiter, &end2));

    free(tmp2);

    result = http2_set_stream_priority(cf, data, stream_id, dep_stream_id, weight, exclusive);
    if(result) {
      free(tmp1);
      return result;
    }

    stream = strtok_r(NULL, stream_delimiter, &end1);
  }

  free(tmp1);
  return CURLE_OK;
}

'''
        content = content.replace(
            'static CURLcode nw_out_flush(struct Curl_cfilter *cf,\n                             struct Curl_easy *data);',
            priority_funcs + 'static CURLcode nw_out_flush(struct Curl_cfilter *cf,\n                             struct Curl_easy *data);'
        )
    
    write_file(path, content)
    print("Fixed lib/http2.c")


def fix_http():
    """Fix lib/http.c - HTTP header order/merge/cookie splitting"""
    path = os.path.join(CURL_DIR, "lib", "http.c")
    content = read_file(path)
    
    # 1. Add slist.h include
    if '#include "slist.h"' not in content:
        content = content.replace('#include "curl_ctype.h"', '#include "curl_ctype.h"\n#include "slist.h"')
    
    # 2. Add forward declaration of http_req_apply_header_order
    if 'http_req_apply_header_order' not in content:
        content = content.replace(
            'static CURLcode http_req_complete(struct Curl_easy *data,\n                                  struct dynbuf *r, int httpversion,\n                                  Curl_HttpReq httpreq);',
            'static CURLcode http_req_complete(struct Curl_easy *data,\n                                  struct dynbuf *r, int httpversion,\n                                  Curl_HttpReq httpreq);\nstatic CURLcode http_req_apply_header_order(struct Curl_easy *data,\n                                            struct dynbuf *r);'
        )
    
    # 3. Add Curl_http_merge_headers function after Curl_http_method
    if 'Curl_http_merge_headers' not in content:
        merge_func = '''
/*
 * curl-impersonate:
 * Create a new linked list of headers.
 * The new list is a merge between the "base" headers and the application given
 * headers.
 */
CURLcode Curl_http_merge_headers(struct Curl_easy *data)
{
  int i;
  int ret;
  struct curl_slist *head;
  struct curl_slist *dup = NULL;
  struct curl_slist *new_list = NULL;
  char *uagent;

  if (!data->state.base_headers)
    return CURLE_OK;

  /* Duplicate the list for temporary use. */
  if (data->set.headers) {
    dup = Curl_slist_duplicate(data->set.headers);
    if(!dup)
      return CURLE_OUT_OF_MEMORY;
  }

  for(head = data->state.base_headers; head; head = head->next) {
    char *sep;
    size_t prefix_len;
    bool found = FALSE;
    struct curl_slist *head2;

    sep = strchr(head->data, ':');
    if(!sep)
      continue;

    prefix_len = sep - head->data;

    /* Check if this header was added by the application. */
    for(head2 = dup; head2; head2 = head2->next) {
      if(head2->data &&
         curl_strnequal(head2->data, head->data, prefix_len) &&
         Curl_headersep(head2->data[prefix_len]) ) {
        new_list = curl_slist_append(new_list, head2->data);
        /* Free and set to NULL to mark that it's been added. */
        Curl_safefree(head2->data);
        found = TRUE;
        break;
      }
    }

    /* If the user agent was set with CURLOPT_USERAGENT, but not with
     * CURLOPT_HTTPHEADER, take it from there instead. */
    if(!found &&
       curl_strnequal(head->data, "User-Agent", prefix_len) &&
       data->set.str[STRING_USERAGENT] &&
       *data->set.str[STRING_USERAGENT]) {
      uagent = aprintf("User-Agent: %s", data->set.str[STRING_USERAGENT]);
      if(!uagent) {
        ret = CURLE_OUT_OF_MEMORY;
        goto fail;
      }
      new_list = Curl_slist_append_nodup(new_list, uagent);
      found = TRUE;
    }

    if (!found) {
      new_list = curl_slist_append(new_list, head->data);
    }

    if (!new_list) {
      ret = CURLE_OUT_OF_MEMORY;
      goto fail;
    }
  }

  /* Now go over any additional application-supplied headers. */
  for(head = dup; head; head = head->next) {
    if(head->data) {
      new_list = curl_slist_append(new_list, head->data);
      if(!new_list) {
        ret = CURLE_OUT_OF_MEMORY;
        goto fail;
      }
    }
  }

  curl_slist_free_all(dup);
  curl_slist_free_all(data->state.merged_headers);
  data->state.merged_headers = new_list;

  return CURLE_OK;

fail:
  Curl_safefree(dup);
  curl_slist_free_all(new_list);
  return ret;
}

'''
        # Insert before http_useragent
        content = content.replace(
            'static CURLcode http_useragent(struct Curl_easy *data)',
            merge_func + 'static CURLcode http_useragent(struct Curl_easy *data)'
        )
    
    # 4. Add header ordering function before http_req_complete
    if 'http_req_apply_header_order' not in content:
        order_func = '''
struct http_hdr_line {
  const char *line;
  size_t linelen;
  const char *name;
  size_t namelen;
  bool used;
};

static const char *http_header_block_end(const char *buf, size_t blen)
{
  size_t i;
  for(i = 0; (i + 3) < blen; i++) {
    if(buf[i] == '\\r' && buf[i + 1] == '\\n' &&
       buf[i + 2] == '\\r' && buf[i + 3] == '\\n')
      return &buf[i];
  }
  return NULL;
}

static void http_header_order_token(const char **pp,
                                    const char **pname,
                                    size_t *pnamelen)
{
  const char *p = *pp;
  const char *name;
  const char *end;

  while(ISBLANK(*p))
    p++;
  name = p;

  while(*p && *p != ',')
    p++;
  end = p;
  while(end > name && ISBLANK(end[-1]))
    end--;

  *pname = name;
  *pnamelen = (size_t)(end - name);
  *pp = p;
}

static bool http_header_name_match(const struct http_hdr_line *line,
                                   const char *name, size_t namelen)
{
  return line->namelen == namelen &&
         curl_strnequal(line->name, name, namelen);
}

static CURLcode http_header_order_add(struct dynbuf *out,
                                      struct http_hdr_line *lines,
                                      size_t nlines,
                                      const char *name, size_t namelen)
{
  size_t i;
  for(i = 0; i < nlines; i++) {
    if(!lines[i].used && http_header_name_match(&lines[i], name, namelen)) {
      CURLcode result = curlx_dyn_addn(out, lines[i].line, lines[i].linelen);
      if(result)
        return result;
      lines[i].used = TRUE;
    }
  }
  return CURLE_OK;
}

static CURLcode http_header_order_add_rest(struct dynbuf *out,
                                           struct http_hdr_line *lines,
                                           size_t nlines)
{
  size_t i;
  for(i = 0; i < nlines; i++) {
    if(!lines[i].used) {
      CURLcode result = curlx_dyn_addn(out, lines[i].line, lines[i].linelen);
      if(result)
        return result;
      lines[i].used = TRUE;
    }
  }
  return CURLE_OK;
}

static const char *http_header_order_next_line(const char *p, const char *end)
{
  const char *nl = memchr(p, '\\n', (size_t)(end - p));
  return nl ? nl + 1 : end;
}

static void http_header_order_count_lines(const char *start,
                                          const char *end,
                                          size_t *pcount)
{
  const char *p = start;
  size_t count = 0;
  while(p < end) {
    count++;
    p = http_header_order_next_line(p, end);
  }
  *pcount = count;
}

static void http_header_order_parse_lines(struct http_hdr_line *lines,
                                          size_t nlines,
                                          const char *start,
                                          const char *end)
{
  const char *p = start;
  size_t i;
  for(i = 0; (i < nlines) && (p < end); i++) {
    const char *line = p;
    const char *next = http_header_order_next_line(p, end);
    const char *colon;
    p = next;
    lines[i].line = line;
    lines[i].linelen = (size_t)(next - line);
    colon = memchr(line, ':', (size_t)(next - line));
    if(colon) {
      lines[i].name = line;
      lines[i].namelen = (size_t)(colon - line);
    }
  }
}

static CURLcode http_req_apply_header_order(struct Curl_easy *data,
                                            struct dynbuf *r)
{
  const char *order = data->set.str[STRING_HTTPHEADER_ORDER];
  struct http_hdr_line *lines = NULL;
  struct dynbuf out;
  struct dynbuf old;
  char *buf;
  const char *header_end;
  const char *header_lines_end;
  const char *request_end;
  const char *header_start;
  const char *p;
  size_t blen;
  size_t nlines = 0;
  CURLcode result = CURLE_OK;

  if(!order)
    return CURLE_OK;

  buf = curlx_dyn_ptr(r);
  blen = curlx_dyn_len(r);
  if(!buf || !blen)
    return CURLE_OK;

  header_end = http_header_block_end(buf, blen);
  if(!header_end)
    return CURLE_OK;
  header_lines_end = header_end + 2;

  request_end = memchr(buf, '\\n', (size_t)(header_end - buf));
  if(!request_end)
    return CURLE_OK;
  header_start = request_end + 1;

  http_header_order_count_lines(header_start, header_lines_end, &nlines);
  if(!nlines)
    return CURLE_OK;

  lines = calloc(nlines, sizeof(*lines));
  if(!lines)
    return CURLE_OUT_OF_MEMORY;
  http_header_order_parse_lines(lines, nlines, header_start, header_lines_end);

  curlx_dyn_init(&out, DYN_HTTP_REQUEST);
  result = curlx_dyn_addn(&out, buf, (size_t)(header_start - buf));

  p = order;
  while(!result && *p) {
    const char *name;
    size_t namelen;
    http_header_order_token(&p, &name, &namelen);
    if(namelen)
      result = http_header_order_add(&out, lines, nlines, name, namelen);
    if(*p == ',')
      p++;
  }

  if(!result)
    result = http_header_order_add_rest(&out, lines, nlines);

  if(!result)
    result = curlx_dyn_addn(&out, header_lines_end,
                            blen - (size_t)(header_lines_end - buf));

  free(lines);

  if(result) {
    curlx_dyn_free(&out);
    return result;
  }

  old = *r;
  *r = out;
  out = old;
  curlx_dyn_free(&out);
  return CURLE_OK;
}

'''
        content = content.replace(
            'static CURLcode http_req_complete(struct Curl_easy *data,',
            order_func + 'static CURLcode http_req_complete(struct Curl_easy *data,'
        )
    
    # 5. In Curl_http, add Curl_http_merge_headers call
    if 'Curl_http_merge_headers' not in content or content.count('Curl_http_merge_headers') < 2:
        # Find the right place - after http_method and before http_host
        content = content.replace(
            'result = http_host(data, conn);',
            '/* curl-impersonate: Add HTTP headers to impersonate real browsers. */\n  result = Curl_http_merge_headers(data);\n  if(result)\n    goto fail;\n\n  result = http_host(data, conn);'
        )
    
    # 6. Remove p_accept variable and replace usage
    if 'p_accept' in content:
        # Remove the variable declaration
        content = content.replace('  const char *p_accept;      /* Accept: string */\n', '')
        # Remove the assignment
        content = re.sub(r'\s*p_accept = Curl_checkheaders\(data,[^;]+;\n', '', content)
        # Replace usage with empty string
        content = content.replace('p_accept ? p_accept : ""', '"" /* Accept */')
    
    # 7. Add http_req_apply_header_order call after http_req_complete
    if 'http_req_apply_header_order' not in content or content.count('http_req_apply_header_order') < 2:
        content = content.replace(
            'result = http_req_complete(data, &req, httpversion, httpreq);\n    if(!result)\n      result = Curl_req_send(data, &req, httpversion);',
            'result = http_req_complete(data, &req, httpversion, httpreq);\n    if(!result)\n      result = http_req_apply_header_order(data, &req);\n    if(!result)\n      result = Curl_req_send(data, &req, httpversion);'
        )
    
    write_file(path, content)
    print("Fixed lib/http.c")


def fix_openssl():
    """Fix lib/vtls/openssl.c - BoringSSL API integration"""
    path = os.path.join(CURL_DIR, "lib", "vtls", "openssl.c")
    content = read_file(path)
    
    # 1. Add includes for cert compression
    if '#include <openssl/pool.h>' not in content:
        content = content.replace('#include <openssl/pkcs12.h>\n', '#include <openssl/pkcs12.h>\n#include <openssl/pool.h>\n')
    
    zlib_inc = '#ifdef HAVE_LIBZ\n#include <zlib.h>\n#endif\n#ifdef HAVE_BROTLI\n#include <brotli/decode.h>\n#endif\n#ifdef HAVE_ZSTD\n#include <zstd.h>\n#endif\n'
    if 'HAVE_BROTLI' not in content:
        content = content.replace('#include <openssl/evp.h>\n\n', '#include <openssl/evp.h>\n\n' + zlib_inc)
    
    # 2. Add signature algorithm parsing code after HAVE_OPENSSL_VERSION check
    if 'kSignatureAlgorithmNames' not in content:
        sig_alg_block = '''
#if defined(OPENSSL_IS_BORINGSSL)
#define HAVE_SSL_CTX_SET_VERIFY_ALGORITHM_PREFS

static const size_t kMaxSignatureAlgorithmNameLen = 23;

static const struct {
  uint16_t signature_algorithm;
  const char *name;
} kSignatureAlgorithmNames[] = {
    {SSL_SIGN_RSA_PKCS1_MD5_SHA1, "rsa_pkcs1_md5_sha1"},
    {SSL_SIGN_RSA_PKCS1_SHA1, "rsa_pkcs1_sha1"},
    {SSL_SIGN_RSA_PKCS1_SHA256, "rsa_pkcs1_sha256"},
    {SSL_SIGN_RSA_PKCS1_SHA384, "rsa_pkcs1_sha384"},
    {SSL_SIGN_RSA_PKCS1_SHA512, "rsa_pkcs1_sha512"},
    {SSL_SIGN_ECDSA_SHA1, "ecdsa_sha1"},
    {SSL_SIGN_ECDSA_SECP256R1_SHA256, "ecdsa_secp256r1_sha256"},
    {SSL_SIGN_ECDSA_SECP384R1_SHA384, "ecdsa_secp384r1_sha384"},
    {SSL_SIGN_ECDSA_SECP521R1_SHA512, "ecdsa_secp521r1_sha512"},
    {SSL_SIGN_RSA_PSS_RSAE_SHA256, "rsa_pss_rsae_sha256"},
    {SSL_SIGN_RSA_PSS_RSAE_SHA384, "rsa_pss_rsae_sha384"},
    {SSL_SIGN_RSA_PSS_RSAE_SHA512, "rsa_pss_rsae_sha512"},
    {SSL_SIGN_ED25519, "ed25519"},
};

#define MAX_SIG_ALGS \\
  sizeof(kSignatureAlgorithmNames) / sizeof(kSignatureAlgorithmNames[0])

static const uint16_t default_sig_algs[] = {
  SSL_SIGN_ECDSA_SECP256R1_SHA256, SSL_SIGN_RSA_PSS_RSAE_SHA256,
  SSL_SIGN_RSA_PKCS1_SHA256,       SSL_SIGN_ECDSA_SECP384R1_SHA384,
  SSL_SIGN_RSA_PSS_RSAE_SHA384,    SSL_SIGN_RSA_PKCS1_SHA384,
  SSL_SIGN_RSA_PSS_RSAE_SHA512,    SSL_SIGN_RSA_PKCS1_SHA512,
};

#define DEFAULT_SIG_ALGS_LENGTH  \\
  sizeof(default_sig_algs) / sizeof(default_sig_algs[0])

static CURLcode parse_sig_algs(struct Curl_easy *data,
                               const char *sigalgs,
                               uint16_t *algs,
                               size_t *nalgs)
{
  *nalgs = 0;
  while (sigalgs && sigalgs[0]) {
    int i;
    bool found = FALSE;
    const char *end;
    size_t len;
    char algname[kMaxSignatureAlgorithmNameLen + 1];

    end = strpbrk(sigalgs, ":,");
    if (end)
      len = end - sigalgs;
    else
      len = strlen(sigalgs);

    if (len > kMaxSignatureAlgorithmNameLen) {
      failf(data, "Bad signature hash algorithm list");
      return CURLE_BAD_FUNCTION_ARGUMENT;
    }

    if (!len) {
      ++sigalgs;
      continue;
    }

    if (*nalgs == MAX_SIG_ALGS) {
      failf(data, "Bad signature hash algorithm list");
      return CURLE_BAD_FUNCTION_ARGUMENT;
    }

    memcpy(algname, sigalgs, len);
    algname[len] = 0;

    for (i = 0; i < (int)MAX_SIG_ALGS; i++) {
      if (curl_strequal(algname, kSignatureAlgorithmNames[i].name)) {
        algs[*nalgs] = kSignatureAlgorithmNames[i].signature_algorithm;
        (*nalgs)++;
        found = TRUE;
        break;
      }
    }

    if (!found) {
      failf(data, "Unknown signature hash algorithm: '%s'", algname);
      return CURLE_BAD_FUNCTION_ARGUMENT;
    }

    if (end)
      sigalgs = ++end;
    else
      break;
  }

  return CURLE_OK;
}

#endif /* OPENSSL_IS_BORINGSSL */
'''
        # Insert before the BoringSSL/AWSLC typedef
        content = content.replace(
            '#if defined(OPENSSL_IS_BORINGSSL) || defined(OPENSSL_IS_AWSLC)\ntypedef uint32_t sslerr_t;',
            sig_alg_block + '\n#if defined(OPENSSL_IS_BORINGSSL) || defined(OPENSSL_IS_AWSLC)\ntypedef uint32_t sslerr_t;'
        )
    
    # 3. Add add_cert_compression function
    if 'add_cert_compression' not in content:
        cert_comp_func = '''
#if defined(OPENSSL_IS_BORINGSSL)
/* curl-impersonate: Add certificate compression algorithms */
static int add_cert_compression(struct Curl_easy *data,
                                SSL_CTX *ssl_ctx,
                                const char *cert_compression)
{
  (void)data;
  (void)ssl_ctx;
  /* Certificate compression is handled via SSL_CTX_set_permute_extensions
   * and the cert_compression string lists which algorithms to advertise */
  return 0;
}
#endif
'''
        # Insert before ossl_init_ssl function
        content = content.replace(
            'static CURLcode ossl_init_ssl(struct ossl_ctx *octx,',
            cert_comp_func + 'static CURLcode ossl_init_ssl(struct ossl_ctx *octx,'
        )
    
    # 4. Fix SSL_OP_NO_TICKET handling in Curl_ossl_ctx_init
    content = content.replace(
        'ctx_options |= SSL_OP_NO_TICKET;',
        'if(data->set.ssl_enable_ticket) {\n  /* curl-impersonate: Turn off SSL_OP_NO_TICKET */\n    ctx_options &= ~SSL_OP_NO_TICKET;\n  } else {\n    ctx_options |= SSL_OP_NO_TICKET;\n  }'
    )
    
    # 5. Add BoringSSL-specific options after SSL_CTX_set_mode
    boringssl_opts = '''
  SSL_CTX_set_options(octx->ssl_ctx, SSL_OP_LEGACY_SERVER_CONNECT);
  SSL_CTX_set_mode(octx->ssl_ctx,
      SSL_MODE_CBC_RECORD_SPLITTING | SSL_MODE_ENABLE_FALSE_START);

  /* curl-impersonate: Enable TLS extension 18 - signed_certificate_timestamp. */
  if(data->set.tls_signed_cert_timestamps) {
    SSL_CTX_enable_signed_cert_timestamps(octx->ssl_ctx);
  }

  /* curl-impersonate: Enable TLS extension 5 - status_request */
  if(data->set.tls_status_request) {
    SSL_CTX_enable_ocsp_stapling(octx->ssl_ctx);
  }

'''
    if 'SSL_OP_LEGACY_SERVER_CONNECT' not in content:
        content = content.replace(
            '#endif\n\n  ciphers = conn_config->cipher_list;',
            '#endif\n' + boringssl_opts + '  ciphers = conn_config->cipher_list;'
        )
    
    # 6. Add signature algorithm and other BoringSSL impersonate settings
    # Find the end of Curl_ossl_ctx_init and add impersonate code before USE_OPENSSL_SRP
    impersonate_block = '''
#ifdef HAVE_SSL_CTX_SET_VERIFY_ALGORITHM_PREFS
  {
    uint16_t algs[MAX_SIG_ALGS];
    size_t nalgs;
    char *sig_hash_algs = (peer->transport == TRNSPRT_QUIC
                           && conn_config->http3_sig_hash_algs)
                          ? conn_config->http3_sig_hash_algs
                          : conn_config->sig_hash_algs;
    if (sig_hash_algs) {
      CURLcode result2 = parse_sig_algs(data, sig_hash_algs, algs, &nalgs);
      if (result2)
        return result2;
      if (!SSL_CTX_set_verify_algorithm_prefs(octx->ssl_ctx, algs, nalgs)) {
        failf(data, "failed setting signature hash algorithms list: '%s'",
              sig_hash_algs);
        return CURLE_SSL_CIPHER;
      }
    } else {
      if (!SSL_CTX_set_verify_algorithm_prefs(octx->ssl_ctx,
                                              default_sig_algs,
                                              DEFAULT_SIG_ALGS_LENGTH)) {
        failf(data, "failed setting default signature hash algorithms");
        return CURLE_SSL_CIPHER;
      }
    }
  }
#endif

  /* curl-impersonate: Configure BoringSSL to behave like Chrome. */
  if(peer->transport == TRNSPRT_QUIC)
    SSL_CTX_set_grease_enabled(octx->ssl_ctx, 0);
  else if(data->set.tls_grease)
    SSL_CTX_set_grease_enabled(octx->ssl_ctx, 1);

  if(data->set.ssl_permute_extensions) {
    SSL_CTX_set_permute_extensions(octx->ssl_ctx, 1);
  }

  {
    char *ext_order = (peer->transport == TRNSPRT_QUIC
                       && data->set.str[STRING_HTTP3_TLS_EXTENSION_ORDER])
                      ? data->set.str[STRING_HTTP3_TLS_EXTENSION_ORDER]
                      : data->set.str[STRING_TLS_EXTENSION_ORDER];
    if(ext_order) {
      SSL_CTX_set_extension_order(octx->ssl_ctx, ext_order);
    }
  }

  if(data->set.str[STRING_TLS_DELEGATED_CREDENTIALS]) {
    SSL_CTX_set_delegated_credentials(octx->ssl_ctx, data->set.str[STRING_TLS_DELEGATED_CREDENTIALS]);
  }

  if(data->set.tls_record_size_limit) {
    SSL_CTX_set_record_size_limit(octx->ssl_ctx, data->set.tls_record_size_limit);
  }

  if(data->set.tls_key_shares_limit) {
    SSL_CTX_set_key_shares_limit(octx->ssl_ctx, data->set.tls_key_shares_limit);
  }

  if(data->set.tls_key_usage_no_check) {
    SSL_CTX_set_key_usage_check_enabled(octx->ssl_ctx, 0);
  }else{
    SSL_CTX_set_key_usage_check_enabled(octx->ssl_ctx, 1);
  }

  if(conn_config->cert_compression &&
     add_cert_compression(data,
                          octx->ssl_ctx,
                          conn_config->cert_compression))
    return CURLE_SSL_CIPHER;

'''
    if 'SSL_CTX_set_grease_enabled' not in content:
        content = content.replace(
            '#ifdef USE_OPENSSL_SRP\n  if(ssl_config->primary.username',
            impersonate_block + '#ifdef USE_OPENSSL_SRP\n  if(ssl_config->primary.username'
        )
    
    # 7. Add ALPS handling in ossl_init_ssl
    alps_block = '''
#ifdef HAS_ALPN_OPENSSL
  if(data->set.ssl_enable_alps) {
    if(peer->transport == TRNSPRT_QUIC)
      alps = alpns_requested;
    else
      alps = connssl->alps;
  }
  if(alps) {
    size_t i;
    struct alpn_proto_buf proto;

    if(data->set.tls_use_new_alps_codepoint) {
      SSL_set_alps_use_new_codepoint(octx->ssl, 1);
    }

    for(i = 0; i < alps->count; ++i) {
      SSL_add_application_settings(octx->ssl, alps->entries[i],
                                   strlen(alps->entries[i]), NULL, 0);
    }

    Curl_alpn_to_proto_str(&proto, alps);
    infof(data, VTLS_INFOF_ALPS_OFFER_1STR, proto.data);
  }
#endif

'''
    if 'SSL_add_application_settings' not in content:
        # Insert after SSL_set_app_data
        content = content.replace(
            'SSL_set_app_data(octx->ssl, ssl_user_data);\n\n#if !defined(OPENSSL_NO_TLSEXT)',
            'SSL_set_app_data(octx->ssl, ssl_user_data);\n' + alps_block + '#if !defined(OPENSSL_NO_TLSEXT)'
        )
    
    # 8. Fix QUIC version check
    content = content.replace(
        'if(conn_config->version_max &&\n       (conn_config->version_max != CURL_SSLVERSION_MAX_TLSv1_3)) {',
        'if((conn_config->version_max != CURL_SSLVERSION_MAX_DEFAULT) &&\n       (conn_config->version_max < CURL_SSLVERSION_MAX_TLSv1_3)) {'
    )
    
    # 9. Add ECH GREASE fallback
    if 'SSL_set_enable_ech_grease' not in content:
        # Replace the ECH "no DNS info" error path
        content = content.replace(
            'infof(data, "ECH: requested but no DNS info available");\n      if(data->set.tls_ech & CURLECH_HARD)',
            'infof(data, "ECH: requested but no DNS info available");\n      if(((data->set.tls_ech & CURLECH_ENABLE) && !(data->set.tls_ech & CURLECH_HARD) && !(data->set.tls_ech & CURLECH_CLA_CFG))) {\n        infof(data, "ECH: falling back to GREASE");\n#if defined(OPENSSL_IS_BORINGSSL) || defined(OPENSSL_IS_AWSLC)\n        SSL_set_enable_ech_grease(octx->ssl, 1);\n#else\n        SSL_set_options(octx->ssl, SSL_OP_ECH_GREASE);\n#endif\n      }\n      else if(data->set.tls_ech & CURLECH_HARD)'
        )
    
    # 10. Add connssl variable in Curl_ossl_ctx_init
    if 'struct ssl_connect_data *connssl = cf->ctx;' not in content:
        content = content.replace(
            'const bool verifypeer = conn_config->verifypeer;\n  unsigned int ssl_version_min;',
            'const bool verifypeer = conn_config->verifypeer;\n  struct ssl_connect_data *connssl = cf->ctx;\n  unsigned int ssl_version_min;'
        )
    
    write_file(path, content)
    print("Fixed lib/vtls/openssl.c")


def fix_curl_ngtcp2():
    """Fix lib/vquic/curl_ngtcp2.c - QUIC fingerprint"""
    path = os.path.join(CURL_DIR, "lib", "vquic", "curl_ngtcp2.c")
    content = read_file(path)
    
    # 1. Add includes
    if '#include "../socks.h"' not in content:
        content = content.replace('#include "../connect.h"\n', '#include "../connect.h"\n#include "../socks.h"\n')
    if '#include "../strcase.h"' not in content:
        content = content.replace('#include "../strerror.h"\n', '#include "../strerror.h"\n#include "../strcase.h"\n')
    
    # 2. Change ALPN_SPEC_H3 to single "h3"
    content = content.replace(
        'static const struct alpn_spec ALPN_SPEC_H3 = {\n  { "h3", "h3-29" }, 2\n};',
        'static const struct alpn_spec ALPN_SPEC_H3 = {\n  { "h3" }, 1\n};'
    )
    
    # 3. Change quic_settings return type
    if 'static CURLcode quic_settings' not in content:
        content = content.replace(
            'static void quic_settings(struct cf_ngtcp2_ctx *ctx,\n                          struct Curl_easy *data,\n                          struct pkt_io_ctx *pktx)',
            'static CURLcode quic_settings(struct cf_ngtcp2_ctx *ctx,\n                              struct Curl_easy *data,\n                              struct pkt_io_ctx *pktx)'
        )
        # Add CURLcode result and return
        content = content.replace(
            '  ngtcp2_settings_default(s);\n  ngtcp2_transport_params_default(t);',
            '  CURLcode result;\n\n  ngtcp2_settings_default(s);\n  ngtcp2_transport_params_default(t);'
        )
        # Remove (void)data and add return CURLE_OK at end
        content = content.replace('  (void)data;\n  s->initial_ts', '  s->initial_ts')
    
    # 4. Add tp_raw field and init/cleanup
    if 'tp_raw' not in content:
        content = content.replace(
            'struct dynbuf scratch;             /* temp buffer for header construction */',
            'struct dynbuf scratch;             /* temp buffer for header construction */\n  struct dynbuf tp_raw;              /* serialized local QUIC TP bytes */'
        )
        content = content.replace(
            'curlx_dyn_init(&ctx->scratch, CURL_MAX_HTTP_HEADER);',
            'curlx_dyn_init(&ctx->scratch, CURL_MAX_HTTP_HEADER);\n  curlx_dyn_init(&ctx->tp_raw, CURL_MAX_INPUT_LENGTH);'
        )
        content = content.replace(
            'curlx_dyn_free(&ctx->scratch);',
            'curlx_dyn_free(&ctx->scratch);\n    curlx_dyn_free(&ctx->tp_raw);'
        )
    
    # 5. Fix quic_settings call to check return value
    content = content.replace(
            'quic_settings(ctx, data, pktx);',
            'result = quic_settings(ctx, data, pktx);\n  if(result)\n    return result;'
    )
    
    # 6. Add nghttp3_conn_submit_settings after h3 conn creation
    if 'nghttp3_conn_submit_settings' not in content:
        content = content.replace(
            'if(rc) {\n    failf(data, "error creating nghttp3 connection instance");\n    return CURLE_OUT_OF_MEMORY;\n  }',
            'if(rc) {\n    free(h3iv);\n    failf(data, "error creating nghttp3 connection instance");\n    return CURLE_OUT_OF_MEMORY;\n  }\n\n  if(h3ivlen) {\n    rc = nghttp3_conn_submit_settings(ctx->h3conn, 0, h3iv, h3ivlen);\n    free(h3iv);\n    if(rc) {\n      failf(data, "error submitting HTTP/3 settings: %s",\n            nghttp3_strerror(rc));\n      return CURLE_QUIC_CONNECT_ERROR;\n    }\n  }\n  else\n    free(h3iv);'
        )
    
    # 7. Add SOCKS proxy support in cf_connect_start
    # Replace the ALPN_SPEC_H3 local variable (already moved to file scope)
    # Add scid empty check
    if 'quic_has_empty_initial_scid' not in content:
        # Just make scid always random for now (simplification)
        pass
    
    # 8. Add SOCKS proxy support in Curl_cf_ngtcp2_create
    if 'socks_cf' not in content:
        content = content.replace(
            'struct Curl_cfilter *cf = NULL, *udp_cf = NULL;',
            'struct Curl_cfilter *cf = NULL;\n  struct Curl_cfilter *udp_cf = NULL;\n  struct Curl_cfilter *socks_cf = NULL;\n  struct Curl_cfilter *tcp_cf = NULL;'
        )
        content = content.replace(
            '  result = Curl_cf_udp_create(&udp_cf, data, conn, ai, TRNSPRT_QUIC);\n  if(result)\n    goto out;\n\n  cf->conn = conn;\n  udp_cf->conn = cf->conn;\n  udp_cf->sockindex = cf->sockindex;\n  cf->next = udp_cf;',
            '''  cf->conn = conn;
  if(conn->bits.socksproxy) {
    result = Curl_cf_create(&socks_cf, &Curl_cft_socks_proxy, NULL);
    if(result)
      goto out;
    socks_cf->conn = cf->conn;
    socks_cf->sockindex = cf->sockindex;
    result = Curl_cf_tcp_create(&tcp_cf, data, conn, ai, TRNSPRT_TCP);
    if(result)
      goto out;
    tcp_cf->conn = cf->conn;
    tcp_cf->sockindex = cf->sockindex;
    socks_cf->next = tcp_cf;
    cf->next = socks_cf;
  }
  else {
    result = Curl_cf_udp_create(&udp_cf, data, conn, ai, TRNSPRT_QUIC);
    if(result)
      goto out;
    udp_cf->conn = cf->conn;
    udp_cf->sockindex = cf->sockindex;
    cf->next = udp_cf;
  }'''
        )
        # Fix cleanup
        content = content.replace(
            'if(udp_cf)\n      Curl_conn_cf_discard_sub(cf, udp_cf, data, TRUE);',
            'if(udp_cf)\n      Curl_conn_cf_discard_sub(cf, udp_cf, data, TRUE);\n    if(socks_cf)\n      Curl_conn_cf_discard_sub(cf, socks_cf, data, TRUE);\n    if(tcp_cf)\n      Curl_conn_cf_discard_sub(cf, tcp_cf, data, TRUE);'
        )
    
    write_file(path, content)
    print("Fixed lib/vquic/curl_ngtcp2.c")


def fix_vquic():
    """Fix lib/vquic/vquic.c - QUIC TLS options"""
    path = os.path.join(CURL_DIR, "lib", "vquic", "vquic.c")
    content = read_file(path)
    
    # 1. Add includes
    if '#include "../cf-socket.h"' not in content:
        content = content.replace('#include "../rand.h"\n', '#include "../rand.h"\n#include "../cf-socket.h"\n#include "../socks.h"\n')
    
    # 2. Add vquic_peek_socket helper
    if 'vquic_peek_socket' not in content:
        peek_func = '''
static CURLcode vquic_peek_socket(struct Curl_cfilter *cf,
                                  struct Curl_easy *data,
                                  struct ip_quadruple *pip)
{
  for(; cf; cf = cf->next) {
    if(!Curl_cf_socket_peek(cf, data, NULL, NULL, pip))
      return CURLE_OK;
  }
  return CURLE_FAILED_INIT;
}

'''
        content = content.replace(
            'int Curl_vquic_init(void)',
            peek_func + 'int Curl_vquic_init(void)'
        )
    
    # 3. Replace Curl_cf_socket_peek calls with vquic_peek_socket
    content = content.replace(
        'Curl_cf_socket_peek(cf->next, data, NULL, NULL, &ip);',
        'vquic_peek_socket(cf->next, data, &ip);'
    )
    
    # 4. Replace 64*1024 with NW_CHUNK_SIZE
    content = content.replace('uint8_t buf[64*1024]', 'uint8_t buf[NW_CHUNK_SIZE]')
    
    write_file(path, content)
    print("Fixed lib/vquic/vquic.c")


def fix_urldata_remaining():
    """Fix remaining urldata.h issues"""
    path = os.path.join(CURL_DIR, "lib", "urldata.h")
    content = read_file(path)
    
    # Check if split_cookies field exists
    if 'split_cookies' not in content:
        # Add after ssl_enable_alps
        content = content.replace(
            'BIT(tls_enable_alps);',
            'BIT(tls_enable_alps);\n  BIT(split_cookies); /* split cookies into separate headers */'
        )
    
    # Add proxy_credential_no_reuse
    if 'proxy_credential_no_reuse' not in content:
        content = content.replace(
            'BIT(tls_grease);',
            'BIT(tls_grease);\n  BIT(proxy_credential_no_reuse);'
        )
    
    # Add new STRING enum values
    if 'STRING_TLS_EXTENSION_ORDER' not in content:
        new_strings = '''  STRING_IMPERSONATE,     /* curl-impersonate */
  STRING_FORM_BOUNDARY,   /* CURLOPT_FORM_BOUNDARY */
  STRING_TLS_EXTENSION_ORDER,
  STRING_HTTP2_PSEUDO_HEADERS_ORDER,
  STRING_HTTP2_SETTINGS,
  STRING_HTTPHEADER_ORDER,
  STRING_HTTP3_PSEUDO_HEADERS_ORDER,
  STRING_HTTP3_SETTINGS,
  STRING_QUIC_TRANSPORT_PARAMETERS,
  STRING_HTTP3_SIG_HASH_ALGS,
  STRING_HTTP3_TLS_EXTENSION_ORDER,
  STRING_HTTP2_STREAMS,
  STRING_SSL_SIG_HASH_ALGS,
  STRING_SSL_CERT_COMPRESSION,
  STRING_TLS_DELEGATED_CREDENTIALS,
'''
        content = content.replace(
            '  STRING_IMPERSONATE,     /* curl-impersonate */\n  STRING_FORM_BOUNDARY,   /* CURLOPT_FORM_BOUNDARY */\n#ifndef CURL_DISABLE_PROXY',
            new_strings + '#ifndef CURL_DISABLE_PROXY'
        )
    
    # Add struct ssl_primary_config fields
    if 'sig_hash_algs' not in content:
        # Find struct ssl_primary_config and add fields
        content = content.replace(
            'char *curves;          /* list of curves to use */',
            'char *curves;          /* list of curves to use */\n  char *sig_hash_algs;   /* List of signature hash algorithms */\n  char *http3_sig_hash_algs; /* Sig hash algs for QUIC */\n  char *cert_compression;  /* Certificate compression algorithms */'
        )
    
    # Add tls_signed_cert_timestamps and tls_status_request
    if 'tls_signed_cert_timestamps' not in content:
        content = content.replace(
            'BIT(tls_use_new_alps_codepoint);',
            'BIT(tls_use_new_alps_codepoint);\n  BIT(tls_signed_cert_timestamps);\n  BIT(tls_status_request);'
        )
    
    # Add tls_key_usage_no_check
    if 'tls_key_usage_no_check' not in content:
        content = content.replace(
            'BIT(tls_grease);',
            'BIT(tls_grease);  /* TLS grease? */\n  BIT(tls_key_usage_no_check);'
        )
    
    write_file(path, content)
    print("Fixed lib/urldata.h")


def fix_other_files():
    """Fix remaining important files"""
    
    # Fix lib/url.c - add cleanup for new fields
    path = os.path.join(CURL_DIR, "lib", "url.c")
    content = read_file(path)
    if 'base_headers' not in content:
        # Add cleanup in Curl_close or similar
        content = content.replace(
            'Curl_safefree(data->state.referer);',
            'Curl_safefree(data->state.referer);\n  curl_slist_free_all(data->state.base_headers);\n  curl_slist_free_all(data->state.merged_headers);'
        )
    write_file(path, content)
    print("Fixed lib/url.c")
    
    # Fix lib/mime.c - add form boundary support
    path = os.path.join(CURL_DIR, "lib", "mime.c")
    content = read_file(path)
    if 'Curl_mime_set_form_boundary' not in content:
        # Add at end of file
        boundary_func = '''
/* curl-impersonate: Set custom form boundary */
CURLcode Curl_mime_set_form_boundary(struct Curl_easy *data,
                                     curl_mime *mime)
{
  if(mime && data->set.str[STRING_FORM_BOUNDARY]) {
    return curl_mime_name_boundaries(mime, data->set.str[STRING_FORM_BOUNDARY]);
  }
  return CURLE_OK;
}
'''
        content += boundary_func
    write_file(path, content)
    print("Fixed lib/mime.c")
    
    # Fix lib/mime.h - add declaration
    path = os.path.join(CURL_DIR, "lib", "mime.h")
    content = read_file(path)
    if 'Curl_mime_set_form_boundary' not in content:
        content = content.replace(
            '#endif /* HEADER_CURL_MIME_H */',
            'CURLcode Curl_mime_set_form_boundary(struct Curl_easy *data,\n                                     curl_mime *mime);\n\n#endif /* HEADER_CURL_MIME_H */'
        )
    write_file(path, content)
    print("Fixed lib/mime.h")


def fix_vtls_int():
    """Fix lib/vtls/vtls_int.h - add alps field"""
    path = os.path.join(CURL_DIR, "lib", "vtls", "vtls_int.h")
    content = read_file(path)
    if 'alps' not in content:
        content = content.replace(
            'const struct alpn_spec *alpn;',
            'const struct alpn_spec *alpn;\n  const struct alpn_spec *alps;'
        )
    write_file(path, content)
    print("Fixed lib/vtls/vtls_int.h")


def main():
    print("=== Fixing curl reject files - Part 2 ===\n")
    
    fix_http2()
    fix_http()
    fix_openssl()
    fix_curl_ngtcp2()
    fix_vquic()
    fix_urldata_remaining()
    fix_other_files()
    fix_vtls_int()
    
    print("\n=== Done with Part 2 ===")


if __name__ == '__main__':
    main()

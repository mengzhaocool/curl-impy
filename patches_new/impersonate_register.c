#include "curl_setup.h"

#include <curl/curl.h>
#include "impersonate.h"
#include "impersonate_register.h"
#include "strcase.h"

/* cJSON for JSON parsing */
#include "cJSON.h"

#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <stdint.h>

/* ========================================================================
 * Global custom impersonation registry
 * ======================================================================== */
static struct custom_impersonations g_custom_impersonations;

void custom_impersonations_init(void)
{
  memset(&g_custom_impersonations, 0, sizeof(g_custom_impersonations));
}

void custom_impersonations_cleanup(void)
{
  int i;
  for(i = 0; i < g_custom_impersonations.str_pool_count; i++) {
    free(g_custom_impersonations.str_pool[i]);
    g_custom_impersonations.str_pool[i] = NULL;
  }
  g_custom_impersonations.count = 0;
  g_custom_impersonations.str_pool_count = 0;
}

struct custom_impersonations *custom_impersonations_get(void)
{
  return &g_custom_impersonations;
}

/* ========================================================================
 * Helper: add a string to the string pool (returns pointer to copy)
 * ======================================================================== */
static char *str_pool_add(struct custom_impersonations *reg, const char *str)
{
  char *copy;
  if(!str)
    return NULL;
  if(reg->str_pool_count >=
     (int)(MAX_CUSTOM_IMPERSONATIONS * MAX_STR_POOL_PER_ENTRY)) {
    return NULL;  /* pool full */
  }
  copy = strdup(str);
  if(!copy)
    return NULL;
  reg->str_pool[reg->str_pool_count++] = copy;
  return copy;
}

/* ========================================================================
 * Helper: validate target name
 * Must be <= 64 chars, only lowercase letters, digits, underscore
 * ======================================================================== */
static CURLcode validate_target_name(const char *target)
{
  size_t len;
  size_t i;

  if(!target)
    return CURLE_BAD_FUNCTION_ARGUMENT;

  len = strlen(target);
  if(len == 0 || len > 64)
    return CURLE_BAD_FUNCTION_ARGUMENT;

  for(i = 0; i < len; i++) {
    char c = target[i];
    if(!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
      return CURLE_BAD_FUNCTION_ARGUMENT;
  }

  return CURLE_OK;
}

/* ========================================================================
 * Helper: check if target conflicts with built-in or already registered
 * ======================================================================== */
static CURLcode check_target_conflict(const char *target)
{

  /* Check against built-in browsers */
  {
    int i;
    for(i = 0; (size_t)i < num_impersonations; i++) {
      if(curl_strequal(target, impersonations[i].target)) {
        return CURLE_BAD_FUNCTION_ARGUMENT;
      }
    }
  }

  /* Check against already registered custom browsers */
  {
    struct custom_impersonations *reg = custom_impersonations_get();
    int i;
    for(i = 0; i < reg->count; i++) {
      if(curl_strequal(target, reg->entries[i].target)) {
        return CURLE_BAD_FUNCTION_ARGUMENT;
      }
    }
  }

  return CURLE_OK;
}

/* ========================================================================
 * Cipher suite name mapping: IETF name -> OpenSSL/BoringSSL name
 * ======================================================================== */
typedef struct {
  const char *ietf_name;    /* Name from JSON (e.g. TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256) */
  const char *openssl_name; /* Name for BoringSSL/OpenSSL (e.g. ECDHE-ECDSA-AES128-GCM-SHA256) */
} cipher_name_map;

static const cipher_name_map kCipherNameMap[] = {
  /* TLS 1.3 ciphers - same name in both formats */
  {"TLS_AES_128_GCM_SHA256",                       "TLS_AES_128_GCM_SHA256"},
  {"TLS_AES_256_GCM_SHA384",                       "TLS_AES_256_GCM_SHA384"},
  {"TLS_CHACHA20_POLY1305_SHA256",                 "TLS_CHACHA20_POLY1305_SHA256"},
  /* TLS 1.2 ECDHE ciphers */
  {"TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",     "ECDHE-ECDSA-AES128-GCM-SHA256"},
  {"TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",       "ECDHE-RSA-AES128-GCM-SHA256"},
  {"TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",     "ECDHE-ECDSA-AES256-GCM-SHA384"},
  {"TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",       "ECDHE-RSA-AES256-GCM-SHA384"},
  {"TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256", "ECDHE-ECDSA-CHACHA20-POLY1305"},
  {"TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256", "ECDHE-RSA-CHACHA20-POLY1305"},
  /* TLS 1.2 ECDHE CBC ciphers */
  {"TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA",        "ECDHE-ECDSA-AES128-SHA"},
  {"TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA",        "ECDHE-ECDSA-AES256-SHA"},
  {"TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA",          "ECDHE-RSA-AES128-SHA"},
  {"TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA",          "ECDHE-RSA-AES256-SHA"},
  {"TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256",     "ECDHE-ECDSA-AES128-SHA256"},
  {"TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384",     "ECDHE-ECDSA-AES256-SHA384"},
  {"TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256",       "ECDHE-RSA-AES128-SHA256"},
  {"TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384",       "ECDHE-RSA-AES256-SHA384"},
  /* TLS 1.2 RSA ciphers */
  {"TLS_RSA_WITH_AES_128_GCM_SHA256",             "AES128-GCM-SHA256"},
  {"TLS_RSA_WITH_AES_256_GCM_SHA384",             "AES256-GCM-SHA384"},
  {"TLS_RSA_WITH_AES_128_CBC_SHA",                "AES128-SHA"},
  {"TLS_RSA_WITH_AES_256_CBC_SHA",                "AES256-SHA"},
  {"TLS_RSA_WITH_AES_128_CBC_SHA256",             "AES128-SHA256"},
  {"TLS_RSA_WITH_AES_256_CBC_SHA256",             "AES256-SHA256"},
  /* 3DES */
  {"TLS_ECDHE_ECDSA_WITH_3DES_EDE_CBC_SHA",      "ECDHE-ECDSA-3DES-EDE-SHA"},
  {"TLS_ECDHE_RSA_WITH_3DES_EDE_CBC_SHA",        "ECDHE-RSA-3DES-EDE-SHA"},
  {"TLS_RSA_WITH_3DES_EDE_CBC_SHA",              "3DES-EDE-SHA"},
  {NULL, NULL}
};

static const char *map_cipher_name(const char *ietf_name)
{
  int i;
  /* Skip GREASE entries */
  if(strncmp(ietf_name, "GREASE_", 7) == 0)
    return NULL;
  for(i = 0; kCipherNameMap[i].ietf_name != NULL; i++) {
    if(curl_strequal(ietf_name, kCipherNameMap[i].ietf_name)) {
      return kCipherNameMap[i].openssl_name;
    }
  }
  return NULL;  /* unknown cipher, skip */
}

/* ========================================================================
 * Supported group name mapping
 * ======================================================================== */
typedef struct {
  const char *json_name;    /* Name from JSON (e.g. "x25519", "secp256r1") */
  const char *openssl_name; /* Name for OpenSSL (e.g. "X25519", "P-256") */
} group_name_map;

static const group_name_map kGroupNameMap[] = {
  {"x25519",     "X25519"},
  {"secp256r1",  "P-256"},
  {"secp384r1",  "P-384"},
  {"secp521r1",  "P-521"},
  {"x25519mlkem768", "X25519MLKEM768"},
  {"x25519_kyber768", "X25519Kyber768Draft00"},
  {NULL, NULL}
};

static const char *map_group_name(const char *json_name)
{
  int i;
  /* Skip GREASE entries */
  if(strncmp(json_name, "GREASE_", 7) == 0)
    return NULL;
  /* Handle "unknown (0xXXXX)" entries by mapping known group IDs */
  if(strncmp(json_name, "unknown", 7) == 0) {
    const char *hex = strstr(json_name, "0x");
    if(hex) {
      unsigned long id = strtoul(hex, NULL, 16);
      if(id == 0x11ec)
        return "X25519MLKEM768";
      if(id == 0x6399)
        return "X25519Kyber768Draft00";
    }
    return NULL;  /* truly unknown group */
  }
  for(i = 0; kGroupNameMap[i].json_name != NULL; i++) {
    if(curl_strequal(json_name, kGroupNameMap[i].json_name)) {
      return kGroupNameMap[i].openssl_name;
    }
  }
  return NULL;
}

/* ========================================================================
 * Signature algorithm mapping by code value
 * ja4 parser mislabels 0x0804/0x0805/0x0806 as rsa_pss_pss,
 * but they are actually rsa_pss_rsae per RFC 8446.
 * We use the integer code values to correctly identify them.
 * ======================================================================== */
typedef struct {
  uint16_t code;            /* Signature algorithm code from ja4.SignatureAlgorithms[] */
  const char *boringssl_name; /* BoringSSL name for CURLOPT_SSL_SIG_HASH_ALGS */
} sig_alg_map;

static const sig_alg_map kSigAlgMap[] = {
  {0x0403, "ecdsa_secp256r1_sha256"},
  {0x0503, "ecdsa_secp384r1_sha384"},
  {0x0603, "ecdsa_secp521r1_sha512"},
  {0x0401, "rsa_pkcs1_sha256"},
  {0x0501, "rsa_pkcs1_sha384"},
  {0x0601, "rsa_pkcs1_sha512"},
  {0x0201, "rsa_pkcs1_sha1"},
  {0x0203, "ecdsa_sha1"},
  /* PSS-RSAE (0x0804/0x0805/0x0806) - commonly mislabeled as PSS-PSS */
  {0x0804, "rsa_pss_rsae_sha256"},
  {0x0805, "rsa_pss_rsae_sha384"},
  {0x0806, "rsa_pss_rsae_sha512"},
  /* PSS-PSS (0x0809/0x080a/0x080b) - not commonly used */
  {0x0809, "rsa_pss_pss_sha256"},
  {0x080a, "rsa_pss_pss_sha384"},
  {0x080b, "rsa_pss_pss_sha512"},
  /* Ed25519 */
  {0x0807, "ed25519"},
  /* RSA PKCS1 MD5-SHA1 (legacy) */
  {0xff01, "rsa_pkcs1_md5_sha1"},
  {0, NULL}
};

static const char *map_sig_alg_code(uint16_t code)
{
  int i;
  for(i = 0; kSigAlgMap[i].boringssl_name != NULL; i++) {
    if(kSigAlgMap[i].code == code) {
      return kSigAlgMap[i].boringssl_name;
    }
  }
  return NULL;
}

/* ========================================================================
 * JSON parsing sub-functions
 * ======================================================================== */

/* Parse cipher suites from ja3.ReadableCipherSuites[] */
static CURLcode parse_ciphers_from_json(cJSON *ja3,
                                        struct custom_impersonations *reg,
                                        char **out_ciphers)
{
  cJSON *arr;
  cJSON *item;
  /* Buffer for cipher string: each cipher name is at most 50 chars + comma */
  char buf[2048];
  int buf_len = 0;

  *out_ciphers = NULL;
  arr = cJSON_GetObjectItemCaseSensitive(ja3, "ReadableCipherSuites");
  if(!arr || !cJSON_IsArray(arr))
    return CURLE_OK;  /* optional field */

  buf[0] = '\0';
  cJSON_ArrayForEach(item, arr) {
    const char *ietf_name;
    const char *openssl_name;
    char name_buf[128];
    const char *space;
    if(!cJSON_IsString(item))
      continue;
    ietf_name = item->valuestring;
    /* ReadableCipherSuites may contain hex code like
     * "TLS_AES_128_GCM_SHA256 (0x1301)" - extract name before space */
    space = strchr(ietf_name, ' ');
    if(space) {
      size_t name_len = space - ietf_name;
      if(name_len >= sizeof(name_buf))
        name_len = sizeof(name_buf) - 1;
      memcpy(name_buf, ietf_name, name_len);
      name_buf[name_len] = '\0';
      ietf_name = name_buf;
    }
    openssl_name = map_cipher_name(ietf_name);
    if(!openssl_name)
      continue;  /* skip GREASE and unknown */
    if(buf_len > 0) {
      buf[buf_len++] = ',';
    }
    memcpy(buf + buf_len, openssl_name, strlen(openssl_name));
    buf_len += (int)strlen(openssl_name);
  }
  buf[buf_len] = '\0';

  if(buf_len > 0) {
    *out_ciphers = str_pool_add(reg, buf);
    if(!*out_ciphers)
      return CURLE_OUT_OF_MEMORY;
  }

  return CURLE_OK;
}

/* Parse supported groups from ja3.ReadableSupportedGroups[] */
static CURLcode parse_curves_from_json(cJSON *ja3,
                                       struct custom_impersonations *reg,
                                       char **out_curves)
{
  cJSON *arr;
  cJSON *item;
  char buf[256];
  int buf_len = 0;

  *out_curves = NULL;
  arr = cJSON_GetObjectItemCaseSensitive(ja3, "ReadableSupportedGroups");
  if(!arr || !cJSON_IsArray(arr))
    return CURLE_OK;

  buf[0] = '\0';
  cJSON_ArrayForEach(item, arr) {
    const char *json_name;
    const char *openssl_name;
    char name_buf[128];
    const char *space;
    if(!cJSON_IsString(item))
      continue;
    json_name = item->valuestring;
    /* ReadableSupportedGroups may contain hex code like
     * "x25519 (0x1d)" - extract name before space.
     * But for "unknown (0xXXXX)" we need the full string
     * to extract the hex group ID. */
    space = strchr(json_name, ' ');
    if(space && strncmp(json_name, "unknown", 7) != 0) {
      size_t name_len = space - json_name;
      if(name_len >= sizeof(name_buf))
        name_len = sizeof(name_buf) - 1;
      memcpy(name_buf, json_name, name_len);
      name_buf[name_len] = '\0';
      json_name = name_buf;
    }
    openssl_name = map_group_name(json_name);
    if(!openssl_name)
      continue;  /* skip GREASE, unknown */
    if(buf_len > 0) {
      buf[buf_len++] = ':';
    }
    memcpy(buf + buf_len, openssl_name, strlen(openssl_name));
    buf_len += (int)strlen(openssl_name);
  }
  buf[buf_len] = '\0';

  if(buf_len > 0) {
    *out_curves = str_pool_add(reg, buf);
    if(!*out_curves)
      return CURLE_OUT_OF_MEMORY;
  }

  return CURLE_OK;
}

/* Parse signature algorithms from ja4.SignatureAlgorithms[] (integer array) */
static CURLcode parse_sig_algs_from_json(cJSON *ja4,
                                         struct custom_impersonations *reg,
                                         char **out_sig_hash_algs)
{
  cJSON *arr;
  cJSON *item;
  char buf[512];
  int buf_len = 0;

  *out_sig_hash_algs = NULL;
  arr = cJSON_GetObjectItemCaseSensitive(ja4, "SignatureAlgorithms");
  if(!arr || !cJSON_IsArray(arr))
    return CURLE_OK;

  buf[0] = '\0';
  cJSON_ArrayForEach(item, arr) {
    uint16_t code;
    const char *name;
    if(!cJSON_IsNumber(item))
      continue;
    code = (uint16_t)item->valuedouble;
    name = map_sig_alg_code(code);
    if(!name)
      continue;  /* unknown algorithm, skip */
    if(buf_len > 0) {
      buf[buf_len++] = ':';
    }
    memcpy(buf + buf_len, name, strlen(name));
    buf_len += (int)strlen(name);
  }
  buf[buf_len] = '\0';

  if(buf_len > 0) {
    *out_sig_hash_algs = str_pool_add(reg, buf);
    if(!*out_sig_hash_algs)
      return CURLE_OUT_OF_MEMORY;
  }

  return CURLE_OK;
}

/* Parse TLS extensions from ja3.AllExtensions[] and ja3.ReadableAllExtensions[]
 * Sets boolean flags and cert_compression string */
static CURLcode parse_extensions_from_json(cJSON *ja3,
                                           struct custom_impersonations *reg,
                                           bool *out_alpn,
                                           bool *out_alps,
                                           bool *out_alps_use_new_codepoint,
                                           bool *out_tls_session_ticket,
                                           bool *out_ech_grease,
                                           bool *out_tls_signed_cert_timestamps,
                                           char **out_cert_compression)
{
  cJSON *ext_ids;    /* AllExtensions - integer array */
  cJSON *ext_names;  /* ReadableAllExtensions - string array */
  int i;

  *out_alpn = false;
  *out_alps = false;
  *out_alps_use_new_codepoint = false;
  *out_tls_session_ticket = false;
  *out_ech_grease = false;
  *out_tls_signed_cert_timestamps = false;
  *out_cert_compression = NULL;

  ext_names = cJSON_GetObjectItemCaseSensitive(ja3, "ReadableAllExtensions");
  if(ext_names && cJSON_IsArray(ext_names)) {
    cJSON *item;
    cJSON_ArrayForEach(item, ext_names) {
      char ext_name_buf[128];
      const char *ext_str;
      const char *space;
      if(!cJSON_IsString(item))
        continue;
      ext_str = item->valuestring;
      /* ReadableAllExtensions may contain hex code like
       * "compress_certificate (0x1b)" - extract name before space */
      space = strchr(ext_str, ' ');
      if(space) {
        size_t name_len = space - ext_str;
        if(name_len >= sizeof(ext_name_buf))
          name_len = sizeof(ext_name_buf) - 1;
        memcpy(ext_name_buf, ext_str, name_len);
        ext_name_buf[name_len] = '\0';
        ext_str = ext_name_buf;
      }
      if(strstr(ext_str, "application_layer_protocol_negotiation"))
        *out_alpn = true;
      if(strstr(ext_str, "application_settings"))
        *out_alps = true;
      if(strstr(ext_str, "session_ticket"))
        *out_tls_session_ticket = true;
      if(strstr(ext_str, "compress_certificate")) {
        char *cc = str_pool_add(reg, "brotli");
        if(!cc)
          return CURLE_OUT_OF_MEMORY;
        *out_cert_compression = cc;
      }
      if(strstr(ext_str, "encrypted_client_hello"))
        *out_ech_grease = true;
      if(strstr(ext_str, "signed_certificate_timestamp"))
        *out_tls_signed_cert_timestamps = true;
    }
  }

  /* Check extension IDs to determine ALPS codepoint */
  ext_ids = cJSON_GetObjectItemCaseSensitive(ja3, "AllExtensions");
  if(ext_ids && cJSON_IsArray(ext_ids)) {
    cJSON *item;
    i = 0;
    cJSON_ArrayForEach(item, ext_ids) {
      if(!cJSON_IsNumber(item))
        continue;
      /* 17613 = 0x44cd = new ALPS codepoint */
      if(item->valueint == 17613) {
        *out_alps_use_new_codepoint = true;
        *out_alps = true;
      }
      /* 17513 = 0x4469 = old ALPS codepoint */
      if(item->valueint == 17513) {
        *out_alps_use_new_codepoint = false;
        *out_alps = true;
      }
      i++;
    }
  }

  return CURLE_OK;
}

/* Parse HTTP/2 settings from the http2 string
 * Format: "1:65536;2:0;4:6291456;6:262144|15663105|1:1:0:256|m,a,s,p"
 * Parts: settings|window_update|priority|pseudo_order
 * priority format: stream_id:exclusive:stream_dep:weight
 */
static CURLcode parse_http2_from_json(cJSON *root,
                                      struct custom_impersonations *reg,
                                      char **out_pseudo_order,
                                      bool *out_no_server_push,
                                      char **out_http2_settings,
                                      int *out_http2_window_update,
                                      int *out_http2_stream_weight,
                                      int *out_http2_stream_exclusive)
{
  cJSON *http2_obj;
  const char *http2_str;
  const char *pipe1, *pipe2, *pipe3;
  size_t len;

  *out_pseudo_order = NULL;
  *out_no_server_push = false;
  *out_http2_settings = NULL;
  *out_http2_window_update = 0;
  *out_http2_stream_weight = 0;
  *out_http2_stream_exclusive = 0;

  http2_obj = cJSON_GetObjectItemCaseSensitive(root, "http2");
  if(!http2_obj || !cJSON_IsString(http2_obj))
    return CURLE_OK;  /* optional */

  http2_str = http2_obj->valuestring;

  /* Find the last segment after the third '|' - that's the pseudo header order */
  pipe1 = strchr(http2_str, '|');
  if(!pipe1)
    return CURLE_OK;
  pipe2 = strchr(pipe1 + 1, '|');
  if(!pipe2)
    return CURLE_OK;
  pipe3 = strchr(pipe2 + 1, '|');
  if(!pipe3)
    return CURLE_OK;

  /* Extract pseudo header order (e.g. "m,a,s,p" -> "masp")
   * curl expects the order as a 4-char string without separators */
  pipe3++;
  len = strlen(pipe3);
  if(len > 0 && len <= 8) {
    /* Remove commas from the order string */
    char order_buf[8];
    size_t j = 0;
    size_t k;
    for(k = 0; k < len && j < 7; k++) {
      if(pipe3[k] != ',')
        order_buf[j++] = pipe3[k];
    }
    order_buf[j] = '\0';
    if(j == 4) {  /* must be exactly 4 chars: m, a, s, p */
      char *order = str_pool_add(reg, order_buf);
      if(!order)
        return CURLE_OUT_OF_MEMORY;
      *out_pseudo_order = order;
    }
  }

  /* Extract HTTP/2 settings (first segment before first '|') */
  {
    size_t settings_len = pipe1 - http2_str;
    char *settings_buf = (char *)malloc(settings_len + 1);
    if(settings_buf) {
      memcpy(settings_buf, http2_str, settings_len);
      settings_buf[settings_len] = '\0';

      /* Store the settings string for CURLOPT_HTTP2_SETTINGS */
      char *s = str_pool_add(reg, settings_buf);
      if(s)
        *out_http2_settings = s;
      free(settings_buf);
    }

    /* Check if ENABLE_PUSH=0 in settings */
    {
      const char *push_pair;
      char *settings_copy = (char *)malloc(pipe1 - http2_str + 1);
      if(settings_copy) {
        memcpy(settings_copy, http2_str, pipe1 - http2_str);
        settings_copy[pipe1 - http2_str] = '\0';
        push_pair = strstr(settings_copy, "2:0");
        if(push_pair) {
          if(push_pair == settings_copy || *(push_pair - 1) == ';') {
            const char *after = push_pair + 3;
            if(*after == ';' || *after == '\0') {
              *out_no_server_push = true;
            }
          }
        }
        free(settings_copy);
      }
    }
  }

  /* Extract HTTP/2 window update (second segment between first and second '|') */
  {
    size_t wu_len = pipe2 - pipe1 - 1;
    char wu_buf[32];
    if(wu_len > 0 && wu_len < sizeof(wu_buf)) {
      memcpy(wu_buf, pipe1 + 1, wu_len);
      wu_buf[wu_len] = '\0';
      *out_http2_window_update = atoi(wu_buf);
    }
  }

  /* Extract HTTP/2 priority (third segment between second and third '|')
   * Format: stream_id:exclusive:stream_dep:weight */
  {
    size_t pri_len = pipe3 - pipe2 - 2;  /* subtract pipe2+1 and trailing | */
    char pri_buf[64];
    if(pri_len > 0 && pri_len < sizeof(pri_buf)) {
      int stream_id, exclusive, stream_dep, weight;
      memcpy(pri_buf, pipe2 + 1, pri_len);
      pri_buf[pri_len] = '\0';
      if(sscanf(pri_buf, "%d:%d:%d:%d", &stream_id, &exclusive,
                &stream_dep, &weight) == 4) {
        *out_http2_stream_weight = weight;
        *out_http2_stream_exclusive = exclusive;
      }
    }
  }

  return CURLE_OK;
}

/* Parse HTTP headers from detail.HTTP2Frames.Headers[] */
static CURLcode parse_headers_from_json(cJSON *detail,
                                        struct custom_impersonations *reg,
                                        char *out_headers[],
                                        int *out_header_count)
{
  cJSON *frames, *headers_arr, *item;
  int count = 0;

  *out_header_count = 0;

  frames = cJSON_GetObjectItemCaseSensitive(detail, "HTTP2Frames");
  if(!frames)
    return CURLE_OK;

  headers_arr = cJSON_GetObjectItemCaseSensitive(frames, "Headers");
  if(!headers_arr || !cJSON_IsArray(headers_arr))
    return CURLE_OK;

  cJSON_ArrayForEach(item, headers_arr) {
    cJSON *name_obj, *value_obj;
    const char *name, *value;
    char header_buf[1024];
    int header_len;

    if(count >= IMPERSONATE_MAX_HEADERS)
      break;

    name_obj = cJSON_GetObjectItemCaseSensitive(item, "Name");
    value_obj = cJSON_GetObjectItemCaseSensitive(item, "Value");
    if(!name_obj || !value_obj || !cJSON_IsString(name_obj) ||
       !cJSON_IsString(value_obj))
      continue;

    name = name_obj->valuestring;
    value = value_obj->valuestring;

    /* Skip pseudo headers (start with ':') */
    if(name[0] == ':')
      continue;

    /* Skip site-specific headers that depend on the target URL/context.
     * These should not be baked into the browser fingerprint profile
     * as they vary per request. */
    if(curl_strequal(name, "referer") ||
       curl_strequal(name, "origin") ||
       curl_strequal(name, ":authority"))
      continue;
    /* Skip user-agent since it's handled by the impersonation system
     * via the browser's UA string, not as a custom header. */
    if(curl_strequal(name, "user-agent"))
      continue;

    /* Format: "Name: Value" */
    header_len = snprintf(header_buf, sizeof(header_buf), "%s: %s",
                          name, value);
    if(header_len <= 0 || header_len >= (int)sizeof(header_buf))
      continue;

    out_headers[count] = str_pool_add(reg, header_buf);
    if(!out_headers[count])
      return CURLE_OUT_OF_MEMORY;
    count++;
  }

  *out_header_count = count;
  return CURLE_OK;
}

/* Parse TLS extension order from ja3.AllExtensions[] (integer array)
 * Builds a hyphen-separated string of extension IDs for
 * CURLOPT_TLS_EXTENSION_ORDER, e.g. "0-17513-16-45-27-18-23-13-65037-5-35-43-65281-51-10-11"
 * GREASE extensions (0x0A0A, 0x1A1A, ..., 0xFAFA and 0xAAAA, ..., 0x4A4A) are skipped.
 * Extension 0 (SNI/server_name) is prepended.
 */
static CURLcode parse_ext_order_from_json(cJSON *ja3,
                                           struct custom_impersonations *reg,
                                           char **out_tls_extension_order,
                                           bool *out_tls_grease)
{
  cJSON *ext_ids;
  char buf[1024];
  int buf_len = 0;

  *out_tls_extension_order = NULL;
  *out_tls_grease = false;

  ext_ids = cJSON_GetObjectItemCaseSensitive(ja3, "AllExtensions");
  if(!ext_ids || !cJSON_IsArray(ext_ids))
    return CURLE_OK;

  /* Prepend SNI (extension 0) as curl expects it first */
  buf[0] = '0';
  buf_len = 1;

  {
    cJSON *item;
    cJSON_ArrayForEach(item, ext_ids) {
      int ext_id;
      if(!cJSON_IsNumber(item))
        continue;
      ext_id = item->valueint;

      /* Skip GREASE extension IDs */
      if((ext_id >= 0x0A0A && ext_id <= 0xFAFA &&
          (ext_id & 0x0F0F) == 0x0A0A) ||
         (ext_id >= 0xAAAA && ext_id <= 0xFAFA &&
          (ext_id & 0x0F0F) == 0xAAAA) ||
         /* Standard GREASE ranges */
         ext_id == 0x0A0A || ext_id == 0x1A1A || ext_id == 0x2A2A ||
         ext_id == 0x3A3A || ext_id == 0x4A4A || ext_id == 0x5A5A ||
         ext_id == 0x6A6A || ext_id == 0x7A7A || ext_id == 0x8A8A ||
         ext_id == 0x9A9A || ext_id == 0xAAAA || ext_id == 0xBABA ||
         ext_id == 0xCACA || ext_id == 0xDADA || ext_id == 0xEAEA ||
         ext_id == 0xFAFA) {
        *out_tls_grease = true;
        continue;
      }

      /* Add hyphen separator and extension ID */
      buf[buf_len++] = '-';
      buf_len += snprintf(buf + buf_len, sizeof(buf) - buf_len,
                          "%d", ext_id);
      if(buf_len >= (int)sizeof(buf) - 10)
        break;
    }
  }

  buf[buf_len] = '\0';

  if(buf_len > 2) {  /* more than just "0" */
    char *order = str_pool_add(reg, buf);
    if(!order)
      return CURLE_OUT_OF_MEMORY;
    *out_tls_extension_order = order;
  }

  return CURLE_OK;
}

/* Parse connection state from detail.ConnectionState */
static CURLcode parse_conn_state_from_json(cJSON *detail,
                                           int *out_httpversion,
                                           int *out_ssl_version)
{
  cJSON *cs, *version_obj, *proto_obj;

  *out_httpversion = CURL_HTTP_VERSION_NONE;
  *out_ssl_version = CURL_SSLVERSION_DEFAULT;

  cs = cJSON_GetObjectItemCaseSensitive(detail, "ConnectionState");
  if(!cs)
    return CURLE_OK;

  /* Parse TLS version */
  version_obj = cJSON_GetObjectItemCaseSensitive(cs, "Version");
  if(version_obj && cJSON_IsNumber(version_obj)) {
    int ver = version_obj->valueint;
    if(ver == 772) {       /* TLS 1.3 */
      *out_ssl_version = CURL_SSLVERSION_TLSv1_2 | CURL_SSLVERSION_MAX_DEFAULT;
    }
    else if(ver == 771) {  /* TLS 1.2 */
      *out_ssl_version = CURL_SSLVERSION_TLSv1_2 | CURL_SSLVERSION_MAX_DEFAULT;
    }
    else if(ver == 770) {  /* TLS 1.1 */
      *out_ssl_version = CURL_SSLVERSION_TLSv1_0 | CURL_SSLVERSION_MAX_DEFAULT;
    }
    else {
      *out_ssl_version = CURL_SSLVERSION_TLSv1_2 | CURL_SSLVERSION_MAX_DEFAULT;
    }
  }

  /* Parse negotiated protocol */
  proto_obj = cJSON_GetObjectItemCaseSensitive(cs, "NegotiatedProtocol");
  if(proto_obj && cJSON_IsString(proto_obj)) {
    if(curl_strequal(proto_obj->valuestring, "h2")) {
      *out_httpversion = CURL_HTTP_VERSION_2_0;
    }
    else {
      *out_httpversion = CURL_HTTP_VERSION_1_1;
    }
  }

  return CURLE_OK;
}

/* ========================================================================
 * Main registration function
 * ======================================================================== */
CURLcode curl_easy_impersonate_register(const char *target,
                                         const char *json_config)
{
  CURLcode result;
  cJSON *root = NULL;
  cJSON *ja3, *ja4, *detail;
  struct custom_impersonations *reg;
  struct impersonate_opts *entry;
  char *ciphers = NULL;
  char *curves = NULL;
  char *sig_hash_algs = NULL;
  char *cert_compression = NULL;
  char *pseudo_order = NULL;
  char *http2_settings = NULL;
  char *tls_extension_order = NULL;
  bool alpn = false, alps = false, alps_new_cp = false;
  bool tls_session_ticket = false, ech_grease = false;
  bool tls_signed_cert_timestamps = false, tls_grease = false;
  bool no_server_push = false;
  int httpversion = CURL_HTTP_VERSION_NONE;
  int ssl_version = CURL_SSLVERSION_DEFAULT;
  int http2_window_update = 0;
  int http2_stream_weight = 0;
  int http2_stream_exclusive = 0;
  char *headers[IMPERSONATE_MAX_HEADERS];
  int header_count = 0;
  int i;

  /* Initialize headers array */
  memset(headers, 0, sizeof(headers));

  /* 1. Validate target name */
  result = validate_target_name(target);
  if(result)
    return result;

  /* 2. Validate json_config */
  if(!json_config)
    return CURLE_BAD_FUNCTION_ARGUMENT;

  /* Check JSON length limit (1MB) */
  if(strlen(json_config) > 1024 * 1024)
    return CURLE_BAD_FUNCTION_ARGUMENT;

  /* 3. Check for conflicts */
  result = check_target_conflict(target);
  if(result)
    return result;

  /* 4. Get registry and check capacity */
  reg = custom_impersonations_get();
  if(reg->count >= MAX_CUSTOM_IMPERSONATIONS)
    return CURLE_OUT_OF_MEMORY;

  /* 5. Parse JSON */
  root = cJSON_Parse(json_config);
  if(!root) {
    return CURLE_BAD_FUNCTION_ARGUMENT;
  }

  /* 6. Parse detail first (ja3/ja4 are inside detail) */
  detail = cJSON_GetObjectItemCaseSensitive(root, "detail");

  /* 7. Parse ja3 from detail.ja3 */
  ja3 = NULL;
  if(detail) {
    ja3 = cJSON_GetObjectItemCaseSensitive(detail, "ja3");
  }
  /* Fallback: try top-level ja3 (some JSON formats may have it there) */
  if(!ja3) {
    ja3 = cJSON_GetObjectItemCaseSensitive(root, "ja3");
  }
  if(ja3 && cJSON_IsObject(ja3)) {
    result = parse_ciphers_from_json(ja3, reg, &ciphers);
    if(result)
      goto fail;

    result = parse_curves_from_json(ja3, reg, &curves);
    if(result)
      goto fail;

    result = parse_extensions_from_json(ja3, reg,
                                        &alpn, &alps, &alps_new_cp,
                                        &tls_session_ticket, &ech_grease,
                                        &tls_signed_cert_timestamps,
                                        &cert_compression);
    if(result)
      goto fail;

    /* Parse TLS extension order from ja3.AllExtensions[] */
    result = parse_ext_order_from_json(ja3, reg,
                                       &tls_extension_order,
                                       &tls_grease);
    if(result)
      goto fail;
  }

  /* 8. Parse ja4 from detail.ja4 */
  ja4 = NULL;
  if(detail) {
    ja4 = cJSON_GetObjectItemCaseSensitive(detail, "ja4");
  }
  if(!ja4) {
    ja4 = cJSON_GetObjectItemCaseSensitive(root, "ja4");
  }
  if(ja4 && cJSON_IsObject(ja4)) {
    result = parse_sig_algs_from_json(ja4, reg, &sig_hash_algs);
    if(result)
      goto fail;
  }

  /* 9. Parse http2 */
  result = parse_http2_from_json(root, reg, &pseudo_order, &no_server_push,
                                 &http2_settings, &http2_window_update,
                                 &http2_stream_weight, &http2_stream_exclusive);
  if(result)
    goto fail;

  /* 10. Parse detail for connection state and headers */
  if(detail) {
    /* ConnectionState and HTTP2Frames may be under detail.metadata */
    cJSON *metadata = cJSON_GetObjectItemCaseSensitive(detail, "metadata");
    cJSON *cs_source = detail;
    if(metadata) {
      cs_source = metadata;
    }
    result = parse_conn_state_from_json(cs_source, &httpversion, &ssl_version);
    if(result)
      goto fail;

    result = parse_headers_from_json(cs_source, reg, headers, &header_count);
    if(result)
      goto fail;
  }

  /* 10. Fill impersonate_opts structure */
  entry = &reg->entries[reg->count];
  memset(entry, 0, sizeof(*entry));

  entry->target = str_pool_add(reg, target);
  if(!entry->target) {
    result = CURLE_OUT_OF_MEMORY;
    goto fail;
  }

  entry->httpversion = httpversion;
  entry->ssl_version = ssl_version;
  entry->ciphers = ciphers;          /* already in str_pool */
  entry->curves = curves;            /* already in str_pool */
  entry->sig_hash_algs = sig_hash_algs;  /* already in str_pool */
  entry->npn = false;
  entry->alpn = alpn;
  entry->alps = alps;
  entry->tls_session_ticket = tls_session_ticket;
  entry->cert_compression = cert_compression;  /* already in str_pool */
  entry->http2_pseudo_headers_order = pseudo_order;  /* already in str_pool */
  entry->http2_settings = http2_settings;  /* already in str_pool */
  entry->http2_window_update = http2_window_update;
  entry->http2_stream_weight = http2_stream_weight;
  entry->http2_stream_exclusive = http2_stream_exclusive;
  entry->http2_no_server_push = no_server_push;
  /* If we have an explicit extension order, use it instead of permutation.
   * Otherwise, enable extension permutation for Chrome-like browsers. */
  entry->tls_extension_order = tls_extension_order;  /* already in str_pool */
  entry->tls_permute_extensions = (tls_extension_order == NULL) &&
                                  (alpn || alps || ech_grease ||
                                   tls_session_ticket || cert_compression);
  entry->ech_grease = ech_grease;
  entry->alps_use_new_codepoint = alps_new_cp;
  entry->tls_signed_cert_timestamps = tls_signed_cert_timestamps;
  entry->tls_grease = tls_grease;

  /* Copy headers */
  for(i = 0; i < header_count && i < IMPERSONATE_MAX_HEADERS; i++) {
    entry->http_headers[i] = headers[i];  /* already in str_pool */
  }

  /* 11. Commit the entry */
  reg->count++;

  /* 12. Cleanup JSON object */
  cJSON_Delete(root);

  return CURLE_OK;

fail:
  /* On failure, we need to remove any strings we added to the pool.
   * Since the entry wasn't committed, we can just reset the pool count
   * to what it was before. However, for simplicity, we leave the pool
   * as-is (the strings will be freed on cleanup). The entry wasn't
   * committed so it won't be used. */
  cJSON_Delete(root);
  return result;
}

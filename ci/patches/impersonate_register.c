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
  const struct impersonate_opts *opts;

  /* Check against built-in browsers */
  for(opts = impersonations; opts->target != NULL; opts++) {
    if(strcasecompare(target, opts->target)) {
      return CURLE_BAD_FUNCTION_ARGUMENT;
    }
  }

  /* Check against already registered custom browsers */
  {
    struct custom_impersonations *reg = custom_impersonations_get();
    int i;
    for(i = 0; i < reg->count; i++) {
      if(strcasecompare(target, reg->entries[i].target)) {
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
    if(strcasecompare(ietf_name, kCipherNameMap[i].ietf_name)) {
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
    if(strcasecompare(json_name, kGroupNameMap[i].json_name)) {
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

/* Parse cipher suites from ja3.ReadableCipherSuites[]
 * Splits into TLS 1.2 ciphers (out_ciphers) and TLS 1.3 ciphers (out_ciphers13) */
static CURLcode parse_ciphers_from_json(cJSON *ja3,
                                        struct custom_impersonations *reg,
                                        char **out_ciphers,
                                        char **out_ciphers13)
{
  cJSON *arr;
  cJSON *item;
  /* Buffer for cipher string: each cipher name is at most 50 chars + comma */
  char buf[2048];
  char buf13[512];
  int buf_len = 0, buf13_len = 0;

  *out_ciphers = NULL;
  *out_ciphers13 = NULL;
  arr = cJSON_GetObjectItemCaseSensitive(ja3, "ReadableCipherSuites");
  if(!arr || !cJSON_IsArray(arr))
    return CURLE_OK;  /* optional field */

  buf[0] = '\0';
  buf13[0] = '\0';
  cJSON_ArrayForEach(item, arr) {
    const char *ietf_name;
    const char *openssl_name;
    char name_buf[128];
    const char *space;
    int is_tls13;
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

    /* TLS 1.3 ciphers start with "TLS_" and have no "_WITH_" */
    is_tls13 = (strncmp(openssl_name, "TLS_", 4) == 0 &&
                strstr(openssl_name, "_WITH_") == NULL);

    if(is_tls13) {
      if(buf13_len > 0) {
        buf13[buf13_len++] = ',';
      }
      memcpy(buf13 + buf13_len, openssl_name, strlen(openssl_name));
      buf13_len += (int)strlen(openssl_name);
    }
    else {
      if(buf_len > 0) {
        buf[buf_len++] = ',';
      }
      memcpy(buf + buf_len, openssl_name, strlen(openssl_name));
      buf_len += (int)strlen(openssl_name);
    }
  }
  buf[buf_len] = '\0';
  buf13[buf13_len] = '\0';

  if(buf_len > 0) {
    *out_ciphers = str_pool_add(reg, buf);
    if(!*out_ciphers)
      return CURLE_OUT_OF_MEMORY;
  }
  if(buf13_len > 0) {
    *out_ciphers13 = str_pool_add(reg, buf13);
    if(!*out_ciphers13)
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
 */
static CURLcode parse_http2_from_json(cJSON *root,
                                      struct custom_impersonations *reg,
                                      char **out_pseudo_order,
                                      bool *out_no_server_push)
{
  cJSON *http2_obj;
  const char *http2_str;
  const char *pipe1, *pipe2, *pipe3;
  size_t len;

  *out_pseudo_order = NULL;
  *out_no_server_push = false;

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

  /* Check if ENABLE_PUSH=0 in settings (first segment before first '|') */
  {
    size_t settings_len = pipe1 - http2_str;
    char *settings = (char *)malloc(settings_len + 1);
    if(settings) {
      const char *pair;
      memcpy(settings, http2_str, settings_len);
      settings[settings_len] = '\0';

      /* Look for "2:0" which means ENABLE_PUSH=0 */
      pair = strstr(settings, "2:0");
      if(pair) {
        /* Verify it's exactly setting ID 2 with value 0 */
        if(pair == settings || *(pair - 1) == ';') {
          const char *after = pair + 3;
          if(*after == ';' || *after == '\0') {
            *out_no_server_push = true;
          }
        }
      }
      free(settings);
    }
  }

  return CURLE_OK;
}

/* Parse HTTP/2 frames detail from detail.HTTP2Frames
 * Extracts Settings, WindowUpdateIncrement, and Priorities
 */
static CURLcode parse_http2_frames_from_json(cJSON *detail,
                                              struct impersonate_opts *entry)
{
  cJSON *frames, *settings_arr, *window_obj, *prio_arr;
  int count = 0;

  if(!detail)
    return CURLE_OK;

  frames = cJSON_GetObjectItemCaseSensitive(detail, "HTTP2Frames");
  if(!frames)
    return CURLE_OK;

  /* Parse Settings array: [{"Id":1,"Val":65536}, ...] */
  settings_arr = cJSON_GetObjectItemCaseSensitive(frames, "Settings");
  if(settings_arr && cJSON_IsArray(settings_arr)) {
    cJSON *item;
    cJSON_ArrayForEach(item, settings_arr) {
      cJSON *id_obj, *val_obj;
      if(count >= 8)
        break;
      id_obj = cJSON_GetObjectItemCaseSensitive(item, "Id");
      val_obj = cJSON_GetObjectItemCaseSensitive(item, "Val");
      if(id_obj && val_obj && cJSON_IsNumber(id_obj) && cJSON_IsNumber(val_obj)) {
        entry->http2_settings_ids[count] = id_obj->valueint;
        entry->http2_settings_vals[count] = val_obj->valueint;
        count++;
      }
    }
  }
  entry->http2_settings_count = count;

  /* Parse WindowUpdateIncrement */
  window_obj = cJSON_GetObjectItemCaseSensitive(frames, "WindowUpdateIncrement");
  if(window_obj && cJSON_IsNumber(window_obj)) {
    entry->http2_window_update_increment = window_obj->valueint;
  }

  /* Parse Priorities array: [{"StreamId":1,"StreamDep":0,"Exclusive":true,"Weight":255}] */
  prio_arr = cJSON_GetObjectItemCaseSensitive(frames, "Priorities");
  if(prio_arr && cJSON_IsArray(prio_arr)) {
    cJSON *prio_item = cJSON_GetArrayItem(prio_arr, 0);
    if(prio_item) {
      cJSON *dep_obj = cJSON_GetObjectItemCaseSensitive(prio_item, "StreamDep");
      cJSON *weight_obj = cJSON_GetObjectItemCaseSensitive(prio_item, "Weight");
      cJSON *excl_obj = cJSON_GetObjectItemCaseSensitive(prio_item, "Exclusive");
      if(dep_obj && cJSON_IsNumber(dep_obj))
        entry->http2_priority_stream_dep = dep_obj->valueint;
      if(weight_obj && cJSON_IsNumber(weight_obj))
        entry->http2_priority_weight = weight_obj->valueint;
      if(excl_obj && cJSON_IsBool(excl_obj))
        entry->http2_priority_exclusive = cJSON_IsTrue(excl_obj);
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

    /* Whitelist: only inject headers that are browser fingerprint headers.
     * These are headers that modern browsers automatically attach to every
     * request with fixed values determined by the browser identity.
     * Headers NOT in this list are per-site/per-session/per-request values
     * (e.g. cookie, referer, authorization) that should NOT be injected.
     *
     * Reference: RFC9110 §5.1 header field names are case-insensitive,
     * so strcasecompare handles all casings (User-Agent, user-agent, etc).
     *
     * Browser fingerprint headers:
     *   user-agent          - Browser identity string
     *   accept              - Default MIME types for navigation
     *   accept-encoding     - Supported content encodings (br, gzip, etc.)
     *   accept-language     - Language preference (zh-CN, en-US, etc.)
     *   sec-ch-ua           - Client Hints: browser brand/version (Chromium)
     *   sec-ch-ua-mobile    - Client Hints: mobile indicator (Chromium)
     *   sec-ch-ua-platform  - Client Hints: OS platform (Chromium)
     *   sec-fetch-site      - Fetch metadata: request origin (Chromium/FF)
     *   sec-fetch-mode      - Fetch metadata: request mode (Chromium/FF)
     *   sec-fetch-user      - Fetch metadata: user activation (Chromium/FF)
     *   sec-fetch-dest      - Fetch metadata: request destination (Chromium/FF)
     *   upgrade-insecure-requests - HTTPS upgrade signal
     *   priority            - HTTP/2 fetch priority (Chromium format "u=0, i")
     */
    if(!strcasecompare(name, "user-agent") &&
       !strcasecompare(name, "accept") &&
       !strcasecompare(name, "accept-encoding") &&
       !strcasecompare(name, "accept-language") &&
       !strcasecompare(name, "sec-ch-ua") &&
       !strcasecompare(name, "sec-ch-ua-mobile") &&
       !strcasecompare(name, "sec-ch-ua-platform") &&
       !strcasecompare(name, "sec-fetch-site") &&
       !strcasecompare(name, "sec-fetch-mode") &&
       !strcasecompare(name, "sec-fetch-user") &&
       !strcasecompare(name, "sec-fetch-dest") &&
       !strcasecompare(name, "upgrade-insecure-requests") &&
       !strcasecompare(name, "priority"))
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
    if(strcasecompare(proto_obj->valuestring, "h2")) {
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
  char *ciphers13 = NULL;
  char *curves = NULL;
  char *sig_hash_algs = NULL;
  char *cert_compression = NULL;
  char *pseudo_order = NULL;
  bool alpn = false, alps = false, alps_new_cp = false;
  bool tls_session_ticket = false, ech_grease = false;
  bool no_server_push = false;
  int httpversion = CURL_HTTP_VERSION_NONE;
  int ssl_version = CURL_SSLVERSION_DEFAULT;
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
    result = parse_ciphers_from_json(ja3, reg, &ciphers, &ciphers13);
    if(result)
      goto fail;

    result = parse_curves_from_json(ja3, reg, &curves);
    if(result)
      goto fail;

    result = parse_extensions_from_json(ja3, reg,
                                        &alpn, &alps, &alps_new_cp,
                                        &tls_session_ticket, &ech_grease,
                                        &cert_compression);
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
  result = parse_http2_from_json(root, reg, &pseudo_order, &no_server_push);
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
  entry->ciphers13 = ciphers13;      /* already in str_pool */
  entry->curves = curves;            /* already in str_pool */
  entry->sig_hash_algs = sig_hash_algs;  /* already in str_pool */
  entry->npn = false;
  entry->alpn = alpn;
  entry->alps = alps;
  entry->tls_session_ticket = tls_session_ticket;
  entry->cert_compression = cert_compression;  /* already in str_pool */
  entry->http2_pseudo_headers_order = pseudo_order;  /* already in str_pool */
  entry->http2_no_server_push = no_server_push;
  /* If extensions were parsed from JSON, enable extension permutation
   * to match the browser's extension order. Chrome browsers always
   * permute extensions in a specific order. */
  entry->tls_permute_extensions = (alpn || alps || ech_grease ||
                                   tls_session_ticket || cert_compression);
  entry->ech_grease = ech_grease;
  entry->alps_use_new_codepoint = alps_new_cp;

  /* Parse HTTP/2 frames detail (Settings, WindowUpdate, Priority) */
  if(detail) {
    cJSON *h2frames_src = detail;
    cJSON *metadata = cJSON_GetObjectItemCaseSensitive(detail, "metadata");
    if(metadata) {
      cJSON *mf = cJSON_GetObjectItemCaseSensitive(metadata, "HTTP2Frames");
      if(mf)
        h2frames_src = metadata;
    }
    result = parse_http2_frames_from_json(h2frames_src, entry);
    if(result)
      goto fail;
  }

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

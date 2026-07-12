#ifndef HEADER_CURL_IMPERSONATE_REGISTER_H
#define HEADER_CURL_IMPERSONATE_REGISTER_H

#include "curl_setup.h"
#include <curl/curl.h>
#include "impersonate.h"

/* Maximum number of custom browser impersonations that can be registered */
#define MAX_CUSTOM_IMPERSONATIONS 64

/* Maximum strings in the string pool per registration */
#define MAX_STR_POOL_PER_ENTRY (IMPERSONATE_MAX_HEADERS + 6)

/*
 * curl-impersonate: Custom browser impersonation registry.
 * Stores dynamically registered browser fingerprint configurations.
 */
struct custom_impersonations {
  struct impersonate_opts entries[MAX_CUSTOM_IMPERSONATIONS];
  int count;
  /* String pool: dynamically allocated strings from JSON parsing.
   * Each entry can have: target, ciphers, curves, sig_hash_algs,
   * cert_compression, http2_pseudo_headers_order, and up to
   * IMPERSONATE_MAX_HEADERS http_headers strings. */
  char *str_pool[MAX_CUSTOM_IMPERSONATIONS * MAX_STR_POOL_PER_ENTRY];
  int str_pool_count;
};

/* Initialize the custom impersonation registry */
void custom_impersonations_init(void);

/* Cleanup the custom impersonation registry (free all allocated memory) */
void custom_impersonations_cleanup(void);

/* Get the global custom impersonation registry */
struct custom_impersonations *custom_impersonations_get(void);

/*
 * curl-impersonate: Register a custom browser impersonation target.
 * The json_config parameter is a JSON string containing the browser's
 * TLS/HTTP2/HTTP fingerprint data, following the format from
 * https://120.26.33.71/json/detail
 * After registration, the target can be used with curl_easy_impersonate().
 */
CURLcode curl_easy_impersonate_register(const char *target,
                                         const char *json_config);

#endif /* HEADER_CURL_IMPERSONATE_REGISTER_H */

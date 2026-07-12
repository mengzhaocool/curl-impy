#ifndef HEADER_CURL_IMPERSONATE_H
#define HEADER_CURL_IMPERSONATE_H

#include <curl/curl.h>
#include "curl_setup.h"

/* curl-impersonate: Compatibility with older curl API names */
#define strcasecompare(a,b) curl_strequal((a),(b))
#define strncasecompare(a,b,c) curl_strnequal((a),(b),(c))
#define Curl_safefree(ptr) curlx_safefree(ptr)
#define aprintf curl_maprintf

#define IMPERSONATE_MAX_HEADERS 32

/*
 * curl-impersonate: Options to be set for each supported target browser.
 */
struct impersonate_opts {
  const char *target;
  int httpversion;
  int ssl_version;
  const char *ciphers;
  /* TLS 1.3 cipher suites.
   * Passed to CURLOPT_TLS13_CIPHERS */
  const char *ciphers13;
  /* Elliptic curves (TLS extension 10).
   * Passed to CURLOPT_SSL_EC_CURVES */
  const char *curves;
  /* Signature hash algorithms (TLS extension 13).
   * Passed to CURLOPT_SSL_SIGNATURE_ALGORITHMS (native 8.20.0) */
  const char *sig_hash_algs;
  /* Enable TLS ALPN extension. */
  bool alpn;
  /* Enable TLS NPN extension (deprecated, always false). */
  bool npn;
  /* Enable TLS ALPS extension. */
  bool alps;
  /* Enable TLS session ticket extension. */
  bool tls_session_ticket;
  /* TLS certificate compression algorithms.
   * (TLS extension 27) */
  const char *cert_compression;
  const char *http_headers[IMPERSONATE_MAX_HEADERS];
  const char *http2_pseudo_headers_order;
  bool http2_no_server_push;
  bool tls_permute_extensions;
  bool ech_grease;              /* Enable ECH GREASE extension (0xfe0d) */
  bool alps_use_new_codepoint;  /* Use ALPS new codepoint 0x44cd */
  /* HTTP/2 SETTINGS frame entries (from HTTP2Frames.Settings in JSON) */
  int http2_settings_ids[8];    /* Settings IDs (e.g. 1=HEADER_TABLE_SIZE) */
  int http2_settings_vals[8];   /* Settings values */
  int http2_settings_count;     /* Number of settings entries (max 8) */
  /* HTTP/2 WINDOW_UPDATE increment (from HTTP2Frames.WindowUpdateIncrement) */
  int http2_window_update_increment;  /* 0 = use default */
  /* HTTP/2 stream priority (from HTTP2Frames.Priorities[0]) */
  int http2_priority_stream_dep;      /* Stream dependency */
  int http2_priority_weight;          /* Priority weight (1-256) */
  bool http2_priority_exclusive;      /* Exclusive flag */
  /* Other TLS options will come here in the future once they are
   * configurable through curl_easy_setopt() */
};

/*
 * curl-impersonate: Global array of supported browsers and their
 * impersonation options.
 */
extern const struct impersonate_opts impersonations[];

#endif /* HEADER_CURL_IMPERSONATE_H */

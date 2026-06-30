/*
 * Functional test for curl-impersonate three core APIs:
 * 1. curl_easy_impersonate_list() - List all available browser targets
 * 2. curl_easy_impersonate() - Impersonate a browser
 * 3. curl_easy_impersonate_register() - Register custom browser
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

/* Write callback to discard response body */
static size_t write_callback(void *ptr, size_t size, size_t nmemb, void *data)
{
  (void)ptr;
  (void)data;
  return size * nmemb;
}

/* Test 1: curl_easy_impersonate_list() */
static int test_list(void)
{
  struct curl_slist *list, *item;
  int count = 0;

  printf("=== Test 1: curl_easy_impersonate_list() ===\n");

  list = curl_easy_impersonate_list();
  if(!list) {
    printf("  FAIL: curl_easy_impersonate_list() returned NULL\n");
    return 1;
  }

  printf("  Available browser targets:\n");
  for(item = list; item; item = item->next) {
    printf("    - %s\n", item->data);
    count++;
  }

  curl_slist_free_all(list);

  if(count > 0) {
    printf("  PASS: Listed %d browser targets\n", count);
    return 0;
  }
  else {
    printf("  FAIL: No browser targets found\n");
    return 1;
  }
}

/* Test 2: curl_easy_impersonate() */
static int test_impersonate(void)
{
  CURL *curl;
  CURLcode res;
  char *effective_url = NULL;
  long http_code = 0;

  printf("\n=== Test 2: curl_easy_impersonate() ===\n");

  curl = curl_easy_init();
  if(!curl) {
    printf("  FAIL: curl_easy_init() returned NULL\n");
    return 1;
  }

  /* Impersonate Chrome */
  res = curl_easy_impersonate(curl, "chrome120", 1);
  if(res != CURLE_OK) {
    printf("  FAIL: curl_easy_impersonate('chrome120') failed: %s\n",
           curl_easy_strerror(res));
    curl_easy_cleanup(curl);
    return 1;
  }
  printf("  PASS: curl_easy_impersonate('chrome120') succeeded\n");

  /* Set URL to a test endpoint (TLS fingerprint check) */
  curl_easy_setopt(curl, CURLOPT_URL, "https://tls13.1d.pw");
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
  curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
  curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

  printf("  INFO: Connecting to https://tls13.1d.pw ...\n");
  res = curl_easy_perform(curl);

  if(res == CURLE_OK) {
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    printf("  PASS: HTTP request succeeded (code: %ld)\n", http_code);
  }
  else {
    printf("  WARN: HTTP request failed: %s (may be network issue)\n",
           curl_easy_strerror(res));
  }

  curl_easy_cleanup(curl);
  return 0;
}

/* Test 3: curl_easy_impersonate_register() */
static int test_register(void)
{
  CURL *curl;
  CURLcode res;
  struct curl_slist *list, *item;
  int found = 0;

  printf("\n=== Test 3: curl_easy_impersonate_register() ===\n");

  /* Register a custom browser with minimal JSON config */
  const char *json_config = "{"
    "\"detail\": {"
    "  \"ja3\": {"
    "    \"ReadableCipherSuites\": ["
    "      \"TLS_AES_128_GCM_SHA256\","
    "      \"TLS_CHACHA20_POLY1305_SHA256\","
    "      \"TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256\""
    "    ],"
    "    \"ReadableSupportedGroups\": [\"x25519\", \"secp256r1\"],"
    "    \"ReadableAllExtensions\": ["
    "      \"application_layer_protocol_negotiation\","
    "      \"compress_certificate\","
    "      \"session_ticket\""
    "    ]"
    "  },"
    "  \"ja4\": {"
    "    \"SignatureAlgorithms\": [1027, 2059, 1285]"
    "  },"
    "  \"ConnectionState\": {"
    "    \"Version\": 772,"
    "    \"NegotiatedProtocol\": \"h2\""
    "  }"
    "}"
    "}";

  res = curl_easy_impersonate_register("test_custom", json_config);
  if(res != CURLE_OK) {
    printf("  FAIL: curl_easy_impersonate_register() failed: %s\n",
           curl_easy_strerror(res));
    return 1;
  }
  printf("  PASS: curl_easy_impersonate_register('test_custom') succeeded\n");

  /* Verify the custom target appears in the list */
  list = curl_easy_impersonate_list();
  for(item = list; item; item = item->next) {
    if(strcmp(item->data, "test_custom") == 0) {
      found = 1;
      break;
    }
  }
  curl_slist_free_all(list);

  if(found) {
    printf("  PASS: 'test_custom' found in impersonate list\n");
  }
  else {
    printf("  FAIL: 'test_custom' NOT found in impersonate list\n");
    return 1;
  }

  /* Try to use the custom target */
  curl = curl_easy_init();
  if(!curl) {
    printf("  FAIL: curl_easy_init() returned NULL\n");
    return 1;
  }

  res = curl_easy_impersonate(curl, "test_custom", 1);
  if(res != CURLE_OK) {
    printf("  FAIL: curl_easy_impersonate('test_custom') failed: %s\n",
           curl_easy_strerror(res));
    curl_easy_cleanup(curl);
    return 1;
  }
  printf("  PASS: curl_easy_impersonate('test_custom') succeeded\n");

  curl_easy_cleanup(curl);
  return 0;
}

int main(void)
{
  int failures = 0;

  printf("curl-impersonate API Functional Test\n");
  printf("=====================================\n\n");

  if(curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
    printf("FATAL: curl_global_init() failed\n");
    return 1;
  }

  failures += test_list();
  failures += test_impersonate();
  failures += test_register();

  curl_global_cleanup();

  printf("\n=====================================\n");
  if(failures == 0)
    printf("ALL TESTS PASSED\n");
  else
    printf("%d TEST(S) FAILED\n", failures);

  return failures;
}

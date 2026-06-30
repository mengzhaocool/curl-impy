/* Debug test: find which CURLOPT fails */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

int main(void)
{
  CURL *curl;
  CURLcode res;

  printf("curl-impersonate debug test\n");

  if(curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
    printf("FATAL: curl_global_init() failed\n");
    return 1;
  }

  curl = curl_easy_init();
  if(!curl) {
    printf("FATAL: curl_easy_init() returned NULL\n");
    return 1;
  }

  /* Test each custom CURLOPT individually */
  printf("Testing CURLOPT_SSL_ENABLE_ALPN...\n");
  res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_ALPN, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_SSL_ENABLE_ALPS...\n");
  res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_ALPS, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_SSL_ENABLE_TICKET...\n");
  res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_TICKET, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_SSL_PERMUTE_EXTENSIONS...\n");
  res = curl_easy_setopt(curl, CURLOPT_SSL_PERMUTE_EXTENSIONS, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_TLS_GREASE...\n");
  res = curl_easy_setopt(curl, CURLOPT_TLS_GREASE, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS...\n");
  res = curl_easy_setopt(curl, CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_TLS_STATUS_REQUEST...\n");
  res = curl_easy_setopt(curl, CURLOPT_TLS_STATUS_REQUEST, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_SPLIT_COOKIES...\n");
  res = curl_easy_setopt(curl, CURLOPT_SPLIT_COOKIES, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_HTTP2_NO_PRIORITY...\n");
  res = curl_easy_setopt(curl, CURLOPT_HTTP2_NO_PRIORITY, 0);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_PROXY_CREDENTIAL_NO_REUSE...\n");
  res = curl_easy_setopt(curl, CURLOPT_PROXY_CREDENTIAL_NO_REUSE, 0);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT...\n");
  res = curl_easy_setopt(curl, CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT, 0);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_HTTP2_WINDOW_UPDATE...\n");
  res = curl_easy_setopt(curl, CURLOPT_HTTP2_WINDOW_UPDATE, 15663105);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_STREAM_EXCLUSIVE...\n");
  res = curl_easy_setopt(curl, CURLOPT_STREAM_EXCLUSIVE, 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_TLS_RECORD_SIZE_LIMIT...\n");
  res = curl_easy_setopt(curl, CURLOPT_TLS_RECORD_SIZE_LIMIT, 0);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_TLS_KEY_SHARES_LIMIT...\n");
  res = curl_easy_setopt(curl, CURLOPT_TLS_KEY_SHARES_LIMIT, 0);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_SSL_SIG_HASH_ALGS...\n");
  res = curl_easy_setopt(curl, CURLOPT_SSL_SIG_HASH_ALGS, "test");
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_HTTP2_SETTINGS...\n");
  res = curl_easy_setopt(curl, CURLOPT_HTTP2_SETTINGS, "1:65536");
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_FORM_BOUNDARY...\n");
  res = curl_easy_setopt(curl, CURLOPT_FORM_BOUNDARY, "webkit");
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  printf("Testing CURLOPT_IMPERSONATE...\n");
  res = curl_easy_setopt(curl, CURLOPT_IMPERSONATE, "chrome120:yes");
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  /* Now test curl_easy_impersonate */
  printf("\nTesting curl_easy_impersonate('chrome120')...\n");
  res = curl_easy_impersonate(curl, "chrome120", 1);
  printf("  Result: %d (%s)\n", res, curl_easy_strerror(res));

  curl_easy_cleanup(curl);
  curl_global_cleanup();
  printf("\nDone\n");
  return 0;
}

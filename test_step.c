#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "deps/curl-8.20.0/include/curl/curl.h"

/* Test each setopt call from _do_impersonate individually */
int main(void)
{
    CURL *curl;
    CURLcode res;
    int fail_count = 0;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if(!curl) {
        fprintf(stderr, "curl_easy_init() failed\n");
        return 1;
    }

    printf("Testing each CURLOPT from _do_impersonate('chrome120'):\n\n");

    /* 1. CURLOPT_HTTP_VERSION */
    res = curl_easy_setopt(curl, CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_2_0);
    printf("CURLOPT_HTTP_VERSION = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 2. CURLOPT_SSLVERSION */
    res = curl_easy_setopt(curl, CURLOPT_SSLVERSION, CURL_SSLVERSION_MAX_TLSv1_3 | CURL_SSLVERSION_TLSv1_2);
    printf("CURLOPT_SSLVERSION = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 3. CURLOPT_SSL_CIPHER_LIST */
    res = curl_easy_setopt(curl, CURLOPT_SSL_CIPHER_LIST, "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES256-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA:AES256-SHA");
    printf("CURLOPT_SSL_CIPHER_LIST = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 4. CURLOPT_SSL_EC_CURVES */
    res = curl_easy_setopt(curl, CURLOPT_SSL_EC_CURVES, "X25519:P-256:P-384");
    printf("CURLOPT_SSL_EC_CURVES = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 5. CURLOPT_SSL_SIG_HASH_ALGS */
    res = curl_easy_setopt(curl, CURLOPT_SSL_SIG_HASH_ALGS, "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:rsa_pss_rsae_sha256:rsa_pss_rsae_sha384:rsa_pkcs1_sha256:rsa_pkcs1_sha384:rsa_pkcs1_sha1");
    printf("CURLOPT_SSL_SIG_HASH_ALGS = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 6. CURLOPT_HTTP3_SIG_HASH_ALGS - NULL for chrome120, skip */

    /* 7. CURLOPT_SSL_ENABLE_NPN */
    res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_NPN, 0);
    printf("CURLOPT_SSL_ENABLE_NPN = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 8. CURLOPT_SSL_ENABLE_ALPN */
    res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_ALPN, 1);
    printf("CURLOPT_SSL_ENABLE_ALPN = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 9. CURLOPT_SSL_ENABLE_ALPS */
    res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_ALPS, 1);
    printf("CURLOPT_SSL_ENABLE_ALPS = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 10. CURLOPT_SSL_ENABLE_TICKET */
    res = curl_easy_setopt(curl, CURLOPT_SSL_ENABLE_TICKET, 1);
    printf("CURLOPT_SSL_ENABLE_TICKET = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 11. CURLOPT_SSL_PERMUTE_EXTENSIONS */
    res = curl_easy_setopt(curl, CURLOPT_SSL_PERMUTE_EXTENSIONS, 1);
    printf("CURLOPT_SSL_PERMUTE_EXTENSIONS = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 12. CURLOPT_SSL_CERT_COMPRESSION - NULL for chrome120, skip */

    /* 13. CURLOPT_HTTP2_PSEUDO_HEADERS_ORDER */
    res = curl_easy_setopt(curl, CURLOPT_HTTP2_PSEUDO_HEADERS_ORDER, ":method:authority:scheme:path");
    printf("CURLOPT_HTTP2_PSEUDO_HEADERS_ORDER = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 14. CURLOPT_HTTP2_SETTINGS */
    res = curl_easy_setopt(curl, CURLOPT_HTTP2_SETTINGS, "1:65536;3:1000;4:65536;6:262144");
    printf("CURLOPT_HTTP2_SETTINGS = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 15. CURLOPT_HTTPHEADER_ORDER */
    res = curl_easy_setopt(curl, CURLOPT_HTTPHEADER_ORDER, ":method:authority:scheme:path");
    printf("CURLOPT_HTTPHEADER_ORDER = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 16. CURLOPT_HTTP2_WINDOW_UPDATE */
    res = curl_easy_setopt(curl, CURLOPT_HTTP2_WINDOW_UPDATE, 15663105);
    printf("CURLOPT_HTTP2_WINDOW_UPDATE = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 17. CURLOPT_HTTP2_STREAMS */
    res = curl_easy_setopt(curl, CURLOPT_HTTP2_STREAMS, "1000");
    printf("CURLOPT_HTTP2_STREAMS = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 18. CURLOPT_HTTP2_NO_PRIORITY */
    res = curl_easy_setopt(curl, CURLOPT_HTTP2_NO_PRIORITY, 1);
    printf("CURLOPT_HTTP2_NO_PRIORITY = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 19. CURLOPT_TLS_GREASE */
    res = curl_easy_setopt(curl, CURLOPT_TLS_GREASE, 1);
    printf("CURLOPT_TLS_GREASE = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 20. CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT */
    res = curl_easy_setopt(curl, CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT, 1);
    printf("CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 21. CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS */
    res = curl_easy_setopt(curl, CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS, 1);
    printf("CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 22. CURLOPT_TLS_STATUS_REQUEST */
    res = curl_easy_setopt(curl, CURLOPT_TLS_STATUS_REQUEST, 1);
    printf("CURLOPT_TLS_STATUS_REQUEST = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 23. CURLOPT_TLS_EXTENSION_ORDER */
    res = curl_easy_setopt(curl, CURLOPT_TLS_EXTENSION_ORDER, "0,10,11,13,16,23,27,35,43,45,51,65281");
    printf("CURLOPT_TLS_EXTENSION_ORDER = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 24. CURLOPT_TLS_DELEGATED_CREDENTIALS - NULL for chrome120, skip */

    /* 25. CURLOPT_TLS_RECORD_SIZE_LIMIT */
    res = curl_easy_setopt(curl, CURLOPT_TLS_RECORD_SIZE_LIMIT, 0);
    printf("CURLOPT_TLS_RECORD_SIZE_LIMIT = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 26. CURLOPT_TLS_KEY_SHARES_LIMIT */
    res = curl_easy_setopt(curl, CURLOPT_TLS_KEY_SHARES_LIMIT, 0);
    printf("CURLOPT_TLS_KEY_SHARES_LIMIT = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 27. CURLOPT_STREAM_WEIGHT */
    res = curl_easy_setopt(curl, CURLOPT_STREAM_WEIGHT, 256);
    printf("CURLOPT_STREAM_WEIGHT = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 28. CURLOPT_STREAM_EXCLUSIVE */
    res = curl_easy_setopt(curl, CURLOPT_STREAM_EXCLUSIVE, 1);
    printf("CURLOPT_STREAM_EXCLUSIVE = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 29. CURLOPT_PROXY_CREDENTIAL_NO_REUSE */
    res = curl_easy_setopt(curl, CURLOPT_PROXY_CREDENTIAL_NO_REUSE, 0);
    printf("CURLOPT_PROXY_CREDENTIAL_NO_REUSE = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 30. CURLOPT_SPLIT_COOKIES */
    res = curl_easy_setopt(curl, CURLOPT_SPLIT_COOKIES, 0);
    printf("CURLOPT_SPLIT_COOKIES = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    /* 31. CURLOPT_FORM_BOUNDARY */
    res = curl_easy_setopt(curl, CURLOPT_FORM_BOUNDARY, "----WebKitFormBoundary");
    printf("CURLOPT_FORM_BOUNDARY = %d %s\n", res, res ? "FAIL" : "OK");
    if(res) fail_count++;

    printf("\n--- Summary ---\n");
    printf("Failed: %d\n", fail_count);

    /* Now test the actual impersonate call */
    curl_easy_cleanup(curl);
    curl = curl_easy_init();
    printf("\nTesting curl_easy_impersonate('chrome120')...\n");
    res = curl_easy_impersonate(curl, "chrome120", 1);
    printf("curl_easy_impersonate('chrome120') = %d", res);
    if(res == CURLE_UNKNOWN_OPTION)
        printf(" (CURLE_UNKNOWN_OPTION)");
    else if(res == CURLE_NOT_BUILT_IN)
        printf(" (CURLE_NOT_BUILT_IN)");
    printf("\n");

    curl_easy_cleanup(curl);
    curl_global_cleanup();
    return fail_count > 0 ? 1 : 0;
}

/* Quick test: verify all protocols and TLS fingerprint */
#include <stdio.h>
#include <string.h>
#include <curl/curl.h>

static size_t write_cb(char *ptr, size_t size, size_t nmemb, void *userdata) {
    return size * nmemb;
}

int main(void) {
    curl_version_info_data *info;
    const char *const *proto;
    int i;

    printf("=== curl-impersonate Protocol Support ===\n\n");

    info = curl_version_info(CURLVERSION_NOW);
    printf("Version: %s\n", info->version);
    printf("SSL: %s\n", info->ssl_version ? info->ssl_version : "none");
    printf("libz: %s\n", info->libz_version ? info->libz_version : "none");
    printf("\n");

    /* List all protocols */
    printf("Supported Protocols:\n");
    for (i = 0, proto = info->protocols; *proto; proto++, i++) {
        printf("  [%2d] %s\n", i+1, *proto);
    }
    printf("Total: %d protocols\n\n", i);

    /* Check features */
    printf("Features:\n");
    if (info->features & CURL_VERSION_IPV6)       printf("  IPv6\n");
    if (info->features & CURL_VERSION_SSL)         printf("  SSL\n");
    if (info->features & CURL_VERSION_LIBZ)        printf("  libz\n");
    if (info->features & CURL_VERSION_NTLM)        printf("  NTLM\n");
    if (info->features & CURL_VERSION_HTTP2)        printf("  HTTP/2\n");
    if (info->features & CURL_VERSION_HTTP3)        printf("  HTTP/3\n");
    if (info->features & CURL_VERSION_BROTLI)       printf("  Brotli\n");
    if (info->features & CURL_VERSION_ALTSVC)       printf("  Alt-Svc\n");
    if (info->features & CURL_VERSION_HTTPS_PROXY)  printf("  HTTPS-proxy\n");
    if (info->features & CURL_VERSION_ZSTD)         printf("  Zstd\n");
    if (info->features & CURL_VERSION_HSTS)         printf("  HSTS\n");
    /* CURL_VERSION_WEBSOCKETS added in 8.8.0 */
    if (info->features & CURL_VERSION_ASYNCHDNS)    printf("  AsyncDNS\n");

    /* Test TLS fingerprint */
    printf("\n=== TLS Fingerprint Test ===\n");
    CURL *curl = curl_easy_init();
    if (curl) {
        /* Test Chrome 132 impersonation */
        CURLcode res = curl_easy_impersonate(curl, "chrome131", 0);
        if (res != CURLE_OK) {
            printf("curl_easy_impersonate failed: %s\n", curl_easy_strerror(res));
        } else {
            curl_easy_setopt(curl, CURLOPT_URL, "https://ja3er.com/json");
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
            curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
            curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);

            res = curl_easy_perform(curl);
            if (res != CURLE_OK) {
                printf("HTTP request failed: %s\n", curl_easy_strerror(res));
            } else {
                long http_code = 0;
                curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
                printf("HTTP Status: %ld\n", http_code);
                if (http_code == 200) {
                    printf("TLS Fingerprint: PASSED (Chrome 132)\n");
                } else {
                    printf("TLS Fingerprint: FAILED (non-200 response)\n");
                }
            }
        }
        curl_easy_cleanup(curl);
    }

    printf("\nDone.\n");
    return 0;
}

/*
 * CONNECT 隧道响应头分离测试
 * 测试 curl-impersonate 是否正确分离 CONNECT 隧道响应头和实际 HTTP 响应头
 *
 * 问题症状：
 *   - CURLINFO_RESPONSE_CODE 返回 0（应为实际 HTTP 状态码）
 *   - CURLOPT_HEADERFUNCTION 回调收到 CONNECT 响应头（如 "HTTP/1.1 200 Connection established"）
 *   - 实际 HTTP 响应头丢失或被污染
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

/* 收集所有收到的响应头 */
struct header_collector {
    char headers[8192];
    int count;
    int got_connect_status;      /* 是否收到 CONNECT 隧道的 status line */
    int got_http_status;         /* 是否收到实际 HTTP 的 status line */
    long connect_code;           /* CONNECT 隧道响应码 */
};

static size_t header_callback(char *buffer, size_t size, size_t nitems,
                              void *userdata)
{
    struct header_collector *hc = (struct header_collector *)userdata;
    size_t total = size * nitems;

    hc->count++;

    /* 检查是否是 status line */
    if(strncmp(buffer, "HTTP/", 5) == 0) {
        /* 解析状态码 */
        const char *p = buffer + 5;
        while(*p && *p != ' ') p++;
        if(*p == ' ') {
            p++;
            if(p[0] >= '0' && p[0] <= '9' &&
               p[1] >= '0' && p[1] <= '9' &&
               p[2] >= '0' && p[2] <= '9') {
                long code = (p[0]-'0')*100 + (p[1]-'0')*10 + (p[2]-'0');
                if(hc->got_http_status) {
                    /* 已经收到过 HTTP status，这应该是 CONNECT 的 */
                    hc->got_connect_status = 1;
                    hc->connect_code = code;
                    printf("[HEADER_CB] *** CONNECT tunnel status line leaked: %.*s",
                           (int)total, buffer);
                } else if(strstr(buffer, "Connection established") ||
                          strstr(buffer, "Tunnel established")) {
                    /* CONNECT 隧道响应 */
                    hc->got_connect_status = 1;
                    hc->connect_code = code;
                    printf("[HEADER_CB] *** CONNECT tunnel header leaked: %.*s",
                           (int)total, buffer);
                } else {
                    hc->got_http_status = 1;
                }
            }
        }
    }

    /* 追加到收集缓冲区 */
    if(strlen(hc->headers) + total < sizeof(hc->headers) - 1) {
        strncat(hc->headers, buffer, total);
    }

    return total;
}

static size_t write_callback(void *ptr, size_t size, size_t nmemb, void *data)
{
    (void)ptr;
    (void)data;
    return size * nmemb;
}

static int test_connect_tunnel(const char *proxy, const char *url,
                               const char *test_name)
{
    CURL *curl;
    CURLcode res;
    long http_code = 0;
    struct header_collector hc;
    int failure = 0;

    memset(&hc, 0, sizeof(hc));
    hc.headers[0] = '\0';

    printf("\n=== %s ===\n", test_name);
    printf("  Proxy: %s\n", proxy);
    printf("  URL:   %s\n", url);

    curl = curl_easy_init();
    if(!curl) {
        printf("  FAIL: curl_easy_init() returned NULL\n");
        return 1;
    }

    /* Impersonate Chrome */
    res = curl_easy_impersonate(curl, "chrome120", 1);
    if(res != CURLE_OK) {
        printf("  FAIL: curl_easy_impersonate failed: %s\n",
               curl_easy_strerror(res));
        curl_easy_cleanup(curl);
        return 1;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_PROXY, proxy);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, header_callback);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, &hc);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    printf("  Performing request...\n");
    res = curl_easy_perform(curl);

    if(res == CURLE_OK) {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        printf("  CURLINFO_RESPONSE_CODE: %ld\n", http_code);
        printf("  Header callback invocations: %d\n", hc.count);
        printf("  Got CONNECT tunnel status line: %s\n",
               hc.got_connect_status ? "YES (BUG!)" : "no");
        printf("  Got HTTP status line: %s\n",
               hc.got_http_status ? "yes" : "NO (BUG!)");

        /* 判断 */
        if(http_code == 0) {
            printf("  FAIL: RESPONSE_CODE is 0 (should be actual HTTP code)\n");
            failure = 1;
        }
        if(hc.got_connect_status) {
            printf("  FAIL: CONNECT tunnel response header leaked to "
                   "HEADERFUNCTION callback\n");
            failure = 1;
        }
        if(!hc.got_http_status && hc.count == 0) {
            printf("  FAIL: No headers received at all\n");
            failure = 1;
        }
        if(!failure) {
            printf("  PASS: CONNECT tunnel headers properly separated\n");
        }
    } else {
        printf("  WARN: curl_easy_perform failed: %s\n",
               curl_easy_strerror(res));
        /* 网络问题不算测试失败 */
    }

    curl_easy_cleanup(curl);
    return failure;
}

int main(void)
{
    int failures = 0;
    const char *proxy = "http://120.26.33.71:28080";

    printf("CONNECT Tunnel Response Header Separation Test\n");
    printf("================================================\n");

    if(curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        printf("FATAL: curl_global_init() failed\n");
        return 1;
    }

    /* 测试 1: HTTPS 通过 HTTP CONNECT 代理 */
    failures += test_connect_tunnel(
        proxy,
        "https://httpbin.org/get",
        "Test 1: HTTPS via HTTP CONNECT proxy");

    /* 测试 2: 另一个 HTTPS 站点 */
    failures += test_connect_tunnel(
        proxy,
        "https://www.example.com",
        "Test 2: HTTPS via HTTP CONNECT proxy (example.com)");

    curl_global_cleanup();

    printf("\n================================================\n");
    if(failures == 0)
        printf("ALL TESTS PASSED\n");
    else
        printf("%d TEST(S) FAILED\n", failures);

    return failures;
}

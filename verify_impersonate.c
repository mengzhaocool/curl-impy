/*
 * verify_impersonate.c - Comprehensive verification of libcurl-impersonate DLL
 *
 * Tests:
 *   1. DLL load + basic curl functionality (version info, init/cleanup)
 *   2. Built-in impersonation targets (curl_easy_impersonate_list)
 *   3. curl_easy_impersonate_register with XWEB.json
 *   4. HTTPS request with impersonation (JA3/JA4/HTTP2 fingerprint)
 *   5. Fingerprint comparison (JA4 + HTTP2 must match, JA3 extension set must match)
 *
 * Build:
 *   cl /MT /O2 verify_impersonate.c /I output\include /link /LIBPATH:build\curl\lib libcurl-impersonate_imp.lib ws2_32.lib crypt32.lib normaliz.lib advapi32.lib kernel32.lib user32.lib /OUT:verify_impersonate.exe
 *
 * Run:
 *   verify_impersonate.exe <path_to_XWEB.json>
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <curl/curl.h>

/* ── Colors ─────────────────────────────────────────────────────── */
#define COLOR_RED     "\033[31m"
#define COLOR_GREEN   "\033[32m"
#define COLOR_YELLOW  "\033[33m"
#define COLOR_CYAN    "\033[36m"
#define COLOR_RESET   "\033[0m"

static int g_pass = 0, g_fail = 0, g_warn = 0;

#define TEST_PASS(msg) do { printf(COLOR_GREEN "  [PASS] %s\n" COLOR_RESET, msg); g_pass++; } while(0)
#define TEST_FAIL(msg) do { printf(COLOR_RED "  [FAIL] %s\n" COLOR_RESET, msg); g_fail++; } while(0)
#define TEST_WARN(msg) do { printf(COLOR_YELLOW "  [WARN] %s\n" COLOR_RESET, msg); g_warn++; } while(0)
#define TEST_INFO(msg) do { printf(COLOR_CYAN "  [INFO] %s\n" COLOR_RESET, msg); } while(0)

/* ── Write callback ─────────────────────────────────────────────── */
struct response_buf {
    char  *data;
    size_t size;
};

static size_t write_cb(void *ptr, size_t size, size_t nmemb, void *userdata)
{
    struct response_buf *buf = (struct response_buf *)userdata;
    size_t total = size * nmemb;
    char *newp = (char *)realloc(buf->data, buf->size + total + 1);
    if(!newp) return 0;
    buf->data = newp;
    memcpy(buf->data + buf->size, ptr, total);
    buf->size += total;
    buf->data[buf->size] = '\0';
    return total;
}

/* ── Read file into malloc'd string ─────────────────────────────── */
static char *read_file(const char *path, size_t *out_len)
{
    FILE *f = fopen(path, "rb");
    if(!f) return NULL;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc(len + 1);
    if(!buf) { fclose(f); return NULL; }
    fread(buf, 1, len, f);
    buf[len] = '\0';
    fclose(f);
    if(out_len) *out_len = (size_t)len;
    return buf;
}

/* ── Parse XWEB.json expected values ────────────────────────────── */
/* We extract expected JA4 and HTTP2 fingerprint from the JSON ourselves
 * to avoid depending on an external JSON parser in C. */

static int find_json_string_value(const char *json, const char *key, char *out, size_t out_sz)
{
    /* Simple: find "key":"value" */
    char search[256];
    snprintf(search, sizeof(search), "\"%s\":\"", key);
    const char *p = strstr(json, search);
    if(!p) return -1;
    p += strlen(search);
    size_t i = 0;
    while(*p && *p != '"' && i < out_sz - 1) {
        out[i++] = *p++;
    }
    out[i] = '\0';
    return 0;
}

/* ── Test 1: DLL load + version ─────────────────────────────────── */
static void test_basic_curl(void)
{
    printf("\n=== Test 1: Basic curl functionality ===\n");

    /* Version */
    const char *ver = curl_version();
    if(ver && strlen(ver) > 0) {
        printf("  Version: %s\n", ver);
        TEST_PASS("curl_version() returned valid string");
    } else {
        TEST_FAIL("curl_version() returned NULL or empty");
    }

    /* Version info */
    curl_version_info_data *vi = curl_version_info(CURLVERSION_NOW);
    if(vi) {
        printf("  libcurl version: %u.%u.%u\n", vi->version_num >> 16, (vi->version_num >> 8) & 0xFF, vi->version_num & 0xFF);
        if(vi->ssl_version) printf("  SSL: %s\n", vi->ssl_version);
        if(vi->libz_version) printf("  zlib: %s\n", vi->libz_version);
        if(vi->ares) printf("  c-ares: %s\n", vi->ares);
        printf("  Features: 0x%x\n", vi->features);
        if(vi->features & CURL_VERSION_SSL)  TEST_PASS("SSL/TLS supported");
        else                                 TEST_FAIL("SSL/TLS NOT supported");
        if(vi->features & CURL_VERSION_HTTP2) TEST_PASS("HTTP/2 supported");
        else                                  TEST_FAIL("HTTP/2 NOT supported");
        if(vi->features & CURL_VERSION_BROTLI) TEST_PASS("Brotli supported");
        else                                   TEST_WARN("Brotli not supported");
        if(vi->features & CURL_VERSION_ZSTD)   TEST_PASS("zstd supported");
        else                                   TEST_WARN("zstd not supported");
    } else {
        TEST_FAIL("curl_version_info() returned NULL");
    }

    /* Init/cleanup cycle */
    CURL *curl = curl_easy_init();
    if(curl) {
        TEST_PASS("curl_easy_init() succeeded");
        curl_easy_cleanup(curl);
        TEST_PASS("curl_easy_cleanup() succeeded");
    } else {
        TEST_FAIL("curl_easy_init() failed");
    }
}

/* ── Test 2: Built-in impersonation list ────────────────────────── */
static void test_builtin_impersonate(void)
{
    printf("\n=== Test 2: Built-in impersonation targets ===\n");

    struct curl_slist *list = curl_easy_impersonate_list();
    if(!list) {
        TEST_FAIL("curl_easy_impersonate_list() returned NULL");
        return;
    }

    int count = 0;
    struct curl_slist *item;
    for(item = list; item; item = item->next) {
        count++;
        if(count <= 10) printf("  [%d] %s\n", count, item->data);
    }
    if(count > 10) printf("  ... and %d more\n", count - 10);

    char msg[128];
    snprintf(msg, sizeof(msg), "Found %d built-in impersonation targets", count);
    if(count > 0) TEST_PASS(msg);
    else          TEST_FAIL(msg);

    curl_slist_free_all(list);
}

/* ── Test 3: curl_easy_impersonate_register ─────────────────────── */
static const char *XWEB_TARGET = "xweb_wechat_win";

static void test_register_impersonate(const char *json_config)
{
    printf("\n=== Test 3: curl_easy_impersonate_register ===\n");

    CURLcode res = curl_easy_impersonate_register(XWEB_TARGET, json_config);
    if(res == CURLE_OK) {
        char msg[128];
        snprintf(msg, sizeof(msg), "Registered target '%s'", XWEB_TARGET);
        TEST_PASS(msg);
    } else {
        char msg[128];
        snprintf(msg, sizeof(msg), "Register target '%s' failed: %d (%s)",
                 XWEB_TARGET, res, curl_easy_strerror(res));
        TEST_FAIL(msg);
    }

    /* Verify it appears in the list now */
    struct curl_slist *list = curl_easy_impersonate_list();
    int found = 0;
    struct curl_slist *item;
    for(item = list; item; item = item->next) {
        if(strcmp(item->data, XWEB_TARGET) == 0) {
            found = 1;
            break;
        }
    }
    if(found) {
        char msg[128];
        snprintf(msg, sizeof(msg), "Target '%s' appears in impersonate_list", XWEB_TARGET);
        TEST_PASS(msg);
    } else {
        char msg[128];
        snprintf(msg, sizeof(msg), "Target '%s' NOT found in impersonate_list", XWEB_TARGET);
        TEST_FAIL(msg);
    }
    curl_slist_free_all(list);
}

/* ── Test 4: HTTPS request with impersonation ───────────────────── */
static const char *TEST_URL = "https://120.26.33.71/json/detail";

static void test_https_request(const char *target_name, int default_headers)
{
    printf("\n=== Test 4: HTTPS request with impersonation (%s, default_headers=%d) ===\n",
           target_name, default_headers);

    CURL *curl = curl_easy_init();
    if(!curl) {
        TEST_FAIL("curl_easy_init() failed");
        return;
    }

    /* Apply impersonation */
    CURLcode res = curl_easy_impersonate(curl, target_name, default_headers);
    if(res != CURLE_OK) {
        char msg[256];
        snprintf(msg, sizeof(msg), "curl_easy_impersonate(curl, '%s', %d) failed: %d (%s)",
                 target_name, default_headers, res, curl_easy_strerror(res));
        TEST_FAIL(msg);
        curl_easy_cleanup(curl);
        return;
    }
    {
        char msg[256];
        snprintf(msg, sizeof(msg), "curl_easy_impersonate(curl, '%s', %d) succeeded", target_name, default_headers);
        TEST_PASS(msg);
    }

    /* Set URL and SSL options */
    curl_easy_setopt(curl, CURLOPT_URL, TEST_URL);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);

    /* Response buffer */
    struct response_buf buf = {NULL, 0};
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);

    /* Perform request */
    printf("  Requesting %s ...\n", TEST_URL);
    res = curl_easy_perform(curl);

    if(res == CURLE_OK) {
        TEST_PASS("curl_easy_perform() succeeded");

        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        char msg[128];
        snprintf(msg, sizeof(msg), "HTTP response code: %ld", http_code);
        TEST_PASS(msg);

        long http_version = 0;
        curl_easy_getinfo(curl, CURLINFO_HTTP_VERSION, &http_version);
        const char *hv_str = "unknown";
        switch(http_version) {
            case CURL_HTTP_VERSION_1_0: hv_str = "HTTP/1.0"; break;
            case CURL_HTTP_VERSION_1_1: hv_str = "HTTP/1.1"; break;
            case CURL_HTTP_VERSION_2_0: hv_str = "HTTP/2";   break;
            case CURL_HTTP_VERSION_3:   hv_str = "HTTP/3";   break;
            default: break;
        }
        snprintf(msg, sizeof(msg), "Negotiated protocol: %s", hv_str);
        if(http_version == CURL_HTTP_VERSION_2_0) TEST_PASS(msg);
        else { TEST_WARN(msg); printf("  (Expected HTTP/2 for XWEB)\n"); }

        if(buf.data && buf.size > 0) {
            printf("  Response body (%zu bytes):\n", buf.size);
            /* Print first 500 chars */
            size_t print_len = buf.size > 500 ? 500 : buf.size;
            printf("  %.500s\n", buf.data);
            TEST_PASS("Received response body");
        } else {
            TEST_WARN("Empty response body");
        }
    } else {
        char msg[256];
        snprintf(msg, sizeof(msg), "curl_easy_perform() failed: %d (%s)", res, curl_easy_strerror(res));
        TEST_FAIL(msg);
    }

    free(buf.data);
    curl_easy_cleanup(curl);
}

/* ── Test 5: Fingerprint verification via detail endpoint ───────── */
static void test_fingerprints(const char *target_name, const char *expected_ja4,
                               const char *expected_http2, const char *expected_ja3_ext_set)
{
    printf("\n=== Test 5: Fingerprint verification ===\n");
    printf("  Expected JA4:        %s\n", expected_ja4);
    printf("  Expected HTTP2:      %s\n", expected_http2);
    printf("  Expected JA3 exts:   %s\n", expected_ja3_ext_set);

    CURL *curl = curl_easy_init();
    if(!curl) {
        TEST_FAIL("curl_easy_init() failed");
        return;
    }

    CURLcode res = curl_easy_impersonate(curl, target_name, 1);
    if(res != CURLE_OK) {
        TEST_FAIL("curl_easy_impersonate() failed for fingerprint test");
        curl_easy_cleanup(curl);
        return;
    }

    curl_easy_setopt(curl, CURLOPT_URL, TEST_URL);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);

    struct response_buf buf = {NULL, 0};
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);

    res = curl_easy_perform(curl);
    if(res != CURLE_OK) {
        char msg[256];
        snprintf(msg, sizeof(msg), "Request failed: %d (%s)", res, curl_easy_strerror(res));
        TEST_FAIL(msg);
        curl_easy_cleanup(curl);
        free(buf.data);
        return;
    }

    if(!buf.data || buf.size == 0) {
        TEST_FAIL("Empty response - cannot verify fingerprints");
        curl_easy_cleanup(curl);
        free(buf.data);
        return;
    }

    /* The /json/detail endpoint returns JSON with:
     * ja3, ja4, http2 fingerprints that the server observed */
    printf("  Server response (%zu bytes):\n", buf.size);

    /* Extract observed fingerprints from server response */
    char observed_ja3[512] = {0};
    char observed_ja4[256] = {0};
    char observed_http2[512] = {0};

    /* Try to find ja4 fingerprint in response */
    find_json_string_value(buf.data, "ja4", observed_ja4, sizeof(observed_ja4));
    find_json_string_value(buf.data, "http2", observed_http2, sizeof(observed_http2));
    find_json_string_value(buf.data, "ja3", observed_ja3, sizeof(observed_ja3));

    /* If the server returns the full detail object, ja4 may be nested */
    /* Try alternative key names */
    if(observed_ja4[0] == '\0') {
        find_json_string_value(buf.data, "tls_ja4", observed_ja4, sizeof(observed_ja4));
    }

    printf("  Observed JA4:        %s\n", observed_ja4[0] ? observed_ja4 : "(not found in response)");
    printf("  Observed HTTP2:      %s\n", observed_http2[0] ? observed_http2 : "(not found in response)");
    printf("  Observed JA3:        %s\n", observed_ja3[0] ? observed_ja3 : "(not found in response)");

    /* JA4 comparison - MUST match exactly */
    if(observed_ja4[0] && expected_ja4[0]) {
        if(strcmp(observed_ja4, expected_ja4) == 0) {
            char msg[256];
            snprintf(msg, sizeof(msg), "JA4 fingerprint MATCH: %s", observed_ja4);
            TEST_PASS(msg);
        } else {
            char msg[256];
            snprintf(msg, sizeof(msg), "JA4 fingerprint MISMATCH: got '%s', expected '%s'", observed_ja4, expected_ja4);
            TEST_FAIL(msg);
        }
    } else {
        TEST_WARN("Cannot verify JA4 - not found in server response");
    }

    /* HTTP2 fingerprint comparison - MUST match exactly */
    if(observed_http2[0] && expected_http2[0]) {
        if(strcmp(observed_http2, expected_http2) == 0) {
            char msg[256];
            snprintf(msg, sizeof(msg), "HTTP2 fingerprint MATCH: %s", observed_http2);
            TEST_PASS(msg);
        } else {
            char msg[256];
            snprintf(msg, sizeof(msg), "HTTP2 fingerprint MISMATCH: got '%s', expected '%s'", observed_http2, expected_http2);
            TEST_FAIL(msg);
        }
    } else {
        TEST_WARN("Cannot verify HTTP2 fingerprint - not found in server response");
    }

    /* JA3 extension SET comparison (order doesn't matter) */
    if(observed_ja3[0] && expected_ja3_ext_set[0]) {
        /* Parse comma-separated extension IDs into sets and compare */
        int ext_set_obs[64] = {0}, ext_set_exp[64] = {0};
        int n_obs = 0, n_exp = 0;

        /* Parse observed extensions from JA3 raw format: version,ciphers,extensions,groups,points */
        /* The extensions field is the 3rd component */
        char ja3_raw_obs[512] = {0};
        find_json_string_value(buf.data, "ja3_raw", ja3_raw_obs, sizeof(ja3_raw_obs));

        if(ja3_raw_obs[0]) {
            /* Find the 3rd field (extensions) */
            char *p = ja3_raw_obs;
            int field = 0;
            while(field < 2 && *p) { if(*p == ',') field++; p++; }
            if(*p) {
                char ext_str[256] = {0};
                int i = 0;
                while(*p && *p != ',' && i < 255) ext_str[i++] = *p++;
                ext_str[i] = '\0';

                /* Parse dash-separated values */
                char *tok = strtok(ext_str, "-");
                while(tok && n_obs < 64) {
                    ext_set_obs[n_obs++] = atoi(tok);
                    tok = strtok(NULL, "-");
                }
            }
        }

        /* Parse expected extension set */
        {
            char exp_copy[512];
            strncpy(exp_copy, expected_ja3_ext_set, sizeof(exp_copy) - 1);
            char *tok = strtok(exp_copy, "-");
            while(tok && n_exp < 64) {
                ext_set_exp[n_exp++] = atoi(tok);
                tok = strtok(NULL, "-");
            }
        }

        /* Sort both and compare as sets */
        /* Simple bubble sort */
        int j, k, tmp;
        for(j = 0; j < n_obs - 1; j++)
            for(k = 0; k < n_obs - 1 - j; k++)
                if(ext_set_obs[k] > ext_set_obs[k+1]) { tmp = ext_set_obs[k]; ext_set_obs[k] = ext_set_obs[k+1]; ext_set_obs[k+1] = tmp; }
        for(j = 0; j < n_exp - 1; j++)
            for(k = 0; k < n_exp - 1 - j; k++)
                if(ext_set_exp[k] > ext_set_exp[k+1]) { tmp = ext_set_exp[k]; ext_set_exp[k] = ext_set_exp[k+1]; ext_set_exp[k+1] = tmp; }

        /* Compare */
        int set_match = (n_obs == n_exp);
        if(set_match) {
            for(j = 0; j < n_obs; j++) {
                if(ext_set_obs[j] != ext_set_exp[j]) { set_match = 0; break; }
            }
        }

        if(set_match) {
            char msg[256];
            snprintf(msg, sizeof(msg), "JA3 extension SET match (%d extensions)", n_obs);
            TEST_PASS(msg);
        } else {
            char msg[256];
            snprintf(msg, sizeof(msg), "JA3 extension SET mismatch: got %d, expected %d extensions", n_obs, n_exp);
            TEST_FAIL(msg);
            printf("  Observed exts: ");
            for(j = 0; j < n_obs; j++) printf("%d%s", ext_set_obs[j], j < n_obs-1 ? "-" : "");
            printf("\n  Expected exts: ");
            for(j = 0; j < n_exp; j++) printf("%d%s", ext_set_exp[j], j < n_exp-1 ? "-" : "");
            printf("\n");
        }
    } else {
        TEST_WARN("Cannot verify JA3 extension set - missing data");
    }

    free(buf.data);
    curl_easy_cleanup(curl);
}

/* ── Test 6: Built-in impersonation request ─────────────────────── */
static void test_builtin_chrome_request(void)
{
    printf("\n=== Test 6: Built-in Chrome impersonation request ===\n");

    /* Try a common Chrome target */
    const char *targets[] = {"chrome124", "chrome123", "chrome120", "chrome116", "chrome110", NULL};
    const char *used_target = NULL;

    struct curl_slist *list = curl_easy_impersonate_list();
    for(int i = 0; targets[i]; i++) {
        struct curl_slist *item;
        for(item = list; item; item = item->next) {
            if(strcmp(item->data, targets[i]) == 0) {
                used_target = targets[i];
                break;
            }
        }
        if(used_target) break;
    }
    curl_slist_free_all(list);

    if(!used_target) {
        TEST_WARN("No built-in Chrome target found, skipping");
        return;
    }

    CURL *curl = curl_easy_init();
    if(!curl) { TEST_FAIL("curl_easy_init() failed"); return; }

    CURLcode res = curl_easy_impersonate(curl, used_target, 1);
    if(res != CURLE_OK) {
        char msg[128];
        snprintf(msg, sizeof(msg), "curl_easy_impersonate('%s') failed", used_target);
        TEST_FAIL(msg);
        curl_easy_cleanup(curl);
        return;
    }

    curl_easy_setopt(curl, CURLOPT_URL, TEST_URL);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 10L);

    struct response_buf buf = {NULL, 0};
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);

    printf("  Testing built-in target: %s\n", used_target);
    res = curl_easy_perform(curl);

    if(res == CURLE_OK) {
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        char msg[128];
        snprintf(msg, sizeof(msg), "Built-in '%s': HTTP %ld, %zu bytes response",
                 used_target, http_code, buf.size);
        TEST_PASS(msg);

        if(buf.data) {
            printf("  Response preview: %.300s\n", buf.data);
        }
    } else {
        char msg[256];
        snprintf(msg, sizeof(msg), "Built-in '%s' request failed: %d (%s)",
                 used_target, res, curl_easy_strerror(res));
        TEST_FAIL(msg);
    }

    free(buf.data);
    curl_easy_cleanup(curl);
}

/* ── Main ───────────────────────────────────────────────────────── */
int main(int argc, char *argv[])
{
    printf("================================================================\n");
    printf("  libcurl-impersonate DLL Verification\n");
    printf("================================================================\n\n");

    /* Initialize curl globally */
    curl_global_init(CURL_GLOBAL_ALL);

    /* Load XWEB.json if provided */
    char *xweb_json = NULL;
    char expected_ja4[256] = {0};
    char expected_http2[512] = {0};
    char expected_ja3_exts[512] = {0};  /* dash-separated extension IDs */

    if(argc > 1) {
        xweb_json = read_file(argv[1], NULL);
        if(xweb_json) {
            printf("  Loaded XWEB.json from: %s (%zu bytes)\n", argv[1], strlen(xweb_json));

            /* Extract expected values */
            find_json_string_value(xweb_json, "ja4", expected_ja4, sizeof(expected_ja4));
            find_json_string_value(xweb_json, "http2", expected_http2, sizeof(expected_http2));

            /* JA3 extension IDs from detail.ja3.AllExtensions (dash-separated in ja3_raw) */
            /* ja3_raw format: version,ciphers-...,extensions-...,groups-...,points */
            char ja3_raw[512] = {0};
            find_json_string_value(xweb_json, "ja3_raw", ja3_raw, sizeof(ja3_raw));
            if(ja3_raw[0]) {
                /* Find 3rd field (extensions) */
                char *p = ja3_raw;
                int field = 0;
                while(field < 2 && *p) { if(*p == ',') field++; p++; }
                if(*p) {
                    int i = 0;
                    while(*p && *p != ',' && i < 511) {
                        expected_ja3_exts[i++] = *p++;
                    }
                    expected_ja3_exts[i] = '\0';
                }
            }

            printf("  Expected JA4:      %s\n", expected_ja4);
            printf("  Expected HTTP2:    %s\n", expected_http2);
            printf("  Expected JA3 exts: %s\n", expected_ja3_exts);
        } else {
            printf("  WARNING: Could not read %s\n", argv[1]);
        }
    } else {
        printf("  Usage: %s <path_to_XWEB.json>\n", argv[0]);
        printf("  Running basic tests without XWEB registration...\n\n");
    }

    /* Run tests */
    test_basic_curl();
    test_builtin_impersonate();

    if(xweb_json) {
        test_register_impersonate(xweb_json);
        test_https_request(XWEB_TARGET, 1);
        test_fingerprints(XWEB_TARGET, expected_ja4, expected_http2, expected_ja3_exts);
    }

    test_builtin_chrome_request();

    /* Summary */
    printf("\n================================================================\n");
    printf("  SUMMARY: %d PASS, %d FAIL, %d WARN\n", g_pass, g_fail, g_warn);
    printf("================================================================\n");

    /* Cleanup */
    free(xweb_json);
    curl_global_cleanup();

    return g_fail > 0 ? 1 : 0;
}

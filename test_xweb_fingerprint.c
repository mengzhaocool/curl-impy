/*
 * XWEB Browser Fingerprint Verification Test
 *
 * 1. Register XWEB.json fingerprint via curl_easy_impersonate_register()
 * 2. Access https://120.26.33.71/json/detail (self-signed cert)
 * 3. Compare fingerprints:
 *    - JA4:       MUST match exactly
 *    - H2:        MUST match exactly
 *    - Extensions: SET must match (order is random, that's OK)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

/* ---- Response buffer ---- */
struct resp_buf {
    char *data;
    size_t size;
};

static size_t write_cb(void *ptr, size_t size, size_t nmemb, void *ud)
{
    struct resp_buf *buf = (struct resp_buf *)ud;
    size_t total = size * nmemb;
    char *p = realloc(buf->data, buf->size + total + 1);
    if(!p) return 0;
    buf->data = p;
    memcpy(buf->data + buf->size, ptr, total);
    buf->size += total;
    buf->data[buf->size] = '\0';
    return total;
}

/* ---- Read file into malloc'd string ---- */
static char *read_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    char *buf;
    long len;
    if(!f) return NULL;
    fseek(f, 0, SEEK_END);
    len = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = malloc(len + 1);
    if(!buf) { fclose(f); return NULL; }
    fread(buf, 1, len, f);
    buf[len] = '\0';
    fclose(f);
    return buf;
}

/* ---- Simple JSON string extraction (no cJSON dependency) ---- */
static char *extract_json_string(const char *json, const char *key)
{
    char search[256];
    const char *p;
    const char *start, *end;
    size_t klen;

    snprintf(search, sizeof(search), "\"%s\"", key);
    p = strstr(json, search);
    if(!p) return NULL;
    p += strlen(search);
    /* skip whitespace and colon */
    while(*p && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r' || *p == ':'))
        p++;
    if(*p != '"') return NULL;
    p++;
    start = p;
    end = strchr(p, '"');
    if(!end) return NULL;
    klen = end - start;
    {
        char *result = malloc(klen + 1);
        memcpy(result, start, klen);
        result[klen] = '\0';
        return result;
    }
}

/* ---- Extract ja4 fingerprint string from XWEB.json or server response ----
 * XWEB.json has: "ja4":"t13i1515h2_8daaf6152771_02713d6af862" (top-level string)
 *                AND "ja4":{"Protocol":116,...} (under detail, as object)
 * Server response has: "ja4":"t13i1515h2_..."
 * We search for the LAST occurrence of "ja4" followed by a string value,
 * which works for both formats since the top-level string comes after
 * the detail object in the JSON. */
static char *extract_ja4_fingerprint(const char *json)
{
    const char *p = json;
    const char *last_match = NULL;
    const char *start, *end;
    size_t klen;
    char *result = NULL;

    /* Find all occurrences of "ja4" and keep the last one that's a string */
    while((p = strstr(p, "\"ja4\"")) != NULL) {
        const char *after = p + 5; /* skip "ja4" */
        while(*after && (*after == ' ' || *after == '\t' || *after == '\n' ||
                         *after == '\r' || *after == ':'))
            after++;
        if(*after == '"') {
            last_match = after;
        }
        p = after;
    }

    if(!last_match) return NULL;

    /* Extract the string value */
    start = last_match + 1; /* skip opening quote */
    end = strchr(start, '"');
    if(!end) return NULL;
    klen = end - start;
    result = malloc(klen + 1);
    if(!result) return NULL;
    memcpy(result, start, klen);
    result[klen] = '\0';
    return result;
}

/* ---- Extract http2 fingerprint string ---- */
static char *extract_http2(const char *json)
{
    const char *p = strstr(json, "\"http2\"");
    const char *start, *end;
    size_t klen;
    if(!p) return NULL;
    p += 7;
    while(*p && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r' || *p == ':'))
        p++;
    if(*p != '"') return NULL;
    p++;
    start = p;
    end = strchr(p, '"');
    if(!end) return NULL;
    klen = end - start;
    {
        char *result = malloc(klen + 1);
        memcpy(result, start, klen);
        result[klen] = '\0';
        return result;
    }
}

/* ---- Extract ja3_raw string ---- */
static char *extract_ja3_raw(const char *json)
{
    const char *p = strstr(json, "\"ja3_raw\"");
    const char *start, *end;
    size_t klen;
    if(!p) return NULL;
    p += 9;
    while(*p && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r' || *p == ':'))
        p++;
    if(*p != '"') return NULL;
    p++;
    start = p;
    end = strchr(p, '"');
    if(!end) return NULL;
    klen = end - start;
    {
        char *result = malloc(klen + 1);
        memcpy(result, start, klen);
        result[klen] = '\0';
        return result;
    }
}

/* ---- Extract the extensions segment from JA3_raw ----
 * JA3_raw format: version,ciphers,extensions,groups,points
 * Returns the extensions segment (dash-separated IDs) as a sorted set string.
 */
static char *extract_extensions_sorted(const char *ja3_raw)
{
    const char *p = ja3_raw;
    const char *seg_start, *seg_end;
    int comma_count = 0;
    size_t len;
    char *ext_seg, *sorted;
    int ids[64], count = 0;
    char buf[512];
    int buf_len = 0;
    int i, j;

    /* Find the 3rd segment (extensions) - between 2nd and 3rd commas */
    while(*p && comma_count < 2) {
        if(*p == ',') comma_count++;
        p++;
    }
    if(comma_count < 2) return NULL;
    seg_start = p;
    seg_end = strchr(p, ',');
    if(!seg_end) return NULL;
    len = seg_end - seg_start;

    ext_seg = malloc(len + 1);
    if(!ext_seg) return NULL;
    memcpy(ext_seg, seg_start, len);
    ext_seg[len] = '\0';

    /* Parse dash-separated IDs into array */
    {
        char *tok = strtok(ext_seg, "-");
        while(tok && count < 64) {
            ids[count++] = atoi(tok);
            tok = strtok(NULL, "-");
        }
    }

    free(ext_seg);

    if(count == 0) return NULL;

    /* Bubble sort (small array, fine) */
    for(i = 0; i < count - 1; i++) {
        for(j = 0; j < count - i - 1; j++) {
            if(ids[j] > ids[j+1]) {
                int tmp = ids[j];
                ids[j] = ids[j+1];
                ids[j+1] = tmp;
            }
        }
    }

    /* Build sorted string */
    for(i = 0; i < count; i++) {
        if(i > 0) buf[buf_len++] = '-';
        buf_len += snprintf(buf + buf_len, sizeof(buf) - buf_len, "%d", ids[i]);
    }
    buf[buf_len] = '\0';

    sorted = malloc(buf_len + 1);
    if(!sorted) return NULL;
    memcpy(sorted, buf, buf_len + 1);
    return sorted;
}

/* ---- Extract the cipher suites segment from JA3_raw ---- */
static char *extract_ciphers_sorted(const char *ja3_raw)
{
    const char *p = ja3_raw;
    const char *seg_start, *seg_end;
    int comma_count = 0;
    size_t len;
    char *ciph_seg, *sorted;
    int ids[64], count = 0;
    char buf[512];
    int buf_len = 0;
    int i, j;

    /* Find the 2nd segment (ciphers) - between 1st and 2nd commas */
    while(*p && comma_count < 1) {
        if(*p == ',') comma_count++;
        p++;
    }
    if(comma_count < 1) return NULL;
    seg_start = p;
    seg_end = strchr(p, ',');
    if(!seg_end) return NULL;
    len = seg_end - seg_start;

    ciph_seg = malloc(len + 1);
    if(!ciph_seg) return NULL;
    memcpy(ciph_seg, seg_start, len);
    ciph_seg[len] = '\0';

    /* Parse dash-separated IDs into array */
    {
        char *tok = strtok(ciph_seg, "-");
        while(tok && count < 64) {
            ids[count++] = atoi(tok);
            tok = strtok(NULL, "-");
        }
    }

    free(ciph_seg);

    if(count == 0) return NULL;

    /* Bubble sort */
    for(i = 0; i < count - 1; i++) {
        for(j = 0; j < count - i - 1; j++) {
            if(ids[j] > ids[j+1]) {
                int tmp = ids[j];
                ids[j] = ids[j+1];
                ids[j+1] = tmp;
            }
        }
    }

    /* Build sorted string */
    for(i = 0; i < count; i++) {
        if(i > 0) buf[buf_len++] = '-';
        buf_len += snprintf(buf + buf_len, sizeof(buf) - buf_len, "%d", ids[i]);
    }
    buf[buf_len] = '\0';

    sorted = malloc(buf_len + 1);
    if(!sorted) return NULL;
    memcpy(sorted, buf, buf_len + 1);
    return sorted;
}

/* ---- Extract the groups segment from JA3_raw ---- */
static char *extract_groups_sorted(const char *ja3_raw)
{
    const char *p = ja3_raw;
    const char *seg_start, *seg_end;
    int comma_count = 0;
    size_t len;
    char *grp_seg, *sorted;
    int ids[32], count = 0;
    char buf[256];
    int buf_len = 0;
    int i, j;

    /* Find the 4th segment (groups) - between 3rd and 4th commas */
    while(*p && comma_count < 3) {
        if(*p == ',') comma_count++;
        p++;
    }
    if(comma_count < 3) return NULL;
    seg_start = p;
    seg_end = strchr(p, ',');
    if(!seg_end) return NULL;
    len = seg_end - seg_start;

    grp_seg = malloc(len + 1);
    if(!grp_seg) return NULL;
    memcpy(grp_seg, seg_start, len);
    grp_seg[len] = '\0';

    /* Parse dash-separated IDs into array */
    {
        char *tok = strtok(grp_seg, "-");
        while(tok && count < 32) {
            ids[count++] = atoi(tok);
            tok = strtok(NULL, "-");
        }
    }

    free(grp_seg);

    if(count == 0) return NULL;

    /* Bubble sort */
    for(i = 0; i < count - 1; i++) {
        for(j = 0; j < count - i - 1; j++) {
            if(ids[j] > ids[j+1]) {
                int tmp = ids[j];
                ids[j] = ids[j+1];
                ids[j+1] = tmp;
            }
        }
    }

    /* Build sorted string */
    for(i = 0; i < count; i++) {
        if(i > 0) buf[buf_len++] = '-';
        buf_len += snprintf(buf + buf_len, sizeof(buf) - buf_len, "%d", ids[i]);
    }
    buf[buf_len] = '\0';

    sorted = malloc(buf_len + 1);
    if(!sorted) return NULL;
    memcpy(sorted, buf, buf_len + 1);
    return sorted;
}

/* ---- Main ---- */
int main(void)
{
    CURL *curl;
    CURLcode res;
    struct resp_buf resp = {NULL, 0};
    char *xweb_json = NULL;
    char *expected_ja4 = NULL;
    char *expected_http2 = NULL;
    char *expected_ja3_raw = NULL;
    char *actual_ja4 = NULL;
    char *actual_http2 = NULL;
    char *actual_ja3_raw = NULL;
    long http_code = 0;
    int pass = 1;

    printf("=== XWEB Browser Fingerprint Verification ===\n\n");

    /* 1. Load XWEB.json */
    xweb_json = read_file("D:\\curl-impersonate\\XWEB.json");
    if(!xweb_json) {
        printf("FAIL: Cannot read D:\\curl-impersonate\\XWEB.json\n");
        return 1;
    }
    printf("[OK] Loaded XWEB.json (%zu bytes)\n", strlen(xweb_json));

    /* 2. Extract expected values from XWEB.json */
    expected_ja4 = extract_ja4_fingerprint(xweb_json);
    expected_http2 = extract_http2(xweb_json);
    expected_ja3_raw = extract_ja3_raw(xweb_json);

    printf("\n--- Expected (from XWEB.json) ---\n");
    if(expected_ja4)
        printf("  JA4:       %s\n", expected_ja4);
    if(expected_http2)
        printf("  HTTP/2:    %s\n", expected_http2);
    if(expected_ja3_raw)
        printf("  JA3_raw:   %s\n", expected_ja3_raw);

    /* 3. Initialize curl */
    if(curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        printf("FAIL: curl_global_init() failed\n");
        return 1;
    }

    /* 4. Register XWEB browser */
    res = curl_easy_impersonate_register("xweb", xweb_json);
    if(res != CURLE_OK) {
        printf("FAIL: curl_easy_impersonate_register('xweb') failed: %s\n",
               curl_easy_strerror(res));
        return 1;
    }
    printf("\n[OK] Registered 'xweb' browser impersonation\n");

    /* 5. Create curl handle and impersonate */
    curl = curl_easy_init();
    if(!curl) {
        printf("FAIL: curl_easy_init() failed\n");
        return 1;
    }

    res = curl_easy_impersonate(curl, "xweb", 1);
    if(res != CURLE_OK) {
        printf("FAIL: curl_easy_impersonate('xweb') failed: %s\n",
               curl_easy_strerror(res));
        curl_easy_cleanup(curl);
        return 1;
    }
    printf("[OK] curl_easy_impersonate('xweb') succeeded\n");

    /* 6. Configure request */
    curl_easy_setopt(curl, CURLOPT_URL, "https://120.26.33.71/json/detail");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &resp);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    printf("\n--- Connecting to https://120.26.33.71/json/detail ---\n");
    res = curl_easy_perform(curl);
    if(res != CURLE_OK) {
        printf("FAIL: HTTP request failed: %s\n", curl_easy_strerror(res));
        curl_easy_cleanup(curl);
        return 1;
    }

    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    printf("[OK] HTTP %ld (%zu bytes response)\n", http_code, resp.size);

    /* 7. Extract actual values from server response */
    if(resp.data) {
        actual_ja4 = extract_ja4_fingerprint(resp.data);
        actual_http2 = extract_http2(resp.data);
        actual_ja3_raw = extract_ja3_raw(resp.data);

        printf("\n--- Actual (from server response) ---\n");
        if(actual_ja4)
            printf("  JA4:       %s\n", actual_ja4);
        if(actual_http2)
            printf("  HTTP/2:    %s\n", actual_http2);
        if(actual_ja3_raw)
            printf("  JA3_raw:   %s\n", actual_ja3_raw);
    }

    /* 8. Compare */
    printf("\n=== Fingerprint Comparison ===\n\n");

    /* JA4 comparison - MUST MATCH */
    if(expected_ja4 && actual_ja4) {
        if(strcmp(expected_ja4, actual_ja4) == 0) {
            printf("  [PASS] JA4 fingerprint MATCH (required)\n");
            printf("         %s\n", actual_ja4);
        } else {
            printf("  [FAIL] JA4 fingerprint MISMATCH (required)\n");
            printf("         Expected: %s\n", expected_ja4);
            printf("         Actual:   %s\n", actual_ja4);
            pass = 0;
        }
    } else {
        printf("  [SKIP] JA4: could not extract from one or both sources\n");
        pass = 0;
    }

    /* HTTP/2 fingerprint comparison - MUST MATCH */
    if(expected_http2 && actual_http2) {
        if(strcmp(expected_http2, actual_http2) == 0) {
            printf("  [PASS] HTTP/2 fingerprint MATCH (required)\n");
            printf("         %s\n", actual_http2);
        } else {
            printf("  [FAIL] HTTP/2 fingerprint MISMATCH (required)\n");
            printf("         Expected: %s\n", expected_http2);
            printf("         Actual:   %s\n", actual_http2);
            pass = 0;
        }
    } else {
        printf("  [SKIP] HTTP/2: could not extract\n");
        pass = 0;
    }

    /* TLS extension/cipher/group SET comparison - order doesn't matter */
    if(expected_ja3_raw && actual_ja3_raw) {
        char *exp_ext_sorted = extract_extensions_sorted(expected_ja3_raw);
        char *act_ext_sorted = extract_extensions_sorted(actual_ja3_raw);
        char *exp_ciph_sorted = extract_ciphers_sorted(expected_ja3_raw);
        char *act_ciph_sorted = extract_ciphers_sorted(actual_ja3_raw);
        char *exp_grp_sorted = extract_groups_sorted(expected_ja3_raw);
        char *act_grp_sorted = extract_groups_sorted(actual_ja3_raw);
        int set_match = 1;

        printf("  [INFO] JA3_raw comparison (extension/cipher/group SETS, order irrelevant)\n");

        /* Cipher suites SET comparison */
        if(exp_ciph_sorted && act_ciph_sorted) {
            if(strcmp(exp_ciph_sorted, act_ciph_sorted) == 0) {
                printf("    Cipher suites SET:  MATCH\n");
            } else {
                printf("    Cipher suites SET:  DIFF\n");
                printf("      Expected (sorted): %s\n", exp_ciph_sorted);
                printf("      Actual (sorted):   %s\n", act_ciph_sorted);
                set_match = 0;
            }
        }

        /* Extension SET comparison */
        if(exp_ext_sorted && act_ext_sorted) {
            if(strcmp(exp_ext_sorted, act_ext_sorted) == 0) {
                printf("    Extensions SET:     MATCH\n");
            } else {
                printf("    Extensions SET:     DIFF\n");
                printf("      Expected (sorted): %s\n", exp_ext_sorted);
                printf("      Actual (sorted):   %s\n", act_ext_sorted);
                set_match = 0;
            }
        }

        /* Group SET comparison */
        if(exp_grp_sorted && act_grp_sorted) {
            if(strcmp(exp_grp_sorted, act_grp_sorted) == 0) {
                printf("    Groups SET:         MATCH\n");
            } else {
                printf("    Groups SET:         DIFF\n");
                printf("      Expected (sorted): %s\n", exp_grp_sorted);
                printf("      Actual (sorted):   %s\n", act_grp_sorted);
                set_match = 0;
            }
        }

        if(set_match) {
            printf("  [PASS] TLS fingerprint SET MATCH (order random, that's OK)\n");
        } else {
            printf("  [FAIL] TLS fingerprint SET MISMATCH\n");
            pass = 0;
        }

        free(exp_ext_sorted);
        free(act_ext_sorted);
        free(exp_ciph_sorted);
        free(act_ciph_sorted);
        free(exp_grp_sorted);
        free(act_grp_sorted);
    } else {
        printf("  [SKIP] JA3_raw: could not extract\n");
    }

    /* 9. Print full response for reference */
    printf("\n--- Full Server Response ---\n");
    if(resp.data) {
        /* Print first 2000 chars */
        size_t print_len = resp.size > 2000 ? 2000 : resp.size;
        printf("%.*s\n", (int)print_len, resp.data);
    }

    /* Cleanup */
    curl_easy_cleanup(curl);
    curl_global_cleanup();
    free(resp.data);
    free(xweb_json);
    free(expected_ja4);
    free(expected_http2);
    free(expected_ja3_raw);
    free(actual_ja4);
    free(actual_http2);
    free(actual_ja3_raw);

    printf("\n=== Result: %s ===\n", pass ? "ALL MATCH" : "MISMATCH DETECTED");
    return pass ? 0 : 1;
}

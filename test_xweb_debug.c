/*
 * XWEB Browser Fingerprint Verification Test - Debug Version
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

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

int main(void)
{
    CURL *curl;
    CURLcode res;
    struct resp_buf resp = {NULL, 0};
    char *xweb_json = NULL;
    long http_code = 0;
    struct curl_slist *list, *item;
    int found = 0;

    printf("=== XWEB Debug Test ===\n\n");

    xweb_json = read_file("D:\\curl-impersonate\\XWEB.json");
    if(!xweb_json) {
        printf("FAIL: Cannot read XWEB.json\n");
        return 1;
    }
    printf("Loaded XWEB.json (%zu bytes)\n", strlen(xweb_json));

    curl_global_init(CURL_GLOBAL_DEFAULT);

    /* Register */
    res = curl_easy_impersonate_register("xweb", xweb_json);
    printf("Register: %d (%s)\n", res, curl_easy_strerror(res));

    /* Check list */
    list = curl_easy_impersonate_list();
    for(item = list; item; item = item->next) {
        if(strcmp(item->data, "xweb") == 0) found = 1;
        printf("  Target: %s\n", item->data);
    }
    curl_slist_free_all(list);
    printf("xweb found in list: %s\n", found ? "YES" : "NO");

    /* Create handle and impersonate */
    curl = curl_easy_init();
    res = curl_easy_impersonate(curl, "xweb", 1);
    printf("Impersonate: %d (%s)\n", res, curl_easy_strerror(res));

    /* Print key settings */
    {
        char *h2_settings = NULL;
        char *h2_pseudo = NULL;
        long h2_window = 0;
        long stream_weight = 0;
        long stream_exclusive = 0;
        char *ext_order = NULL;

        curl_easy_getinfo(curl, CURLINFO_HTTP2_SETTINGS, &h2_settings);
        printf("HTTP2 settings: %s\n", h2_settings ? h2_settings : "(null)");
    }

    /* Set URL */
    curl_easy_setopt(curl, CURLOPT_URL, "https://120.26.33.71/json/detail");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &resp);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    printf("\nConnecting...\n");
    res = curl_easy_perform(curl);
    if(res != CURLE_OK) {
        printf("FAIL: %s\n", curl_easy_strerror(res));
        curl_easy_cleanup(curl);
        return 1;
    }

    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    printf("HTTP %ld (%zu bytes)\n", http_code, resp.size);

    if(resp.data) {
        /* Print first 3000 chars */
        size_t len = resp.size > 3000 ? 3000 : resp.size;
        printf("\n--- Response ---\n%.*s\n", (int)len, resp.data);
    }

    curl_easy_cleanup(curl);
    curl_global_cleanup();
    free(resp.data);
    free(xweb_json);

    return 0;
}

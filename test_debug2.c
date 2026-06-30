#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "deps/curl-8.20.0/include/curl/curl.h"

int main(void)
{
    CURL *curl;
    CURLcode res;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    curl = curl_easy_init();
    if(!curl) {
        fprintf(stderr, "curl_easy_init() failed\n");
        return 1;
    }

    fprintf(stderr, "About to call curl_easy_impersonate('chrome120')...\n");
    fflush(stderr);
    res = curl_easy_impersonate(curl, "chrome120", 1);
    fprintf(stderr, "Result: %d (%s)\n", res, curl_easy_strerror(res));
    fflush(stderr);

    if(res == CURLE_OK) {
        printf("SUCCESS\n");
    } else {
        printf("FAILED: %d (%s)\n", res, curl_easy_strerror(res));
    }

    curl_easy_cleanup(curl);
    curl_global_cleanup();
    return 0;
}

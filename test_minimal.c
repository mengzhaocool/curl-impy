/* Minimal test: just list browser targets */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

int main(void)
{
  struct curl_slist *list, *item;
  int count = 0;

  printf("curl-impersonate minimal test\n");

  if(curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
    printf("FATAL: curl_global_init() failed\n");
    return 1;
  }
  printf("curl_global_init() OK\n");

  /* Test curl_easy_impersonate_list */
  printf("Calling curl_easy_impersonate_list()...\n");
  fflush(stdout);
  list = curl_easy_impersonate_list();
  printf("Returned: %p\n", (void*)list);
  fflush(stdout);

  if(list) {
    for(item = list; item; item = item->next) {
      printf("  - %s\n", item->data);
      count++;
    }
    curl_slist_free_all(list);
  }
  printf("Listed %d targets\n", count);

  /* Test curl_easy_init + curl_easy_impersonate */
  printf("\nTesting curl_easy_impersonate...\n");
  fflush(stdout);
  CURL *curl = curl_easy_init();
  if(curl) {
    printf("curl_easy_init() OK\n");
    CURLcode res = curl_easy_impersonate(curl, "chrome120", 1);
    printf("curl_easy_impersonate('chrome120') = %d (%s)\n", res, curl_easy_strerror(res));
    curl_easy_cleanup(curl);
  }

  curl_global_cleanup();
  printf("\nDone\n");
  return 0;
}

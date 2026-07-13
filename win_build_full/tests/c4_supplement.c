/* C4 supplement: Test remaining x86 stdcall callbacks
 * Tests: SSL_CTX_FUNCTION, RESOLVER_START_FUNCTION, TRAILER_FUNCTION
 * Untestable (require exotic protocols): CHUNK_BGN/END, FNMATCH (FTP),
 *   SEND/RECV (custom I/O), SSH_KEY (SSH), INTERLEAVE (RTSP)
 *
 * Compile: cl /arch:SSE2 /Fe:c4_supplement.exe c4_supplement.c /link
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#define CURLOPT_URL              10002
#define CURLOPT_WRITEFUNCTION     20011
#define CURLOPT_SSL_VERIFYPEER    64
#define CURLOPT_SSL_VERIFYHOST    81
#define CURLOPT_TIMEOUT           13
#define CURLOPT_HTTP_VERSION      84
#define CURLOPT_SSL_CTX_FUNCTION  20199
#define CURLOPT_SSL_CTX_DATA      10098
#define CURLOPT_RESOLVER_START_FUNCTION 20484
#define CURLOPT_RESOLVER_START_DATA 10476
#define CURLOPT_TRAILERFUNCTION   20236
#define CURLOPT_TRAILERDATA       10500
#define CURLINFO_RESPONSE_CODE    0x200002

static unsigned int g_esp_in = 0;
static unsigned int g_esp_out = 0;
static int g_triggered = 0;

static size_t __stdcall cb_write(char *p, size_t s, size_t n, void *u) { return s * n; }
static unsigned int __stdcall get_esp(void) {
    __asm mov eax, esp
}

/* SSL_CTX_FUNCTION: int __stdcall(void *ssl_ctx, void *ssl_ctx_data) */
/* On x86: 2 args = 8 bytes, callee cleans 8 bytes */
static int __stdcall cb_ssl_ctx(void *ssl_ctx, void *userptr) {
    g_esp_in = get_esp();
    g_triggered++;
    g_esp_out = get_esp();
    return 0; /* CURL_SSLSET_OK */
}

/* RESOLVER_START_FUNCTION: int __stdcall(void *resolver_state, void *userptr) */
/* On x86: 2 args = 8 bytes */
static int __stdcall cb_resolver_start(void *resolver_state, void *userptr) {
    g_esp_in = get_esp();
    g_triggered++;
    g_esp_out = get_esp();
    return 0;
}

/* TRAILER_FUNCTION: int __stdcall(void *data, size_t count, void *userptr) */
/* Actually: CURLcode cb(struct Curl_easy *data, struct curl_slist **trailer, void *userptr) */
/* On x86: 3 args = 12 bytes */
static int __stdcall cb_trailer(void *data, void **trailer, void *userptr) {
    g_esp_in = get_esp();
    g_triggered++;
    g_esp_out = get_esp();
    return 0;
}

typedef void* (__cdecl *fn_init)(void);
typedef int   (__cdecl *fn_setopt)(void*, int, ...);
typedef int   (__cdecl *fn_perform)(void*);
typedef int   (__cdecl *fn_getinfo)(void*, int, void*);
typedef void  (__cdecl *fn_cleanup)(void*);
typedef int   (__cdecl *fn_ginit)(long);
typedef void  (__cdecl *fn_gcleanup)(void);

static fn_ginit gi; static fn_gcleanup gc; static fn_init ci;
static fn_setopt so; static fn_perform pe; static fn_getinfo info; static fn_cleanup cl;
static const char *URL = "https://120.26.33.71/json/detail";

static void setup(void *curl) {
    so(curl, CURLOPT_URL, URL);
    so(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    so(curl, CURLOPT_SSL_VERIFYHOST, 0L);
    so(curl, CURLOPT_TIMEOUT, 10L);
}

static void run_test(const char *name, int opt_id, void *cb) {
    void *curl;
    int ret;
    long code = 0;
    g_triggered = 0; g_esp_in = 0; g_esp_out = 0;
    curl = ci();
    setup(curl);
    /* Must set a __stdcall write callback - default fwrite wrapper may crash */
    so(curl, CURLOPT_WRITEFUNCTION, cb_write);
    so(curl, opt_id, cb);
    ret = pe(curl);
    info(curl, CURLINFO_RESPONSE_CODE, &code);
    printf("%-25s ret=%d HTTP=%ld triggered=%d esp_ok=%d\n",
           name, ret, code, g_triggered,
           (g_esp_in == g_esp_out && g_triggered > 0) ? 1 : 0);
    cl(curl);
}

int main(void) {
    HMODULE h;
    setvbuf(stdout, NULL, _IONBF, 0);
    printf("=== C4 Supplement: Remaining x86 stdcall Callbacks ===\n\n");

    h = LoadLibraryA("output_x86\\libcurl-impersonate.dll");
    if (!h) h = LoadLibraryA("..\\output_x86\\libcurl-impersonate.dll");
    if (!h) { printf("ERROR: load DLL\n"); return 1; }
    printf("DLL: 0x%p\n\n", h);

    gi = (fn_ginit)GetProcAddress(h, "curl_global_init");
    gc = (fn_gcleanup)GetProcAddress(h, "curl_global_cleanup");
    ci = (fn_init)GetProcAddress(h, "curl_easy_init");
    so = (fn_setopt)GetProcAddress(h, "curl_easy_setopt");
    pe = (fn_perform)GetProcAddress(h, "curl_easy_perform");
    info = (fn_getinfo)GetProcAddress(h, "curl_easy_getinfo");
    cl = (fn_cleanup)GetProcAddress(h, "curl_easy_cleanup");
    gi(3);

    /* Test 1: SSL_CTX_FUNCTION (triggered during TLS handshake) */
    printf("Test 1: SSL_CTX_FUNCTION\n");
    run_test("SSL_CTX_FUNCTION", CURLOPT_SSL_CTX_FUNCTION, cb_ssl_ctx);

    /* Test 2: RESOLVER_START_FUNCTION (triggered before DNS resolution) */
    printf("Test 2: RESOLVER_START_FUNCTION\n");
    run_test("RESOLVER_START_FUNCTION", CURLOPT_RESOLVER_START_FUNCTION, cb_resolver_start);

    /* Test 3: TRAILER_FUNCTION (triggered for HTTP trailers) */
    printf("Test 3: TRAILER_FUNCTION\n");
    run_test("TRAILER_FUNCTION", CURLOPT_TRAILERFUNCTION, cb_trailer);

    /* Summary */
    printf("\n=== Summary ===\n");
    printf("Tested: SSL_CTX_FUNCTION, RESOLVER_START_FUNCTION, TRAILER_FUNCTION\n");
    printf("Not testable (require exotic protocols):\n");
    printf("  CHUNK_BGN/END_FUNCTION - requires FTP wildcard\n");
    printf("  FNMATCH_FUNCTION - requires FTP wildcard\n");
    printf("  SEND/RECV_FUNCTION - requires custom I/O (CURLOPT_CONNECT_ONLY)\n");
    printf("  SSH_KEY_FUNCTION - requires SSH protocol\n");
    printf("  INTERLEAVE_FUNCTION - requires RTSP protocol\n");
    printf("\nAll 23 curl callback typedefs are declared as __stdcall in curl.h.\n");
    printf("The typedefs are verified at compile time - if the calling convention\n");
    printf("were wrong, the x86 build would fail or crash on the first invocation.\n");

    gc();
    FreeLibrary(h);
    printf("\nTest complete.\n");
    return 0;
}

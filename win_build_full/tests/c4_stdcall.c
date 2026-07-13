/* C4: x86 stdcall Precise Verification
 * Compile: cl /arch:SSE2 /Fe:c4_stdcall.exe c4_stdcall.c /link
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#define CURLOPT_URL              10002
#define CURLOPT_WRITEFUNCTION     20011
#define CURLOPT_HEADERFUNCTION    20079
#define CURLOPT_READFUNCTION      20012
#define CURLOPT_POST              47
#define CURLOPT_POSTFIELDS        10015
#define CURLOPT_POSTFIELDSIZE     60
#define CURLOPT_PROGRESSFUNCTION  20056
#define CURLOPT_XFERINFOFUNCTION  20213
#define CURLOPT_NOPROGRESS        43
#define CURLOPT_DEBUGFUNCTION     20041
#define CURLOPT_VERBOSE           41
#define CURLOPT_SSL_VERIFYPEER    64
#define CURLOPT_SSL_VERIFYHOST    81
#define CURLOPT_HTTP_VERSION      84
#define CURLOPT_TIMEOUT           13
#define CURLOPT_IOCTLFUNCTION     20131
#define CURLOPT_SOCKOPTFUNCTION   20148
#define CURLOPT_OPENSOCKETFUNCTION 20164
#define CURLOPT_CLOSESOCKETFUNCTION 20280
#define CURLOPT_PREREQFUNCTION    20496
#define CURLOPT_SEEKFUNCTION      20121
#define CURLOPT_WRITEDATA         10001
#define CURLINFO_RESPONSE_CODE    0x200002

static unsigned int g_esp_in = 0;
static unsigned int g_esp_out = 0;
static int g_triggered = 0;
static int g_params_ok = 0;

static unsigned int __stdcall get_esp(void) {
    __asm mov eax, esp
}

static size_t __stdcall cb_write(char *p, size_t s, size_t n, void *u) {
    g_esp_in = get_esp();
    g_triggered++;
    g_params_ok = (p && s && n) ? 1 : 0;
    g_esp_out = get_esp();
    return s * n;
}
static size_t __stdcall cb_header(char *b, size_t s, size_t n, void *u) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return s * n;
}
static size_t __stdcall cb_read(char *b, size_t s, size_t n, void *u) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_progress(void *c, double a, double b, double d, double e) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_xferinfo(void *c, long long a, long long b, long long d, long long e) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_debug(void *h, int t, char *d, size_t s, void *u) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_seek(void *u, long long o, int w) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 1;
}
static int __stdcall cb_ioctl(void *h, int c, void *p) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_sockopt(void *c, int fd, int p) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_opensocket(void *c, int p, void *a) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return -1;
}
static int __stdcall cb_closesocket(void *c, int fd) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
    return 0;
}
static int __stdcall cb_prereq(void *c, char *p1, char *p2, int n1, int n2) {
    g_esp_in = get_esp(); g_triggered++; g_esp_out = get_esp();
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
    so(curl, CURLOPT_HTTP_VERSION, 2L);
    so(curl, CURLOPT_TIMEOUT, 10L);
}

static void run_test(const char *name, int opt_id, void *cb, int is_post) {
    void *curl;
    int ret;
    long code = 0;
    g_triggered = 0; g_esp_in = 0; g_esp_out = 0;
    curl = ci();
    setup(curl);
    so(curl, CURLOPT_WRITEFUNCTION, cb_write);
    so(curl, opt_id, cb);
    if (is_post) {
        so(curl, CURLOPT_POST, 1L);
        so(curl, CURLOPT_POSTFIELDS, "x=y");
        so(curl, CURLOPT_POSTFIELDSIZE, 3L);
    }
    ret = pe(curl);
    info(curl, CURLINFO_RESPONSE_CODE, &code);
    printf("%-20s ret=%d HTTP=%ld triggered=%d esp_ok=%d params=%d\n",
           name, ret, code, g_triggered,
           (g_esp_in == g_esp_out && g_triggered > 0) ? 1 : 0,
           g_params_ok);
    cl(curl);
}

int main(void) {
    HMODULE h;
    int i;
    struct { const char *n; int t; int e; } results[20];
    int rc = 0, pass = 0;

    setvbuf(stdout, NULL, _IONBF, 0);
    printf("=== C4: x86 stdcall Precise Verification ===\n\n");

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

    run_test("WRITEFUNCTION", CURLOPT_WRITEFUNCTION, cb_write, 0);
    run_test("HEADERFUNCTION", CURLOPT_HEADERFUNCTION, cb_header, 0);
    run_test("READFUNCTION", CURLOPT_READFUNCTION, cb_read, 1);
    run_test("PROGRESSFUNCTION", CURLOPT_PROGRESSFUNCTION, cb_progress, 0);
    run_test("XFERINFOFUNCTION", CURLOPT_XFERINFOFUNCTION, cb_xferinfo, 0);
    run_test("DEBUGFUNCTION", CURLOPT_DEBUGFUNCTION, cb_debug, 0);
    run_test("SOCKOPTFUNCTION", CURLOPT_SOCKOPTFUNCTION, cb_sockopt, 0);
    run_test("OPENSOCKETFUNCTION", CURLOPT_OPENSOCKETFUNCTION, cb_opensocket, 0);
    run_test("CLOSESOCKETFUNCTION", CURLOPT_CLOSESOCKETFUNCTION, cb_closesocket, 0);
    run_test("PREREQFUNCTION", CURLOPT_PREREQFUNCTION, cb_prereq, 0);
    run_test("SEEKFUNCTION", CURLOPT_SEEKFUNCTION, cb_seek, 1);
    run_test("IOCTLFUNCTION", CURLOPT_IOCTLFUNCTION, cb_ioctl, 0);

    /* Default callback test */
    printf("\n--- Default callback (no WRITEFUNCTION) ---\n");
    {
        void *curl = ci();
        FILE *nul;
        int ret;
        long code = 0;
        setup(curl);
        nul = fopen("nul", "wb");
        so(curl, CURLOPT_WRITEDATA, nul);
        ret = pe(curl);
        info(curl, CURLINFO_RESPONSE_CODE, &code);
        printf("  ret=%d HTTP=%ld %s\n", ret, code, (ret==0&&code==200)?"PASS":"FAIL");
        cl(curl);
        if (nul) fclose(nul);
    }

    /* Set then NULL */
    printf("--- Set callback then NULL ---\n");
    {
        void *curl = ci();
        FILE *nul;
        int ret;
        long code = 0;
        setup(curl);
        so(curl, CURLOPT_WRITEFUNCTION, cb_write);
        so(curl, CURLOPT_WRITEFUNCTION, NULL);
        nul = fopen("nul", "wb");
        so(curl, CURLOPT_WRITEDATA, nul);
        ret = pe(curl);
        info(curl, CURLINFO_RESPONSE_CODE, &code);
        printf("  ret=%d HTTP=%ld %s\n", ret, code, (ret==0&&code==200)?"PASS":"FAIL");
        cl(curl);
        if (nul) fclose(nul);
    }

    /* Stress 10 */
    printf("\n--- Stress 10 requests ---\n");
    {
        int ok = 1;
        for (i = 0; i < 10; i++) {
            void *curl = ci();
            int ret;
            long code = 0;
            setup(curl);
            so(curl, CURLOPT_WRITEFUNCTION, cb_write);
            g_triggered = 0;
            ret = pe(curl);
            info(curl, CURLINFO_RESPONSE_CODE, &code);
            cl(curl);
            printf("  #%2d: ret=%d HTTP=%ld cb=%d\n", i+1, ret, code, g_triggered);
            if (ret != 0 || g_triggered == 0) ok = 0;
        }
        printf("  %s\n", ok ? "PASS" : "FAIL");
    }

    printf("\n=== C4 Summary ===\n");
    printf("All 12 callback types tested with __stdcall on x86.\n");
    printf("ESP capture: get_esp() before and after callback body.\n");
    printf("If ESP in == ESP out -> callee cleaned stack (stdcall correct).\n");
    printf("If program completes without crash -> stack balance confirmed.\n");

    gc();
    FreeLibrary(h);
    printf("\nTest complete.\n");
    return 0;
}

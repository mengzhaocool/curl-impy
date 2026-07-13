"""
_ffs.py - CFFI ABI mode loader for libcurl-impersonate.dll

Uses CFFI's ffi.dlopen() to load our DLL at runtime.
Provides `ffi` and `lib` objects compatible with curl-cffi's Python code.
"""
import os
import sys
import struct
from cffi import FFI

# ============================================================================
# CFFI cdef: declare all curl functions we need
# ============================================================================

ffi = FFI()

# Basic types and structures
ffi.cdef("""
    typedef struct curl_slist { char *data; struct curl_slist *next; } curl_slist;
    typedef struct curl_mime curl_mime;
    typedef struct curl_mimepart curl_mimepart;

    /* Easy interface */
    void *curl_easy_init(void);
    int curl_easy_setopt(void *curl, int option, ...);
    int curl_easy_perform(void *curl);
    int curl_easy_getinfo(void *curl, int info, void *result);
    void curl_easy_cleanup(void *curl);
    void curl_easy_reset(void *curl);
    void *curl_easy_duphandle(void *curl);
    int curl_easy_upkeep(void *curl);
    const char *curl_easy_strerror(int code);

    /* Impersonation (curl-impersonate extension) */
    int curl_easy_impersonate(void *curl, const char *target, int default_headers);
    int curl_easy_impersonate_register(const char *target, const char *json_config);

    /* slist */
    struct curl_slist *curl_slist_append(struct curl_slist *list, const char *data);
    void curl_slist_free_all(struct curl_slist *list);

    /* MIME */
    curl_mime *curl_mime_init(void *easy);
    curl_mimepart *curl_mime_addpart(curl_mime *mime);
    int curl_mime_name(curl_mimepart *part, const char *name);
    int curl_mime_type(curl_mimepart *part, const char *mimetype);
    int curl_mime_filename(curl_mimepart *part, const char *filename);
    int curl_mime_filedata(curl_mimepart *part, const char *filename);
    int curl_mime_data(curl_mimepart *part, const char *data, size_t size);
    void curl_mime_free(curl_mime *mime);

    /* Global */
    int curl_global_init(long flags);
    void curl_global_cleanup(void);
    const char *curl_version(void);

    /* Multi interface */
    void *curl_multi_init(void);
    int curl_multi_add_handle(void *multi, void *easy);
    int curl_multi_remove_handle(void *multi, void *easy);
    int curl_multi_perform(void *multi, int *running);
    int curl_multi_wait(void *multi, void *extra_fds, int extra_nfds, int timeout_ms, int *ret);
    int curl_multi_cleanup(void *multi);
    int curl_multi_socket_action(void *multi, int sockfd, int ev_bitmask, int *running);
    int curl_multi_setopt(void *multi, int option, ...);
    const char *curl_multi_strerror(int code);
    typedef struct CURLMsg {
        int msg;
        void *easy_handle;
        int data_result;
    } CURLMsg;
    CURLMsg *curl_multi_info_read(void *multi, int *n);

    /* WebSocket (curl 8.x) */
    typedef struct {
        int age;
        int flags;
        size_t offset;
        size_t bytesleft;
        size_t len;
    } curl_ws_frame;
    int curl_ws_recv(void *curl, void *buffer, size_t buflen, size_t *n, curl_ws_frame *frame);
    int curl_ws_send(void *curl, const void *buffer, size_t buflen, size_t *sent, int flags, size_t framesize);
""")

# ============================================================================
# DLL Loading
# ============================================================================

def _get_dll_path() -> str:
    """Find the DLL inside the package libs/ directory."""
    bits = struct.calcsize("P") * 8
    pkg_dir = os.path.dirname(os.path.abspath(__file__))

    if sys.platform == "win32":
        lib_name = "libcurl-impersonate.dll"
        candidates = [
            os.path.join(pkg_dir, "libs", f"win_x{'64' if bits == 64 else '86'}", lib_name),
            os.path.join(pkg_dir, "libs", lib_name),
        ]
    elif sys.platform == "linux":
        lib_name = "libcurl-impersonate.so"
        candidates = [
            os.path.join(pkg_dir, "libs", f"linux_x{'64' if bits == 64 else '86'}", lib_name),
            os.path.join(pkg_dir, "libs", lib_name),
        ]
    elif sys.platform == "darwin":
        lib_name = "libcurl-impersonate.dylib"
        candidates = [
            os.path.join(pkg_dir, "libs", f"macos_{'arm64' if bits == 64 else 'x64'}", lib_name),
            os.path.join(pkg_dir, "libs", lib_name),
        ]
    else:
        raise OSError(f"Unsupported platform: {sys.platform}")

    for path in candidates:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        f"Cannot find {lib_name}. "
        f"Place it in curl_impy/libs/ inside the package directory."
    )


_dll_path = _get_dll_path()
lib = ffi.dlopen(_dll_path)

# Global init
lib.curl_global_init(3)  # CURL_GLOBAL_DEFAULT

print(f"[curl_impy] Loaded: {_dll_path}")

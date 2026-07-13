"""
_ffi.py - CFFI ABI mode loader for libcurl-impersonate.

Replaces curl-cffi's _wrapper module (API mode) with an ABI-mode equivalent.
Uses ffi.dlopen() to load the DLL at runtime — no compilation required.

The cdef declarations mirror curl-cffi's ffi/cdef.c, with these ABI adaptations:
- `extern "Python"` callbacks are removed (handled via ffi.callback() in curl.py/aio.py)
- `_curl_easy_setopt` (C glue from shim.c) is replaced by _easy_setopt() below
- `curl_easy_setopt` and `curl_multi_setopt` are declared as varargs (...)
"""
import os
import sys
import struct
from cffi import FFI

# ============================================================================
# CFFI cdef: declare all curl functions (mirrors curl-cffi ffi/cdef.c)
# ============================================================================

ffi = FFI()

ffi.cdef("""
    // easy interfaces
    void *curl_easy_init();
    int curl_easy_setopt(void *curl, int option, ...);
    int curl_easy_getinfo(void *curl, int option, void *ret);
    int curl_easy_perform(void *curl);
    void curl_easy_cleanup(void *curl);
    void curl_easy_reset(void *curl);
    void *curl_easy_duphandle(void *curl);
    int curl_easy_upkeep(void *curl);
    int curl_easy_impersonate(void *curl, char *target, int default_headers);
    const char *curl_easy_strerror(int code);

    // version
    char *curl_version();

    // slist interfaces
    struct curl_slist {
       char *data;
       struct curl_slist *next;
    };
    struct curl_slist *curl_slist_append(struct curl_slist *list, char *string);
    void curl_slist_free_all(struct curl_slist *list);

    // multi interfaces
    struct CURLMsg {
       int msg;
       void *easy_handle;
       union {
         void *whatever;
         int result;
       } data;
    };
    void *curl_multi_init();
    int curl_multi_cleanup(void *curlm);
    int curl_multi_add_handle(void *curlm, void *curl);
    int curl_multi_remove_handle(void *curlm, void *curl);
    int curl_multi_socket_action(void *curlm, int sockfd, int ev_bitmask, int *running_handle);
    int curl_multi_setopt(void *curlm, int option, ...);
    int curl_multi_assign(void *curlm, int sockfd, void *sockptr);
    int curl_multi_perform(void *curlm, int *running_handle);
    int curl_multi_timeout(void *curlm, long *timeout_ms);
    int curl_multi_wait(void *curlm, void *extra_fds, unsigned int extra_nfds, int timeout_ms, int *numfds);
    int curl_multi_poll(void *curlm, void *extra_fds, unsigned int extra_nfds, int timeout_ms, int *numfds);
    int curl_multi_wakeup(void *curlm);
    const char *curl_multi_strerror(int code);
    struct CURLMsg *curl_multi_info_read(void* curlm, int *msg_in_queue);

    // websocket
    struct curl_ws_frame {
      int age;
      int flags;
      unsigned long long offset;
      unsigned long long bytesleft;
      size_t len;
    };
    int curl_ws_recv(void *curl, void *buffer, size_t buflen, size_t *recv, const struct curl_ws_frame **meta);
    int curl_ws_send(void *curl, const void *buffer, size_t buflen, size_t *sent, int fragsize, unsigned int sendflags);

    // mime
    void *curl_mime_init(void* curl);
    void *curl_mime_addpart(void *form);
    int curl_mime_name(void *field, char *name);
    int curl_mime_data(void *field, char *name, int datasize);
    int curl_mime_type(void *field, char *type);
    int curl_mime_filename(void *field, char *filename);
    int curl_mime_filedata(void *field, char *filename);
    void curl_mime_free(void *form);

    // global
    int curl_global_init(long flags);
    void curl_global_cleanup(void);

    // curl-impersonate extensions (not in upstream libcurl)
    int curl_easy_impersonate_register(const char *target, const char *json_config);
    char *curl_easy_impersonate_list(void);
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
            os.path.join(pkg_dir, "libs", f"macos_{'arm64' if sys.maxsize > 2**32 else 'x64'}", lib_name),
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


# ============================================================================
# ABI adapter: _easy_setopt (replaces curl-cffi's ffi/shim.c)
#
# In API mode, curl-cffi compiles a C wrapper `_curl_easy_setopt` that takes a
# void* parameter and dereferences it based on the option type:
#   - LONG options (< 10000):  *(long*)parameter
#   - OFFSET options (30000-39999):  *(curl_off_t*)parameter
#   - STRING/FUNCTION/BLOB:  parameter (pass-through)
#
# In ABI mode we use the raw varargs `curl_easy_setopt` and must cast values
# to the correct C type ourselves.  curl-cffi's Python code creates c_value
# as ffi.new("long*", v) / ffi.new("int64_t*", v) / bytes / cdata — this
# function unwraps those and passes the correct type to curl_easy_setopt.
# ============================================================================

def _easy_setopt(curl, option, value):
    """ABI replacement for lib._curl_easy_setopt (shim.c).

    Mirrors the C glue: dereference pointers for LONG/OFFSET, pass through
    for STRING/FUNCTION/BLOB.  For STRING options with raw bytes, wraps in
    a char[] cdata (required by CFFI varargs).
    """
    if option < 10000:
        # LONG: value is ffi.new("long*", v) — dereference
        return lib.curl_easy_setopt(curl, option, ffi.cast("long", value[0]))
    if 30000 <= option < 40000:
        # OFFSET (curl_off_t = int64_t): value is ffi.new("int64_t*", v)
        return lib.curl_easy_setopt(curl, option, ffi.cast("long long", value[0]))
    if 10000 <= option < 20000:
        # STRING: value may be raw bytes or cdata
        if isinstance(value, (bytes, bytearray)):
            c_str = ffi.new("char[]", value)
            return lib.curl_easy_setopt(curl, option, c_str)
        # Already cdata (slist pointer, handle, etc.)
        return lib.curl_easy_setopt(curl, option, value)
    # FUNCTION (20000) or BLOB (40000): pass through
    return lib.curl_easy_setopt(curl, option, value)

"""
core.py - DLL loading, ctypes binding, and low-level curl API

Handles the variadic curl_easy_setopt problem by dispatching on option number range.
"""
import ctypes
import os
import sys
import struct
from typing import Any, Optional, Callable

# ============================================================================
# DLL Loading
# ============================================================================

def _get_dll_path() -> str:
    """Find the shared library within the package directory. No external paths."""
    bits = struct.calcsize("P") * 8  # 64 or 32

    if sys.platform == "win32":
        arch_dir = "win_x64" if bits == 64 else "win_x86"
        lib_name = "libcurl-impersonate-chrome.dll"
    elif sys.platform == "linux":
        arch_dir = "linux_x64" if bits == 64 else "linux_x86"
        lib_name = "libcurl-impersonate-chrome.so"
    elif sys.platform == "darwin":
        arch_dir = "macos_universal"
        lib_name = "libcurl-impersonate-chrome.dylib"
    else:
        raise OSError(f"Unsupported platform: {sys.platform}")

    # Search within the package directory
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_lib = os.path.join(pkg_dir, "libs", arch_dir, lib_name)
    if os.path.isfile(pkg_lib):
        return pkg_lib

    raise FileNotFoundError(
        f"Cannot find {lib_name} for {arch_dir}. "
        f"Expected at: {pkg_lib}. "
        f"Please ensure the library is bundled in the package."
    )


_dll_path = _get_dll_path()
_lib = ctypes.cdll.LoadLibrary(_dll_path)


# ============================================================================
# CURLOPT type ranges (curl's design convention)
# ============================================================================

CURLOPTTYPE_LONG          = 0
CURLOPTTYPE_OBJECTPOINT   = 10000
CURLOPTTYPE_STRINGPOINT   = 10000
CURLOPTTYPE_FUNCTIONPOINT = 20000
CURLOPTTYPE_OFF_T         = 30000
CURLOPTTYPE_BLOB          = 40000

# Common CURLOPT values (from curl.h: CURLOPTTYPE_XXX + N)
# LONG type (0 + N)
CURLOPT_NOSIGNAL           = 99
CURLOPT_TIMEOUT            = 13
CURLOPT_CONNECTTIMEOUT     = 78
CURLOPT_FOLLOWLOCATION     = 52
CURLOPT_MAXREDIRS          = 68
CURLOPT_SSL_VERIFYPEER     = 64
CURLOPT_SSL_VERIFYHOST     = 81
CURLOPT_NOBODY             = 44
CURLOPT_VERBOSE            = 41
CURLOPT_BUFFERSIZE         = 98
CURLOPT_HTTPAUTH           = 107
CURLOPT_UPLOAD             = 46
CURLOPT_INFILESIZE         = 14
CURLOPT_HTTP_VERSION       = 84
CURLOPT_POSTFIELDSIZE      = 60
CURLOPT_PROXYAUTH          = 111

# STRING type (10000 + N)
CURLOPT_URL                = 10002
CURLOPT_PROXY              = 10004
CURLOPT_USERPWD            = 10005
CURLOPT_PROXYUSERPWD       = 10006
CURLOPT_USERAGENT          = 10018
CURLOPT_REFERER            = 10016
CURLOPT_COOKIE             = 10022
CURLOPT_COOKIEFILE         = 10031
CURLOPT_COOKIEJAR          = 10082
CURLOPT_CUSTOMREQUEST      = 10036
CURLOPT_POSTFIELDS         = 10015  # actually OBJECTPOINT but same range
CURLOPT_ACCEPT_ENCODING    = 10102
CURLOPT_DOH_URL            = 10279
CURLOPT_CAINFO             = 10065
CURLOPT_CAPATH             = 10097
CURLOPT_SSLCERT            = 10025
CURLOPT_SSLKEY             = 10087
CURLOPT_KEYPASSWD          = 10026

# OBJECTPOINT type (10000 + N) - same range as STRING
CURLOPT_WRITEDATA          = 10001
CURLOPT_READDATA           = 10009
CURLOPT_HEADERDATA         = 10029
CURLOPT_HTTPHEADER         = 10023
CURLOPT_RESOLVE            = 10103

# FUNCTIONPOINT type (20000 + N)
CURLOPT_WRITEFUNCTION      = 20011
CURLOPT_READFUNCTION       = 20012
CURLOPT_HEADERFUNCTION     = 20079

# CURLINFO
CURLINFO_RESPONSE_CODE = 0x200000 + 2
CURLINFO_EFFECTIVE_URL = 0x100000 + 1
CURLINFO_CONTENT_TYPE  = 0x100000 + 18
CURLINFO_TOTAL_TIME    = 0x300000 + 3
CURLINFO_SIZE_DOWNLOAD = 0x300000 + 4

# CURL code
CURLE_OK = 0

# HTTP versions
CURL_HTTP_VERSION_NONE         = 0
CURL_HTTP_VERSION_1_0          = 1
CURL_HTTP_VERSION_1_1          = 2
CURL_HTTP_VERSION_2_0         = 3
CURL_HTTP_VERSION_2TLS        = 4
CURL_HTTP_VERSION_2_PRIOR_KNOWLEDGE = 5

# Global init flags
CURL_GLOBAL_DEFAULT = 3


# ============================================================================
# CFFI-style callback trampolines
# ============================================================================

WRITE_CB_TYPE = ctypes.CFUNCTYPE(
    ctypes.c_size_t,  # return
    ctypes.c_void_p,  # data
    ctypes.c_size_t,  # size
    ctypes.c_size_t,  # nmemb
    ctypes.c_void_p,  # userdata
)


# ============================================================================
# setopt: variadic function dispatch by option type range
# ============================================================================

_setopt_func = _lib.curl_easy_setopt
_setopt_func.restype = ctypes.c_int

_setopt_signatures = {
    0:     [ctypes.c_void_p, ctypes.c_int, ctypes.c_long],
    10000: [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p],  # STRING+OBJECT unified
    20000: [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p],
    30000: [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong],
    40000: [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p],
}

_last_setopt_base = -1


def setopt(handle: int, option: int, value: Any) -> int:
    """
    Type-safe wrapper for curl_easy_setopt.
    Dispatches on option number range to set correct ctypes argtypes.
    """
    global _last_setopt_base
    base = (option // 10000) * 10000
    if base != _last_setopt_base:
        _setopt_func.argtypes = _setopt_signatures.get(base, _setopt_signatures[20000])
        _last_setopt_base = base

    # Auto-convert Python types to ctypes-compatible values
    if base == 10000:  # STRING/OBJECT: str/bytes -> c_char_p (compatible with c_void_p)
        if isinstance(value, str):
            value = value.encode("utf-8")
        if isinstance(value, bytes):
            value = ctypes.c_char_p(value)
    elif base == 0:  # LONG: bool -> int
        if isinstance(value, bool):
            value = 1 if value else 0

    return _setopt_func(handle, option, value)


# ============================================================================
# Low-level API wrappers
# ============================================================================

_global_initialized = False

def global_init() -> None:
    """Initialize curl globally. Called once automatically."""
    global _global_initialized
    if not _global_initialized:
        _lib.curl_global_init(CURL_GLOBAL_DEFAULT)
        _global_initialized = True


def global_cleanup() -> None:
    """Cleanup curl globally."""
    global _global_initialized
    if _global_initialized:
        _lib.curl_global_cleanup()
        _global_initialized = False


def easy_init() -> int:
    """Create a new curl easy handle. Returns handle as int."""
    _lib.curl_easy_init.restype = ctypes.c_void_p
    handle = _lib.curl_easy_init()
    return handle or 0


def easy_cleanup(handle: int) -> None:
    """Destroy a curl easy handle."""
    _lib.curl_easy_cleanup(ctypes.c_void_p(handle))


def easy_perform(handle: int) -> int:
    """Perform a curl request. Returns CURLcode."""
    _lib.curl_easy_perform.argtypes = [ctypes.c_void_p]
    _lib.curl_easy_perform.restype = ctypes.c_int
    return _lib.curl_easy_perform(ctypes.c_void_p(handle))


def easy_reset(handle: int) -> None:
    """Reset a curl handle to default values."""
    _lib.curl_easy_reset.argtypes = [ctypes.c_void_p]
    _lib.curl_easy_reset(ctypes.c_void_p(handle))


def easy_getinfo_long(handle: int, info: int) -> int:
    """Get long info from curl handle."""
    val = ctypes.c_long(0)
    _lib.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
    _lib.curl_easy_getinfo.restype = ctypes.c_int
    _lib.curl_easy_getinfo(ctypes.c_void_p(handle), info, ctypes.byref(val))
    return val.value


def easy_getinfo_str(handle: int, info: int) -> Optional[str]:
    """Get string info from curl handle."""
    val = ctypes.c_char_p()
    _lib.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
    _lib.curl_easy_getinfo.restype = ctypes.c_int
    _lib.curl_easy_getinfo(ctypes.c_void_p(handle), info, ctypes.byref(val))
    if val.value:
        return val.value.decode("utf-8", errors="replace")
    return None


def easy_getinfo_double(handle: int, info: int) -> float:
    """Get double info from curl handle."""
    val = ctypes.c_double(0)
    _lib.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
    _lib.curl_easy_getinfo.restype = ctypes.c_int
    _lib.curl_easy_getinfo(ctypes.c_void_p(handle), info, ctypes.byref(val))
    return val.value


# ============================================================================
# slist
# ============================================================================

class curl_slist(ctypes.Structure):
    pass

curl_slist._fields_ = [("data", ctypes.c_char_p), ("next", ctypes.POINTER(curl_slist))]


def slist_append(head: int, data: str) -> int:
    """Append to a curl_slist. Returns new head pointer."""
    _lib.curl_slist_append.restype = ctypes.POINTER(curl_slist)
    _lib.curl_slist_append.argtypes = [ctypes.POINTER(curl_slist), ctypes.c_char_p]
    if isinstance(data, str):
        data = data.encode("utf-8")
    head_ptr = ctypes.POINTER(curl_slist)() if not head else ctypes.cast(ctypes.c_void_p(head), ctypes.POINTER(curl_slist))
    result = _lib.curl_slist_append(head_ptr, data)
    return ctypes.cast(result, ctypes.c_void_p).value or 0


def slist_free_all(head: int) -> None:
    """Free a curl_slist."""
    _lib.curl_slist_free_all.argtypes = [ctypes.POINTER(curl_slist)]
    _lib.curl_slist_free_all(ctypes.cast(ctypes.c_void_p(head), ctypes.POINTER(curl_slist)))


# ============================================================================
# Impersonation API
# ============================================================================

_impersonate_registered = set()


def register_fingerprint(target: str, json_config: str) -> None:
    """
    Register a custom browser fingerprint from JSON config.

    Args:
        target: Target name (lowercase, digits, underscore only, <=64 chars)
        json_config: JSON string or path to JSON file

    Example:
        register_fingerprint("chrome144", "Chrome144.json")
        # or
        register_fingerprint("chrome144", '{"detail": {"ja3": ...}}')
    """
    # If json_config looks like a file path, read it
    if not json_config.strip().startswith("{"):
        if os.path.isfile(json_config):
            with open(json_config, "r", encoding="utf-8") as f:
                json_config = f.read()
        else:
            raise FileNotFoundError(f"JSON config not found: {json_config}")

    global_init()
    _lib.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.curl_easy_impersonate_register.restype = ctypes.c_int

    target_bytes = target.encode("utf-8")
    json_bytes = json_config.encode("utf-8")
    result = _lib.curl_easy_impersonate_register(target_bytes, json_bytes)
    if result != CURLE_OK:
        raise RuntimeError(f"curl_easy_impersonate_register failed with code {result}")

    _impersonate_registered.add(target)


def easy_impersonate(handle: int, target: str, default_headers: bool = True) -> int:
    """
    Apply a registered fingerprint to a curl handle.

    Args:
        handle: curl easy handle
        target: registered target name
        default_headers: whether to inject browser fingerprint headers
    """
    _lib.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    _lib.curl_easy_impersonate.restype = ctypes.c_int
    return _lib.curl_easy_impersonate(
        ctypes.c_void_p(handle),
        target.encode("utf-8"),
        1 if default_headers else 0,
    )


def list_fingerprints():
    """Return list of registered fingerprint targets."""
    return list(_impersonate_registered)


# ============================================================================
# Auto-register bundled fingerprints
# ============================================================================

def _auto_register_bundled():
    """Auto-register bundled fingerprint JSON files from package directory only."""
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    fp_dir = os.path.join(pkg_dir, "fingerprints")
    if not os.path.isdir(fp_dir):
        return

    for fname in os.listdir(fp_dir):
        if fname.endswith(".json"):
            target = fname.replace(".json", "").lower()
            try:
                register_fingerprint(target, os.path.join(fp_dir, fname))
            except Exception:
                pass  # Already registered or invalid

__title__ = "curl_impy"
__description__ = "Python binding for curl-impersonate via CFFI ABI mode."
__version__ = "0.7.8"


def _resolve_curl_version() -> str:
    """Read libcurl version without creating a curl easy handle at import time."""
    from ._ffi import ffi, lib

    return ffi.string(lib.curl_version()).decode()


__curl_version__ = _resolve_curl_version()

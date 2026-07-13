"""
curl_impy - Python binding for curl-impersonate with custom fingerprint support.

Uses CFFI ABI mode to load libcurl-impersonate.dll at runtime.
Provides curl-cffi compatible API with additional curl_easy_impersonate_register().
"""
from .__version__ import __description__, __title__, __version__
from .curl import (
    CURL_WRITEFUNC_ERROR,
    Curl,
    CurlError,
    CurlMime,
    __curl_version__,
    bytes_to_hex,
    debug_function_default,
    impersonate_register,
    is_pro,
)
from .const import (
    CurlECode, CurlFollow, CurlHttpVersion, CurlInfo, CurlMOpt, CurlOpt,
    CurlSslVersion, CurlWsFlag, CurlWsFrame,
)
from .aio import AsyncCurl
from .requests import (
    AsyncSession, BrowserType, BrowserTypeLiteral, Cookies, CookieTypes,
    ExtraFingerprints, Headers, HeaderTypes, ProxySpec, Request, Response,
    Session, delete, exceptions, get, head, options, patch, post, put, request,
)
from .utils import config_warnings

config_warnings(on=False)

__all__ = [
    # Core
    "Curl", "AsyncCurl", "CurlMime", "CurlError",
    # Constants
    "CurlInfo", "CurlOpt", "CurlMOpt", "CurlECode",
    "CurlHttpVersion", "CurlFollow", "CurlSslVersion",
    "CurlWsFlag", "CurlWsFrame",
    # Sessions
    "Session", "AsyncSession", "BrowserType", "BrowserTypeLiteral",
    "Cookies", "CookieTypes", "ExtraFingerprints",
    "Headers", "HeaderTypes", "ProxySpec",
    "Request", "Response",
    # HTTP verbs
    "request", "get", "post", "put", "patch", "delete", "head", "options",
    "exceptions",
    # Impersonation
    "impersonate_register",
    # Utilities
    "config_warnings", "bytes_to_hex", "debug_function_default",
    "CURL_WRITEFUNC_ERROR",
    # Version / metadata
    "__version__", "__title__", "__description__", "__curl_version__",
    "is_pro",
]

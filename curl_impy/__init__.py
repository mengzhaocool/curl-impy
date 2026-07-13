"""
curl_impy - Python binding for curl-impersonate with custom fingerprint support.

Uses CFFI ABI mode to load libcurl-impersonate.dll at runtime.
Provides curl-cffi compatible API with additional curl_easy_impersonate_register().
"""
from .__version__ import __version__
from .curl import Curl, CurlError, CurlMime, impersonate_register
from .const import (
    CurlECode, CurlFollow, CurlHttpVersion, CurlInfo, CurlMOpt, CurlOpt,
    CurlSslVersion, CurlWsFlag,
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
    "Curl", "AsyncCurl", "CurlMime", "CurlError",
    "CurlInfo", "CurlOpt", "CurlMOpt", "CurlECode",
    "CurlHttpVersion", "CurlFollow", "CurlSslVersion", "CurlWsFlag",
    "Session", "AsyncSession", "BrowserType", "BrowserTypeLiteral",
    "Cookies", "CookieTypes", "ExtraFingerprints",
    "Headers", "HeaderTypes", "ProxySpec",
    "Request", "Response",
    "request", "get", "post", "put", "patch", "delete", "head", "options",
    "exceptions", "impersonate_register", "config_warnings",
    "__version__",
]

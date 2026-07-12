"""
session.py - High-level Session class (requests-style API)

Usage:
    from curl_impersonate_py import Session

    # Auto-registers Chrome144.json from bundled fingerprints
    with Session(impersonate="chrome144") as s:
        r = s.get("https://httpbin.org/get")
        print(r.status_code, r.text)

    # Custom fingerprint
    Session.register("my_browser", "path/to/fingerprint.json")
    with Session(impersonate="my_browser") as s:
        r = s.post("https://api.example.com", json={"key": "value"})
"""
import ctypes
import json as _json
from typing import Optional, Dict, List, Union, Tuple, Any
from . import core
from .core import (
    setopt, easy_init, easy_cleanup, easy_perform, easy_reset,
    easy_getinfo_long, easy_getinfo_str, easy_getinfo_double,
    slist_append, slist_free_all, register_fingerprint, list_fingerprints,
    WRITE_CB_TYPE, CURLE_OK,
    CURLOPT_URL, CURLOPT_WRITEFUNCTION, CURLOPT_WRITEDATA,
    CURLOPT_HEADERFUNCTION, CURLOPT_HEADERDATA,
    CURLOPT_POSTFIELDS, CURLOPT_POSTFIELDSIZE,
    CURLOPT_HTTPHEADER, CURLOPT_NOBODY, CURLOPT_TIMEOUT,
    CURLOPT_CONNECTTIMEOUT, CURLOPT_FOLLOWLOCATION, CURLOPT_MAXREDIRS,
    CURLOPT_SSL_VERIFYPEER, CURLOPT_SSL_VERIFYHOST,
    CURLOPT_PROXY, CURLOPT_CUSTOMREQUEST,
    CURLOPT_HTTP_VERSION, CURLOPT_REFERER, CURLOPT_COOKIE,
    CURLOPT_USERAGENT, CURLOPT_NOSIGNAL, CURLOPT_VERBOSE,
    CURLOPT_RESOLVE, CURLOPT_CAINFO,
    CURLINFO_RESPONSE_CODE, CURLINFO_EFFECTIVE_URL,
    CURLINFO_CONTENT_TYPE, CURLINFO_TOTAL_TIME,
    CURL_HTTP_VERSION_2_0,
)
from dataclasses import dataclass, field
from io import BytesIO


def _find_ca_bundle():
    """Find CA certificate bundle path. Tries certifi, then Windows system paths."""
    # 1. Try certifi (if installed)
    try:
        import certifi
        return certifi.where()
    except ImportError:
        pass

    # 2. Try common Windows CA bundle locations
    import os
    candidates = [
        # Python's bundled certifi-like bundle (some distributions)
        os.path.join(os.path.dirname(__import__('ssl').get_default_verify_paths().openssl_cafile or '') or '', ''),
    ]
    # Python's default CA file
    try:
        import ssl
        cafile = ssl.get_default_verify_paths().openssl_cafile
        if cafile and os.path.isfile(cafile):
            return cafile
    except Exception:
        pass

    # 3. Try pip's CA bundle
    try:
        import pip._vendor.certifi
        return pip._vendor.certifi.where()
    except (ImportError, AttributeError):
        pass

    # 4. Try common system paths on Windows
    for path in [
        os.path.expandvars(r"%PROGRAMDATA%\Git\usr\ssl\cert.pem"),
        os.path.expandvars(r"%PROGRAMFILES%\Git\usr\ssl\cert.pem"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Git\usr\ssl\cert.pem"),
    ]:
        if os.path.isfile(path):
            return path

    return None


@dataclass
class Response:
    """HTTP response object (requests-style)."""
    status_code: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    content: bytes = b""
    url: str = ""
    elapsed: float = 0.0
    _text: Optional[str] = None

    @property
    def text(self) -> str:
        if self._text is None:
            # Try UTF-8, fallback to latin-1
            try:
                self._text = self.content.decode("utf-8")
            except UnicodeDecodeError:
                self._text = self.content.decode("latin-1")
        return self._text

    def json(self) -> Any:
        return _json.loads(self.text)

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def __repr__(self):
        return f"<Response [{self.status_code}]>"


class Session:
    """
    HTTP session with browser fingerprint impersonation.

    Args:
        impersonate: Registered fingerprint target name (e.g. "chrome144")
        timeout: Default request timeout in seconds
        verify: Whether to verify SSL certificates
        proxies: Proxy config dict, e.g. {"https": "http://proxy:8080"}
        headers: Default headers to send with every request
    """

    def __init__(
        self,
        impersonate: Optional[str] = None,
        timeout: float = 30.0,
        verify: bool = True,
        proxies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        core.global_init()
        core._auto_register_bundled()

        self._impersonate = impersonate
        self._timeout = int(timeout)
        self._verify = verify
        self._proxies = proxies or {}
        self._default_headers = headers or {}
        self._handle = 0
        self._callbacks = []  # Keep references to prevent GC

        self._init_handle()

    def _init_handle(self):
        """Create and configure a new curl handle."""
        self._handle = easy_init()
        if not self._handle:
            raise RuntimeError("curl_easy_init() failed")

        # Apply impersonation if specified
        if self._impersonate:
            rc = core.easy_impersonate(self._handle, self._impersonate, True)
            if rc != CURLE_OK:
                raise RuntimeError(f"curl_easy_impersonate failed: {rc}")

        # Common defaults
        setopt(self._handle, CURLOPT_NOSIGNAL, 1)
        setopt(self._handle, CURLOPT_TIMEOUT, self._timeout)
        setopt(self._handle, CURLOPT_CONNECTTIMEOUT, self._timeout)
        setopt(self._handle, CURLOPT_FOLLOWLOCATION, 1)
        setopt(self._handle, CURLOPT_MAXREDIRS, 10)
        setopt(self._handle, CURLOPT_SSL_VERIFYPEER, 1 if self._verify else 0)
        setopt(self._handle, CURLOPT_SSL_VERIFYHOST, 2 if self._verify else 0)

        # CA certificate path: use certifi if available, else Windows system store
        if self._verify:
            ca_path = _find_ca_bundle()
            if ca_path:
                setopt(self._handle, CURLOPT_CAINFO, ca_path)

        # Proxy
        proxy = self._proxies.get("https") or self._proxies.get("http")
        if proxy:
            setopt(self._handle, CURLOPT_PROXY, proxy)

    @staticmethod
    def register(target: str, json_config: str):
        """Register a browser fingerprint."""
        register_fingerprint(target, json_config)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, str]] = None,
        data: Optional[Union[bytes, str, Dict]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        verify: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
    ) -> Response:
        """Send an HTTP request."""
        if not self._handle:
            self._init_handle()
        else:
            easy_reset(self._handle)

        # Re-apply impersonation (reset clears it)
        if self._impersonate:
            core.easy_impersonate(self._handle, self._impersonate, True)

        # Re-apply CA certificate (reset clears it)
        if self._verify:
            ca_path = _find_ca_bundle()
            if ca_path:
                setopt(self._handle, CURLOPT_CAINFO, ca_path)

        # Build URL with params
        final_url = url
        if params:
            from urllib.parse import urlencode, urlsplit, urlunsplit
            parts = urlsplit(url)
            query = parts.query
            if query:
                query += "&"
            query += urlencode(params)
            final_url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

        setopt(self._handle, CURLOPT_URL, final_url)
        setopt(self._handle, CURLOPT_CUSTOMREQUEST, method.upper())

        # Timeout
        t = int(timeout) if timeout else self._timeout
        setopt(self._handle, CURLOPT_TIMEOUT, t)
        setopt(self._handle, CURLOPT_CONNECTTIMEOUT, t)

        # SSL verify
        v = verify if verify is not None else self._verify
        setopt(self._handle, CURLOPT_SSL_VERIFYPEER, 1 if v else 0)
        setopt(self._handle, CURLOPT_SSL_VERIFYHOST, 2 if v else 0)

        # Redirects
        setopt(self._handle, CURLOPT_FOLLOWLOCATION, 1 if allow_redirects else 0)

        # Proxy override
        if proxies:
            proxy = proxies.get("https") or proxies.get("http")
            if proxy:
                setopt(self._handle, CURLOPT_PROXY, proxy)
            else:
                setopt(self._handle, CURLOPT_PROXY, "")
        elif self._proxies:
            proxy = self._proxies.get("https") or self._proxies.get("http")
            if proxy:
                setopt(self._handle, CURLOPT_PROXY, proxy)

        # Headers
        merged_headers = dict(self._default_headers)
        if headers:
            merged_headers.update(headers)
        header_slist = 0
        if merged_headers:
            for k, v in merged_headers.items():
                header_slist = slist_append(header_slist, f"{k}: {v}")
            setopt(self._handle, CURLOPT_HTTPHEADER, ctypes.c_void_p(header_slist))

        # Body
        body = None
        if json is not None:
            body = _json.dumps(json).encode("utf-8")
            if not merged_headers.get("Content-Type"):
                header_slist = slist_append(header_slist, "Content-Type: application/json")
                setopt(self._handle, CURLOPT_HTTPHEADER, ctypes.c_void_p(header_slist))
        elif data is not None:
            if isinstance(data, dict):
                from urllib.parse import urlencode
                body = urlencode(data).encode("utf-8")
                if not merged_headers.get("Content-Type"):
                    header_slist = slist_append(header_slist, "Content-Type: application/x-www-form-urlencoded")
                    setopt(self._handle, CURLOPT_HTTPHEADER, ctypes.c_void_p(header_slist))
            elif isinstance(data, str):
                body = data.encode("utf-8")
            else:
                body = data

        if body is not None:
            setopt(self._handle, CURLOPT_POSTFIELDS, body)
            setopt(self._handle, CURLOPT_POSTFIELDSIZE, len(body))

        # Response buffers
        body_buf = BytesIO()
        header_lines: List[str] = []

        def _write_cb(data, size, nmemb, userdata):
            n = size * nmemb
            body_buf.write(ctypes.string_at(data, n))
            return n

        def _header_cb(data, size, nmemb, userdata):
            n = size * nmemb
            line = ctypes.string_at(data, n).decode("utf-8", errors="replace").strip()
            if line:
                header_lines.append(line)
            return n

        write_cb = WRITE_CB_TYPE(_write_cb)
        header_cb = WRITE_CB_TYPE(_header_cb)
        self._callbacks = [write_cb, header_cb]  # Prevent GC

        setopt(self._handle, CURLOPT_WRITEFUNCTION, ctypes.cast(write_cb, ctypes.c_void_p))
        setopt(self._handle, CURLOPT_WRITEDATA, 0)
        setopt(self._handle, CURLOPT_HEADERFUNCTION, ctypes.cast(header_cb, ctypes.c_void_p))
        setopt(self._handle, CURLOPT_HEADERDATA, 0)

        # Perform
        rc = easy_perform(self._handle)

        # Cleanup slist
        if header_slist:
            slist_free_all(header_slist)

        if rc != CURLE_OK:
            _lib = core._lib
            _lib.curl_easy_strerror.argtypes = [ctypes.c_int]
            _lib.curl_easy_strerror.restype = ctypes.c_char_p
            error_bytes = _lib.curl_easy_strerror(rc)
            if error_bytes:
                error_msg = error_bytes.decode("utf-8", errors="replace")
            else:
                error_msg = f"curl error {rc}"
            raise RuntimeError(f"curl_easy_perform failed: {error_msg} (code={rc})")

        # Parse response
        status = easy_getinfo_long(self._handle, CURLINFO_RESPONSE_CODE)
        final_url = easy_getinfo_str(self._handle, CURLINFO_EFFECTIVE_URL) or url
        elapsed = easy_getinfo_double(self._handle, CURLINFO_TOTAL_TIME)

        # Parse headers
        resp_headers = {}
        for line in header_lines:
            if ":" in line:
                k, _, v = line.partition(":")
                resp_headers[k.strip()] = v.strip()

        return Response(
            status_code=status,
            headers=resp_headers,
            content=body_buf.getvalue(),
            url=final_url,
            elapsed=elapsed,
        )

    def get(self, url, **kwargs) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs) -> Response:
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs) -> Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url, **kwargs) -> Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url, **kwargs) -> Response:
        return self.request("DELETE", url, **kwargs)

    def head(self, url, **kwargs) -> Response:
        kwargs.setdefault("allow_redirects", False)
        return self.request("HEAD", url, **kwargs)

    def close(self):
        if self._handle:
            easy_cleanup(self._handle)
            self._handle = 0
        self._callbacks = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()


class AsyncSession:
    """Placeholder for async session (future implementation)."""
    pass

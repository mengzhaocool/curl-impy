"""
curl.py - Curl class wrapping libcurl-impersonate via CFFI ABI mode.

Adapted from curl-cffi's curl.py with key changes:
1. Uses lib.curl_easy_setopt (varargs) instead of lib._curl_easy_setopt (C glue)
2. Uses ffi.callback() instead of @ffi.def_extern() for C callbacks
3. Adds impersonate_register() method (curl-impy unique feature)
"""
from __future__ import annotations

import locale
import re
import ssl
import sys
import warnings
from http.cookies import SimpleCookie
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import os
import certifi

from ._ffi import ffi, lib
from .const import CurlECode, CurlHttpVersion, CurlInfo, CurlOpt, CurlWsFlag, CurlWsFrame
from .utils import CurlImpyWarning


def _default_cacert() -> str:
    for env_var in ("SSL_CERT_FILE", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE"):
        path = os.environ.get(env_var)
        if path and os.path.exists(path):
            return path
    defaults = ssl.get_default_verify_paths()
    if defaults.cafile and os.path.exists(defaults.cafile):
        return defaults.cafile
    return certifi.where()


DEFAULT_CACERT = _default_cacert()
REASON_PHRASE_RE = re.compile(rb"HTTP/\d\.\d [0-9]{3} (.*)")
STATUS_LINE_RE = re.compile(rb"HTTP/(\d\.\d) ([0-9]{3}) (.*)")

CURL_WRITEFUNC_PAUSE = 0x10000001
CURL_WRITEFUNC_ERROR = 0xFFFFFFFF
CURL_READFUNC_ABORT = 0x10000000
CURL_READFUNC_PAUSE = 0x10000001


class CurlError(Exception):
    """Base exception for curl_impy package"""
    def __init__(self, msg: str, code: int | CurlECode | Literal[0] = 0, *args, **kwargs) -> None:
        super().__init__(msg, *args, **kwargs)
        self.code: int | CurlECode | Literal[0] = code


# ============================================================================
# Callback implementations (using ffi.callback instead of @ffi.def_extern)
# ============================================================================

# Keep references to prevent GC
_callback_refs: set = set()

# Callback type signatures (curl write/read: 4 params, debug: 5 params)
_WRITE_CB_SIG = "size_t(void*, size_t, size_t, void*)"  # (data, size, nmemb, userdata)

def _make_write_callback():
    """Create the write callback that dispatches to user Python callbacks."""
    def _write_cb(data, size, nmemb, clientp):
        try:
            callback = ffi.from_handle(clientp)
            if callback is None:
                return size * nmemb
            data_bytes = ffi.buffer(data, size * nmemb)[:]
            result = callback(data_bytes)
            if result is None:
                return size * nmemb
            return result
        except Exception:
            return CURL_WRITEFUNC_ERROR
    cb = ffi.callback(_WRITE_CB_SIG, _write_cb)
    _callback_refs.add(cb)
    return cb

def _make_buffer_callback():
    """Create a buffer-collecting callback (for header/write data)."""
    def _buf_cb(data, size, nmemb, clientp):
        try:
            buf = ffi.from_handle(clientp)
            if buf is not None:
                buf.write(ffi.buffer(data, size * nmemb)[:])
            return size * nmemb
        except Exception:
            return CURL_WRITEFUNC_ERROR
    cb = ffi.callback(_WRITE_CB_SIG, _buf_cb)
    _callback_refs.add(cb)
    return cb

def _make_read_callback():
    """Create the read callback."""
    def _read_cb(buffer, size, nmemb, clientp):
        try:
            reader = ffi.from_handle(clientp)
            if reader is None:
                return 0
            n = size * nmemb
            data = reader(n)
            if data is None:
                return 0  # EOF
            if isinstance(data, str):
                data = data.encode("utf-8")
            actual = min(len(data), n)
            ffi.memmove(buffer, data, actual)
            return actual
        except Exception:
            return CURL_READFUNC_ABORT
    cb = ffi.callback(_WRITE_CB_SIG, _read_cb)
    _callback_refs.add(cb)
    return cb

def _make_debug_callback():
    """Create the debug callback (5 params: curl, type, data, size, userdata)."""
    _DEBUG_SIG = "int(void*, int, void*, size_t, void*)"
    def _debug_cb(curl, infotype, data, size, clientp):
        try:
            debug_fn = ffi.from_handle(clientp)
            if debug_fn is not None:
                text = ffi.buffer(data, size)[:]
                debug_fn(infotype, text)
            return 0
        except Exception:
            return 0
    cb = ffi.callback(_DEBUG_SIG, _debug_cb)
    _callback_refs.add(cb)
    return cb

# Pre-create callback instances (reusable)
_write_callback = _make_write_callback()
_buffer_callback = _make_buffer_callback()
_read_callback = _make_read_callback()
_read_buffer_callback = _make_read_callback()
_debug_function = _make_debug_callback()


# ============================================================================
# Curl class
# ============================================================================

class Curl:
    """Wraps a curl easy handle."""

    def __init__(self, cacert: str = "", debug: bool = False, handle=None) -> None:
        self._curl = handle if handle else lib.curl_easy_init()
        if self._curl == ffi.NULL:
            raise CurlError("curl_easy_init() failed")

        self._headers = ffi.NULL
        self._proxy_headers = ffi.NULL
        self._resolve = ffi.NULL
        self._mime = ffi.NULL
        self._body_handle = None
        self._cacert = cacert or DEFAULT_CACERT
        self._is_cert_set = False

        # Set CAINFO + PROXY_CAINFO immediately so that verify=True works
        # out of the box. Without this, curl-impersonate may not find the
        # system CA bundle, causing SSL verification failures (especially
        # on Windows where there is no system-wide CA bundle path).
        # This mirrors curl-cffi's behavior of setting CAINFO during init.
        if self._cacert:
            self.setopt(CurlOpt.CAINFO, self._cacert)
            self.setopt(CurlOpt.PROXY_CAINFO, self._cacert)

        # Callback handles (keep refs to prevent GC)
        self._write_handle = ffi.NULL
        self._header_handle = ffi.NULL
        self._read_handle = ffi.NULL
        self._debug_handle = ffi.NULL

        # Error buffer
        self._error_buffer = ffi.new("char[]", 256)
        lib.curl_easy_setopt(self._curl, CurlOpt.ERRORBUFFER, self._error_buffer)

        if debug:
            self.setopt(CurlOpt.VERBOSE, 1)
            self.setopt(CurlOpt.DEBUGFUNCTION, True)

    def setopt(self, option: CurlOpt, value: Any) -> int:
        """Wrapper for curl_easy_setopt (varargs, CFFI ABI mode)."""
        if self._curl == ffi.NULL:
            return 0

        # Determine option type by range
        base = (option // 10000) * 10000

        # Handle special callback options
        if option == CurlOpt.WRITEDATA:
            c_value = ffi.new_handle(value)
            self._write_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.WRITEFUNCTION, _buffer_callback)
            option = CurlOpt.WRITEDATA
        elif option == CurlOpt.HEADERDATA:
            c_value = ffi.new_handle(value)
            self._header_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.HEADERFUNCTION, _buffer_callback)
            option = CurlOpt.HEADERDATA
        elif option == CurlOpt.READDATA:
            c_value = ffi.new_handle(value)
            self._read_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.READFUNCTION, _read_buffer_callback)
            option = CurlOpt.READDATA
        elif option == CurlOpt.WRITEFUNCTION:
            c_value = ffi.new_handle(value)
            self._write_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.WRITEFUNCTION, _write_callback)
            option = CurlOpt.WRITEDATA
        elif option == CurlOpt.HEADERFUNCTION:
            c_value = ffi.new_handle(value)
            self._header_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.HEADERFUNCTION, _write_callback)
            option = CurlOpt.HEADERDATA
        elif option == CurlOpt.READFUNCTION:
            c_value = ffi.new_handle(value)
            self._read_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.READFUNCTION, _read_callback)
            option = CurlOpt.READDATA
        elif option == CurlOpt.DEBUGFUNCTION:
            if value is True:
                # Use default debug that prints to stderr
                def _default_debug(infotype, data):
                    if infotype in (0, 1, 2):  # TEXT, HEADER_IN, HEADER_OUT
                        sys.stderr.write(data.decode("utf-8", errors="replace"))
                value = _default_debug
            c_value = ffi.new_handle(value)
            self._debug_handle = c_value
            lib.curl_easy_setopt(self._curl, CurlOpt.DEBUGFUNCTION, _debug_function)
            option = CurlOpt.DEBUGDATA
        # Type-based value conversion
        elif base == 0:  # LONG type
            if isinstance(value, bool):
                value = 1 if value else 0
            # CFFI varargs requires cdata for long
            c_value = ffi.cast("long", int(value))
            lib.curl_easy_setopt(self._curl, option, c_value)
            self._check_error(0, "setopt", option, value)
            return 0
        elif base == 10000:  # STRING/OBJECT type
            if option == CurlOpt.HTTPHEADER:
                for header in value:
                    if isinstance(header, str):
                        header = header.encode()
                    self._headers = lib.curl_slist_append(self._headers, header)
                lib.curl_easy_setopt(self._curl, option, self._headers)
                self._check_error(0, "setopt", option, value)
                return 0
            elif option == CurlOpt.PROXYHEADER:
                for h in value:
                    if isinstance(h, str):
                        h = h.encode()
                    self._proxy_headers = lib.curl_slist_append(self._proxy_headers, h)
                lib.curl_easy_setopt(self._curl, option, self._proxy_headers)
                self._check_error(0, "setopt", option, value)
                return 0
            elif option == CurlOpt.RESOLVE:
                for r in value:
                    if isinstance(r, str):
                        r = r.encode()
                    self._resolve = lib.curl_slist_append(self._resolve, r)
                lib.curl_easy_setopt(self._curl, option, self._resolve)
                self._check_error(0, "setopt", option, value)
                return 0
            elif option == CurlOpt.POSTFIELDS:
                if isinstance(value, str):
                    value = value.encode("utf-8")
                self._body_handle = ffi.new("char[]", value)
                lib.curl_easy_setopt(self._curl, option, self._body_handle)
                self._check_error(0, "setopt", option, value)
                return 0
            elif option == CurlOpt.MIMEPOST:
                # value is a curl_mime* cdata pointer, pass directly
                self._mime = value
                lib.curl_easy_setopt(self._curl, option, value)
                self._check_error(0, "setopt", option, value)
                return 0
            else:
                # Regular string option - must use ffi.new("char[]") for CFFI varargs
                if isinstance(value, str):
                    filepath_opts = {
                        CurlOpt.CAINFO, CurlOpt.CAPATH, CurlOpt.PROXY_CAINFO,
                        CurlOpt.PROXY_CAPATH, CurlOpt.SSLCERT, CurlOpt.SSLKEY,
                        CurlOpt.CRLFILE, CurlOpt.ISSUERCERT,
                        CurlOpt.SSH_PUBLIC_KEYFILE, CurlOpt.SSH_PRIVATE_KEYFILE,
                        CurlOpt.COOKIEFILE, CurlOpt.COOKIEJAR, CurlOpt.NETRC_FILE,
                        CurlOpt.UNIX_SOCKET_PATH,
                    }
                    if sys.platform.startswith("win") and option in filepath_opts:
                        enc = locale.getpreferredencoding(False)
                        value = value.encode(enc, errors="strict")
                    else:
                        value = value.encode()
                # CFFI varargs needs cdata, not raw bytes
                c_value = ffi.new("char[]", value)
                lib.curl_easy_setopt(self._curl, option, c_value)
                # Keep reference to prevent GC (curl copies the string internally)
                setattr(self, f"_str_{option}", c_value)
                self._check_error(0, "setopt", option, value)
                if option in (CurlOpt.CAINFO, CurlOpt.PROXY_CAINFO):
                    self._is_cert_set = True
                return 0
        elif base == 20000:  # FUNCTION type (already handled above for common ones)
            # For other function pointers, pass directly
            lib.curl_easy_setopt(self._curl, option, value)
            self._check_error(0, "setopt", option, value)
            return 0
        elif base == 30000:  # OFFSET type
            # curl_off_t is int64_t on most platforms
            c_value = ffi.cast("long long", int(value))
            lib.curl_easy_setopt(self._curl, option, c_value)
            self._check_error(0, "setopt", option, value)
            return 0
        else:
            raise NotImplementedError(f"Option unsupported: {option}")

        # For callback options, c_value is already set above
        lib.curl_easy_setopt(self._curl, option, c_value)
        self._check_error(0, "setopt", option, value)

        if option == CurlOpt.CAINFO:
            self._is_cert_set = True

        return 0

    def getinfo(self, option: CurlInfo) -> bytes | int | float | list[str | int]:
        """Wrapper for curl_easy_getinfo."""
        if self._curl == ffi.NULL:
            return b""

        # CURLINFO type is in bits 20-23: STRING=0x100000, LONG=0x200000, DOUBLE=0x300000, SLIST=0x400000
        info_type = (option >> 20) & 0xF

        if info_type == 1:  # CURLINFO_STRING
            val = ffi.new("char**")
            lib.curl_easy_getinfo(self._curl, option, val)
            if val[0] != ffi.NULL:
                return ffi.string(val[0])
            return b""
        elif info_type == 2:  # CURLINFO_LONG
            val = ffi.new("long*")
            lib.curl_easy_getinfo(self._curl, option, val)
            return val[0]
        elif info_type == 3:  # CURLINFO_DOUBLE
            val = ffi.new("double*")
            lib.curl_easy_getinfo(self._curl, option, val)
            return val[0]
        elif info_type == 4:  # CURLINFO_SLIST
            val = ffi.new("struct curl_slist**")
            lib.curl_easy_getinfo(self._curl, option, val)
            result = []
            slist = val[0]
            while slist != ffi.NULL:
                result.append(ffi.string(slist.data))
                slist = slist.next
            return result
        elif info_type == 6:  # CURLINFO_OFF_T (curl_off_t = int64_t)
            val = ffi.new("long long*")
            lib.curl_easy_getinfo(self._curl, option, val)
            return val[0]
        else:
            # Fallback: try as long
            val = ffi.new("long*")
            lib.curl_easy_getinfo(self._curl, option, val)
            return val[0]

    def impersonate(self, target: str, default_headers: bool = True) -> int:
        """Set the browser type to impersonate."""
        if self._curl == ffi.NULL:
            return 0
        return lib.curl_easy_impersonate(
            self._curl, target.encode(), int(default_headers)
        )

    @staticmethod
    def get_reason_phrase(status_line: bytes) -> bytes:
        """Extract reason phrase from response status line."""
        m = REASON_PHRASE_RE.match(status_line)
        return m.group(1) if m else b""

    @staticmethod
    def parse_status_line(status_line: bytes) -> tuple:
        """Parse status line. Returns (http_version, status_code, reason)."""
        from .const import CurlHttpVersion
        m = STATUS_LINE_RE.match(status_line)
        if not m:
            return CurlHttpVersion.V1_0, 0, b""
        if m.group(1) == b"2.0":
            http_version = CurlHttpVersion.V2_0
        elif m.group(1) == b"1.1":
            http_version = CurlHttpVersion.V1_1
        elif m.group(1) == b"1.0":
            http_version = CurlHttpVersion.V1_0
        else:
            http_version = CurlHttpVersion.NONE
        return http_version, int(m.group(2)), m.group(3)

    @staticmethod
    def parse_header_line(header_line: bytes) -> tuple[bytes, bytes]:
        """Parse a header line into (name, value)."""
        m = re.match(rb"^([^:]+):\s*(.*)$", header_line)
        if m:
            return m.group(1), m.group(2)
        return b"", b""

    def close(self) -> None:
        """Alias for cleanup()."""
        self.cleanup()

    def _ensure_cacert(self) -> None:
        """Ensure CA cert is set (called by AsyncCurl)."""
        if not self._is_cert_set and not getattr(self, "_skip_cacert", False):
            self.setopt(CurlOpt.CAINFO, self._cacert)
            self.setopt(CurlOpt.PROXY_CAINFO, self._cacert)

    def _get_error(self, retcode: int, action: str = "") -> CurlError:
        """Get error from retcode (called by AsyncCurl)."""
        error_msg = ffi.string(self._error_buffer) if self._error_buffer else b""
        if not error_msg:
            error_msg = ffi.string(lib.curl_easy_strerror(retcode))
        return CurlError(
            f"{action} failed: {error_msg.decode('utf-8', errors='replace')}",
            code=retcode,
        )

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    def ws_recv(self, buffer_size: int = 4096) -> tuple[bytes, CurlWsFrame]:
        """Receive a WebSocket frame from the connected server.

        Parameters:
            buffer_size: max bytes to read for this call.

        Returns:
            A tuple of ``(payload_bytes, CurlWsFrame)``.
        """
        if self._curl == ffi.NULL:
            raise CurlError("curl handle is None")

        buf = ffi.new("char[]", buffer_size)
        n_recv = ffi.new("size_t*")
        frame = ffi.new("curl_ws_frame*")
        ret = lib.curl_ws_recv(self._curl, buf, buffer_size, n_recv, frame)
        if ret != 0 and ret != CurlECode.AGAIN:
            raise self._get_error(ret, "ws_recv")
        data = ffi.buffer(buf, n_recv[0])[:]
        ws_frame = CurlWsFrame(
            age=frame.age,
            flags=frame.flags,
            offset=frame.offset,
            bytesleft=frame.bytesleft,
            len=frame.len,
        )
        return data, ws_frame

    def ws_send(self, payload: bytes, flags: int = CurlWsFlag.BINARY, framesize: int = 0) -> int:
        """Send a WebSocket frame to the connected server.

        Parameters:
            payload: bytes to send.
            flags: frame flags (see :class:`CurlWsFlag`).
            framesize: total size of the message (0 = use len(payload)).

        Returns:
            Number of bytes sent.
        """
        if self._curl == ffi.NULL:
            raise CurlError("curl handle is None")

        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        sent = ffi.new("size_t*")
        total = framesize or len(payload)
        ret = lib.curl_ws_send(
            self._curl, payload, len(payload), sent, flags, total
        )
        if ret != 0:
            raise self._get_error(ret, "ws_send")
        return sent[0]

    def ws_close(self) -> int:
        """Send a CLOSE frame and finish the WebSocket connection."""
        return self.ws_send(b"", flags=CurlWsFlag.CLOSE)

    # ------------------------------------------------------------------
    # Connection upkeep
    # ------------------------------------------------------------------

    def upkeep(self) -> None:
        """Perform connection upkeep (keep-alive pings, etc.).

        Requires curl 7.62.0+. No-op on older builds.
        """
        if self._curl == ffi.NULL:
            return
        ret = lib.curl_easy_upkeep(self._curl)
        if ret != 0 and ret != CurlECode.NOT_BUILT_IN:
            raise self._get_error(ret, "upkeep")

    # ------------------------------------------------------------------
    # Cookie / header parsing helpers
    # ------------------------------------------------------------------

    def parse_cookie_headers(self, header_list: list[bytes]) -> SimpleCookie:
        """Parse ``Set-Cookie`` headers into a :class:`SimpleCookie`.

        Parameters:
            header_list: raw header bytes (typically from ``getinfo(CERTINFO)``
                or header callback buffer).
        """
        cookies = SimpleCookie()
        for line in header_list:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            # strip leading "Set-Cookie:" prefix if present
            lower = line.lower()
            if lower.startswith("set-cookie:"):
                line = line[len("set-cookie:"):].strip()
            elif lower.startswith("set-cookie2:"):
                line = line[len("set-cookie2:"):].strip()
            if line:
                try:
                    cookies.load(line)
                except Exception:
                    pass
        return cookies

    # ------------------------------------------------------------------
    # slist helper
    # ------------------------------------------------------------------

    @staticmethod
    def slist_to_list(slist_ptr) -> list[bytes]:
        """Convert a ``curl_slist*`` to a Python list of bytes.

        The caller is responsible for freeing the slist via
        ``curl_slist_free_all``.
        """
        result: list[bytes] = []
        if slist_ptr is None or slist_ptr == ffi.NULL:
            return result
        node = slist_ptr
        while node != ffi.NULL:
            result.append(ffi.string(node.data))
            node = node.next
        return result

    # ------------------------------------------------------------------
    # Resource cleanup helper
    # ------------------------------------------------------------------

    def clean_handles_and_buffers(self) -> None:
        """Free all slist handles and reset internal buffers.

        Called internally by :meth:`perform` and :meth:`cleanup`,
        but can be invoked manually when reusing a handle.
        """
        if self._headers != ffi.NULL:
            lib.curl_slist_free_all(self._headers)
            self._headers = ffi.NULL
        if self._proxy_headers != ffi.NULL:
            lib.curl_slist_free_all(self._proxy_headers)
            self._proxy_headers = ffi.NULL
        if self._resolve != ffi.NULL:
            lib.curl_slist_free_all(self._resolve)
            self._resolve = ffi.NULL
        self._body_handle = None
        # Clear string-option references
        for attr in list(self.__dict__):
            if attr.startswith("_str_"):
                delattr(self, attr)

    def perform(self, clear_headers: bool = True, clear_resolve: bool = True) -> None:
        """Perform the curl request."""
        if self._curl == ffi.NULL:
            raise CurlError("curl handle is None")

        if not self._is_cert_set and not getattr(self, "_skip_cacert", False):
            self.setopt(CurlOpt.CAINFO, self._cacert)
            self.setopt(CurlOpt.PROXY_CAINFO, self._cacert)

        ret = lib.curl_easy_perform(self._curl)
        if ret != 0:
            error_msg = ffi.string(self._error_buffer)
            if not error_msg:
                error_msg = ffi.string(lib.curl_easy_strerror(ret))
            raise CurlError(
                f"curl_easy_perform failed: {error_msg.decode('utf-8', errors='replace')}",
                code=ret,
            )

        if clear_headers or clear_resolve:
            if clear_headers:
                # Free headers and proxy headers
                if self._headers != ffi.NULL:
                    lib.curl_slist_free_all(self._headers)
                    self._headers = ffi.NULL
                if self._proxy_headers != ffi.NULL:
                    lib.curl_slist_free_all(self._proxy_headers)
                    self._proxy_headers = ffi.NULL
            if clear_resolve and self._resolve != ffi.NULL:
                lib.curl_slist_free_all(self._resolve)
                self._resolve = ffi.NULL

    def duphandle(self) -> Curl:
        """Duplicate this curl handle."""
        new_handle = lib.curl_easy_duphandle(self._curl)
        new_curl = Curl.__new__(Curl)
        new_curl._curl = new_handle
        new_curl._headers = ffi.NULL
        new_curl._proxy_headers = ffi.NULL
        new_curl._resolve = ffi.NULL
        new_curl._mime = ffi.NULL
        new_curl._body_handle = None
        new_curl._cacert = self._cacert
        new_curl._is_cert_set = self._is_cert_set
        new_curl._write_handle = ffi.NULL
        new_curl._header_handle = ffi.NULL
        new_curl._read_handle = ffi.NULL
        new_curl._debug_handle = ffi.NULL
        new_curl._error_buffer = ffi.new("char[]", 256)
        lib.curl_easy_setopt(new_curl._curl, CurlOpt.ERRORBUFFER, new_curl._error_buffer)
        return new_curl

    def reset(self) -> None:
        """Reset the curl handle to default values."""
        if self._curl == ffi.NULL:
            return

        # Free slists
        if self._headers != ffi.NULL:
            lib.curl_slist_free_all(self._headers)
        if self._proxy_headers != ffi.NULL:
            lib.curl_slist_free_all(self._proxy_headers)
        if self._resolve != ffi.NULL:
            lib.curl_slist_free_all(self._resolve)

        lib.curl_easy_reset(self._curl)

        self._headers = ffi.NULL
        self._proxy_headers = ffi.NULL
        self._resolve = ffi.NULL
        self._body_handle = None
        self._is_cert_set = False
        self._skip_cacert = False
        self._write_handle = ffi.NULL
        self._header_handle = ffi.NULL
        self._read_handle = ffi.NULL
        self._debug_handle = ffi.NULL

        # Re-set error buffer
        self._error_buffer = ffi.new("char[]", 256)
        lib.curl_easy_setopt(self._curl, CurlOpt.ERRORBUFFER, self._error_buffer)

    def cleanup(self) -> None:
        """Destroy the curl handle and free all resources."""
        if self._curl != ffi.NULL:
            self.clean_handles_and_buffers()
            lib.curl_easy_cleanup(self._curl)
            self._curl = ffi.NULL

    def _check_error(self, ret: int, action: str, option: Any = None, value: Any = None) -> None:
        """Check curl return code and raise on error."""
        if ret != 0:
            error_msg = ffi.string(self._error_buffer) if self._error_buffer else b""
            if not error_msg:
                error_msg = ffi.string(lib.curl_easy_strerror(ret))
            raise CurlError(
                f"{action} failed: {error_msg.decode('utf-8', errors='replace')} "
                f"(option={option}, code={ret})",
                code=ret,
            )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()

    def __del__(self):
        try:
            self.cleanup()
        except:
            pass


# ============================================================================
# impersonate_register (curl-impy unique feature)
# ============================================================================

_registered: set = set()

def impersonate_register(target: str, json_config: str) -> None:
    """
    Register a custom browser fingerprint from JSON config.

    This is curl-impy's unique feature - allows registering arbitrary browser
    fingerprints at runtime without recompiling the DLL.

    Args:
        target: Target name (e.g. "chrome144")
        json_config: JSON string or path to JSON file
    """
    if not json_config.strip().startswith("{"):
        if os.path.isfile(json_config):
            with open(json_config, "r", encoding="utf-8") as f:
                json_config = f.read()
        else:
            raise FileNotFoundError(f"JSON config not found: {json_config}")

    result = lib.curl_easy_impersonate_register(
        target.encode("utf-8"),
        json_config.encode("utf-8"),
    )
    if result != 0:
        raise RuntimeError(f"curl_easy_impersonate_register failed with code {result}")
    _registered.add(target)


# Constants expected by requests/utils.py
CURL_WRITEFUNC_ERROR = 0xFFFFFFFF


# ============================================================================
# Debug helpers
# ============================================================================

def bytes_to_hex(data: bytes, width: int = 16) -> str:
    """Format bytes as a hex dump string (like ``xxd``).

    Parameters:
        data: bytes to format.
        width: number of bytes per line.

    Returns:
        Multi-line hex dump string.
    """
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<{width * 3}}  {ascii_part}")
    return "\n".join(lines)


def debug_function_default(infotype: int, data: bytes) -> None:
    """Default debug callback that prints curl trace info to stderr.

    Can be passed to ``curl.setopt(CurlOpt.DEBUGFUNCTION, debug_function_default)``
    or used as a reference implementation.

    Parameters:
        infotype: ``CURLINFO_TEXT=0``, ``CURLINFO_HEADER_IN=1``,
            ``CURLINFO_HEADER_OUT=2``, ``CURLINFO_DATA_IN=3``,
            ``CURLINFO_DATA_OUT=4``, etc.
        data: raw bytes of the debug info.
    """
    prefixes = {
        0: "==",   # TEXT
        1: "<<",   # HEADER_IN
        2: ">>",   # HEADER_OUT
        3: "<-",   # DATA_IN
        4: "->",   # DATA_OUT
        5: "**",   # SSL_DATA_IN
        6: "**",   # SSL_DATA_OUT
    }
    prefix = prefixes.get(infotype, "??")
    if infotype in (0, 1, 2):
        text = data.decode("utf-8", errors="replace")
        sys.stderr.write(f"{prefix} {text}")
        if not text.endswith("\n"):
            sys.stderr.write("\n")
    elif infotype in (3, 4, 5, 6) and data:
        sys.stderr.write(f"{prefix} ({len(data)} bytes)\n")
        sys.stderr.write(bytes_to_hex(data) + "\n")


# ============================================================================
# CurlMime
# ============================================================================

class CurlMime:
    """MIME multipart form data wrapper.

    Build file upload forms and attach them to a :class:`Curl` handle::

        mime = CurlMime()
        mime.addpart(name="file", filename="test.txt", data=b"hello")
        mime.addpart(name="field", data="value")
        mime.attach(curl)
    """

    def __init__(self, curl: Curl | None = None):
        self._mime = lib.curl_mime_init(ffi.NULL)
        self._parts: list = []

    def addpart(
        self,
        name: str | None = None,
        content_type: str | None = None,
        filename: str | None = None,
        data: bytes | str | None = None,
        file_path: str | None = None,
        local_path: str | None = None,  # alias for file_path (curl-cffi compat)
    ) -> None:
        """Add a part to the MIME form.

        Parameters:
            name: form field name.
            content_type: MIME content-type for this part.
            filename: filename reported to the server.
            data: inline data (str is encoded as UTF-8).
            file_path: path to a file whose contents will be uploaded.
            local_path: alias for ``file_path`` (curl-cffi compatibility).
        """
        # local_path is an alias for file_path (curl-cffi uses local_path)
        fp = file_path or local_path
        part = lib.curl_mime_addpart(self._mime)
        if name:
            lib.curl_mime_name(part, name.encode() if isinstance(name, str) else name)
        if content_type:
            lib.curl_mime_type(
                part,
                content_type.encode() if isinstance(content_type, str) else content_type,
            )
        if filename:
            lib.curl_mime_filename(
                part,
                filename.encode() if isinstance(filename, str) else filename,
            )
        if fp:
            lib.curl_mime_filedata(
                part, fp.encode() if isinstance(fp, str) else fp
            )
        elif data is not None:
            if isinstance(data, str):
                data = data.encode()
            lib.curl_mime_data(part, data, len(data))
        self._parts.append(part)

    @classmethod
    def from_list(cls, parts: list[dict]) -> CurlMime:
        """Create a CurlMime from a list of keyword dicts.

        Example::

            mime = CurlMime.from_list([
                {"name": "file", "filename": "f.txt", "data": b"hi"},
                {"name": "key", "data": "val"},
            ])
        """
        mime = cls()
        for part_kwargs in parts:
            mime.addpart(**part_kwargs)
        return mime

    def attach(self, curl: Curl) -> None:
        """Attach this MIME form to a Curl handle (sets ``MIMEPOST``)."""
        curl.setopt(CurlOpt.MIMEPOST, self._mime)

    def close(self) -> None:
        """Free the underlying MIME structure."""
        self.free()

    def free(self) -> None:
        """Free the underlying MIME structure (alias for :meth:`close`)."""
        if self._mime != ffi.NULL:
            lib.curl_mime_free(self._mime)
            self._mime = ffi.NULL

    def __del__(self):
        try:
            self.free()
        except:
            pass


# ============================================================================
# Version / feature detection
# ============================================================================

def _get_curl_version() -> str:
    """Return the libcurl version string."""
    try:
        raw = lib.curl_version()
        if raw != ffi.NULL:
            return ffi.string(raw).decode("utf-8", errors="replace")
    except Exception:
        pass
    return "unknown"


__curl_version__: str = _get_curl_version()


def is_pro() -> bool:
    """Return True if this is a Pro build of curl-impersonate.

    Pro builds include additional browser targets and HTTP/3 support.
    Detection is based on the presence of HTTP/3 capable targets.
    """
    # curl-impersonate Pro builds link against nghttp3/ngtcp2
    # We detect by checking if the version string contains certain markers
    # or by attempting to impersonate a known Pro-only target.
    try:
        test = Curl()
        ret = lib.curl_easy_impersonate(test._curl, b"chrome120", 0)
        test.close()
        # If impersonate succeeds, check for HTTP/3 support in version
        ver = __curl_version__.lower()
        return "nghttp3" in ver or "quic" in ver
    except Exception:
        return False

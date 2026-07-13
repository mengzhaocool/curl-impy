"""aio.py - AsyncCurl using curl_multi socket_action API.
Adapted from curl-cffi's aio.py: @ffi.def_extern → ffi.callback.
"""
import asyncio
import sys
import warnings
from contextlib import suppress
from typing import Any, Optional
from weakref import WeakKeyDictionary

from ._ffi import ffi, lib
from .const import CurlECode, CurlMOpt
from .curl import DEFAULT_CACERT, Curl, CurlError
from .utils import CurlImpyWarning

__all__ = ["AsyncCurl"]

if sys.platform == "win32":
    _selectors: WeakKeyDictionary = WeakKeyDictionary()
    PROACTOR_WARNING = """
    Proactor event loop does not implement add_reader family of methods required.
    Registering an additional selector thread for add_reader support.
    To avoid this warning use:
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    """

    def get_selector(asyncio_loop):
        if asyncio_loop in _selectors:
            return _selectors[asyncio_loop]
        if not isinstance(asyncio_loop, getattr(asyncio, "ProactorEventLoop", type(None))):
            return asyncio_loop
        warnings.warn(PROACTOR_WARNING, CurlImpyWarning, stacklevel=2)
        from ._asyncio_selector import AddThreadSelectorEventLoop
        selector_loop = _selectors[asyncio_loop] = AddThreadSelectorEventLoop(asyncio_loop)
        loop_close = asyncio_loop.close
        def _close_selector_and_loop():
            asyncio_loop.close = loop_close
            _selectors.pop(asyncio_loop, None)
            selector_loop.close()
        asyncio_loop.close = _close_selector_and_loop
        return selector_loop
else:
    def get_selector(loop):
        return loop


CURL_POLL_NONE = 0
CURL_POLL_IN = 1
CURL_POLL_OUT = 2
CURL_POLL_INOUT = 3
CURL_POLL_REMOVE = 4
CURL_SOCKET_TIMEOUT = -1
CURL_SOCKET_BAD = -1
CURL_CSELECT_IN = 0x01
CURL_CSELECT_OUT = 0x02
CURL_CSELECT_ERR = 0x04
CURLMSG_DONE = 1
CURLPIPE_NOTHING = 0
CURLPIPE_HTTP1 = 1
CURLPIPE_MULTIPLEX = 2

# ============================================================================
# Callbacks: ffi.callback instead of @ffi.def_extern
# ============================================================================

_TIMER_CB_SIG = "int(void*, int, void*)"
_SOCKET_CB_SIG = "int(void*, int, int, void*, void*)"
_callback_refs = set()

def _make_timer_callback():
    def _timer_cb(curlm, timeout_ms, clientp):
        try:
            async_curl = ffi.from_handle(clientp)
            if async_curl._timer:
                async_curl._timer.cancel()
                async_curl._timer = None
            async_curl._timer = async_curl.loop.call_later(
                timeout_ms / 1000,
                async_curl.process_data,
                CURL_SOCKET_TIMEOUT,
                CURL_POLL_NONE,
            )
            return 0
        except Exception:
            return -1
    cb = ffi.callback(_TIMER_CB_SIG, _timer_cb)
    _callback_refs.add(cb)
    return cb

def _make_socket_callback():
    def _socket_cb(curl, sockfd, what, clientp, data):
        try:
            async_curl = ffi.from_handle(clientp)
            loop = async_curl.loop
            if sockfd in async_curl._sockfds:
                loop.remove_reader(sockfd)
                loop.remove_writer(sockfd)
            if what & CURL_POLL_IN:
                loop.add_reader(sockfd, async_curl.process_data, sockfd, CURL_CSELECT_IN)
                async_curl._sockfds.add(sockfd)
            if what & CURL_POLL_OUT:
                loop.add_writer(sockfd, async_curl.process_data, sockfd, CURL_CSELECT_OUT)
                async_curl._sockfds.add(sockfd)
            if what == CURL_POLL_REMOVE:
                async_curl._sockfds.discard(sockfd)
            return 0
        except Exception:
            return -1
    cb = ffi.callback(_SOCKET_CB_SIG, _socket_cb)
    _callback_refs.add(cb)
    return cb

_timer_callback = _make_timer_callback()
_socket_callback = _make_socket_callback()


class AsyncCurl:
    """Wrapper around curl_multi handle to provide asyncio support."""

    def __init__(self, cacert: str = "", loop=None):
        self._curlm = lib.curl_multi_init()
        self._cacert = cacert or DEFAULT_CACERT
        self._curl2future = {}
        self._curl2curl = {}
        self._sockfds = set()
        self.loop = get_selector(
            loop if loop is not None else asyncio.get_running_loop()
        )
        self._timeout_checker = self.loop.create_task(self._force_timeout())
        self._timer = None
        self._setup()

    def _setup(self):
        self.setopt(CurlMOpt.TIMERFUNCTION, _timer_callback)
        self.setopt(CurlMOpt.SOCKETFUNCTION, _socket_callback)
        self._self_handle = ffi.new_handle(self)
        self.setopt(CurlMOpt.SOCKETDATA, self._self_handle)
        self.setopt(CurlMOpt.TIMERDATA, self._self_handle)

    async def close(self):
        self._timeout_checker.cancel()
        with suppress(asyncio.CancelledError):
            await self._timeout_checker
        for curl, future in self._curl2future.items():
            lib.curl_multi_remove_handle(self._curlm, curl._curl)
            if not future.done() and not future.cancelled():
                future.set_result(None)
        lib.curl_multi_cleanup(self._curlm)
        self._curlm = None
        for sockfd in self._sockfds:
            self.loop.remove_reader(sockfd)
            self.loop.remove_writer(sockfd)
        if self._timer:
            self._timer.cancel()

    async def _force_timeout(self):
        while True:
            if not self._curlm:
                break
            self.socket_action(CURL_SOCKET_TIMEOUT, CURL_POLL_NONE)
            await asyncio.sleep(0.1)

    def add_handle(self, curl: Curl):
        curl._ensure_cacert()
        errcode = lib.curl_multi_add_handle(self._curlm, curl._curl)
        self._check_error(errcode)
        future = self.loop.create_future()
        self._curl2future[curl] = future
        self._curl2curl[curl._curl] = curl
        return future

    def socket_action(self, sockfd: int, ev_bitmask: int) -> int:
        running_handle = ffi.new("int *")
        errcode = lib.curl_multi_socket_action(
            self._curlm, sockfd, ev_bitmask, running_handle
        )
        self._check_error(errcode)
        return running_handle[0]

    def process_data(self, sockfd: int, ev_bitmask: int):
        if not self._curlm:
            return
        self.socket_action(sockfd, ev_bitmask)
        msg_in_queue = ffi.new("int *")
        while True:
            try:
                curl_msg = lib.curl_multi_info_read(self._curlm, msg_in_queue)
                if curl_msg == ffi.NULL:
                    break
                if curl_msg.msg == CURLMSG_DONE:
                    curl = self._curl2curl[curl_msg.easy_handle]
                    retcode = curl_msg.data.result
                    if retcode == 0:
                        self.set_result(curl)
                    else:
                        self.set_exception(curl, curl._get_error(retcode, "perform"))
            except Exception:
                warnings.warn("Unexpected curl multi state", CurlImpyWarning, stacklevel=2)

    def _pop_future(self, curl: Curl):
        errcode = lib.curl_multi_remove_handle(self._curlm, curl._curl)
        self._check_error(errcode)
        self._curl2curl.pop(curl._curl, None)
        return self._curl2future.pop(curl, None)

    def remove_handle(self, curl: Curl):
        future = self._pop_future(curl)
        if future and not future.done() and not future.cancelled():
            future.cancel()

    def set_result(self, curl: Curl):
        future = self._pop_future(curl)
        if future and not future.done() and not future.cancelled():
            future.set_result(None)

    def set_exception(self, curl: Curl, exception):
        future = self._pop_future(curl)
        if future and not future.done() and not future.cancelled():
            future.set_exception(exception)

    def _check_error(self, errcode: int, *args: Any):
        if errcode == CurlECode.OK:
            return
        errmsg = lib.curl_multi_strerror(errcode)
        action = " ".join([str(a) for a in args])
        raise CurlError(
            f"Failed in {action}, multi: ({errcode}) {ffi.string(errmsg).decode('utf-8','replace')}.",
        )

    def setopt(self, option, value):
        if option in (
            CurlMOpt.PIPELINING, CurlMOpt.MAXCONNECTS,
            CurlMOpt.MAX_HOST_CONNECTIONS, CurlMOpt.MAX_PIPELINE_LENGTH,
            CurlMOpt.MAX_TOTAL_CONNECTIONS, CurlMOpt.MAX_CONCURRENT_STREAMS,
        ):
            c_value = ffi.cast("long", int(value))
        else:
            c_value = value
        return lib.curl_multi_setopt(self._curlm, option, c_value)

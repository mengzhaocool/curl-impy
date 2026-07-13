# curl-impy

Python binding for [curl-impersonate](https://github.com/lwthiker/curl-impersonate) with custom fingerprint registration.

## Features

- **curl-cffi compatible API** — same `Session`, `Curl`, `Cookies`, `Headers` interface
- **Runtime fingerprint registration** — register custom browser fingerprints from JSON config via `impersonate_register()`
- **CFFI ABI mode** — loads `libcurl-impersonate.dll` at runtime, no compilation needed
- **Full feature set** — Cookie management, Content-Encoding, redirects, proxy, async, WebSocket

## Installation

```bash
pip install curl-impy
```

DLL is bundled in the package — no external dependencies needed (except `cffi` and `certifi`).

## Quick Start

```python
from curl_impy import Session, impersonate_register

# Register a custom browser fingerprint (unique to curl-impy)
impersonate_register("chrome144", "path/to/Chrome144.json")

# Use it like curl-cffi
with Session(impersonate="chrome144") as s:
    r = s.get("https://example.com")
    print(r.status_code, r.text)

# Or use low-level Curl API
from curl_impy import Curl, CurlOpt, CurlInfo

c = Curl()
c.impersonate("chrome131")
c.setopt(CurlOpt.URL, "https://example.com")
c.setopt(CurlOpt.SSL_VERIFYPEER, 0)
buf = bytearray()
c.setopt(CurlOpt.WRITEFUNCTION, lambda data: (buf.extend(data), len(data))[1])
c.perform()
print(c.getinfo(CurlInfo.RESPONSE_CODE))
c.close()
```

## API

Identical to [curl-cffi](https://github.com/lexiforest/curl-cffi):

| Feature | API |
|---------|-----|
| Session | `Session.get/post/put/delete/patch/head` |
| Curl | `Curl.setopt/perform/getinfo/impersonate/reset/cleanup` |
| Cookies | Auto Set-Cookie parsing, cross-request, Path matching, jar persistence |
| Encoding | gzip/deflate auto-decompress |
| Redirect | 301/302 follow/no-follow |
| Proxy | Direct/HTTP proxy |
| Async | `AsyncSession`/`AsyncCurl` |
| WebSocket | `WebSocket`/`AsyncWebSocket` |

### Unique feature: `impersonate_register()`

```python
from curl_impy import impersonate_register

# Register any browser fingerprint at runtime from JSON config
impersonate_register("chrome144", "Chrome144.json")

# Then use it
with Session(impersonate="chrome144") as s:
    r = s.get("https://example.com")
```

This is not available in curl-cffi — it allows registering custom fingerprints without recompiling the DLL.

## Architecture

```
curl_impy/
├── _ffi.py              # CFFI ABI: cdef + ffi.dlopen(libcurl-impersonate.dll)
├── curl.py              # Curl class (varargs setopt + ffi.callback)
├── aio.py               # AsyncCurl (curl_multi socket_action)
├── const.py             # CurlOpt/CurlInfo/CurlMOpt enums
├── libs/win_x64/        # Bundled DLL
└── requests/            # curl-cffi compatible requests API
    ├── session.py       # Session/AsyncSession
    ├── cookies.py       # Cookie management
    ├── headers.py       # Header normalization
    ├── models.py        # Request/Response
    └── websockets.py    # WebSocket support
```

## License

MIT

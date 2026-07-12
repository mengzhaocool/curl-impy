# curl-impy

Python binding for **curl-impersonate-chrome** — impersonate any Chrome version's TLS/HTTP2 fingerprint by providing a JSON config.

## Features

- **Chrome 120+ support** — includes post-quantum key exchange (X25519MLKEM768), ECH GREASE
- **Any Chrome version** — just provide a JSON fingerprint config, no code changes
- **Zero external dependencies** — DLL is statically linked (BoringSSL, zlib, brotli, zstd, nghttp2)
- **Proxy isolation** — ignores `http_proxy`, `https_proxy`, `ALL_PROXY`, system proxy settings
- **Header case fix** — no duplicate headers when overriding `User-Agent` with `USER-AGENT`
- **requests-style API** — familiar `Session.get()`, `Session.post()`, etc.

## Installation

```bash
# From source (GitHub)
git clone https://github.com/mengzhaocool/curl-impy.git
cd curl-impy
pip install .

# Or just use directly without install
python -c "from curl_impy import Session; ..."
```

## Quick Start

```python
from curl_impy import Session

# Chrome 144 fingerprint (bundled)
with Session(impersonate="chrome144", verify=False) as s:
    r = s.get("https://httpbin.org/get")
    print(r.status_code)        # 200
    print(r.json()["headers"]["User-Agent"])  # Chrome/144.0.0.0
```

## Custom Fingerprint

Register any Chrome version by providing a JSON config:

```python
from curl_impy import Session

# Register a custom fingerprint
Session.register("chrome120", "path/to/Chrome120.json")

with Session(impersonate="chrome120") as s:
    r = s.get("https://httpbin.org/get")
```

## API Reference

### `Session(impersonate=None, timeout=30, verify=True, proxies=None, headers=None)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `impersonate` | `str` | `None` | Registered fingerprint target name |
| `timeout` | `float` | `30` | Request timeout in seconds |
| `verify` | `bool` | `True` | Verify SSL certificates |
| `proxies` | `dict` | `None` | Proxy config, e.g. `{"https": "http://proxy:8080"}` |
| `headers` | `dict` | `None` | Default headers for all requests |

### Methods

| Method | Description |
|--------|-------------|
| `get(url, **kwargs)` | GET request |
| `post(url, **kwargs)` | POST request |
| `put(url, **kwargs)` | PUT request |
| `patch(url, **kwargs)` | PATCH request |
| `delete(url, **kwargs)` | DELETE request |
| `head(url, **kwargs)` | HEAD request |
| `request(method, url, **kwargs)` | Generic request |

### `Session.register(target, json_config)` (static)

Register a browser fingerprint from JSON file or string.

### `register_fingerprint(target, json_config)`

Module-level fingerprint registration.

### Response Object

| Property | Type | Description |
|----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `headers` | `dict` | Response headers |
| `content` | `bytes` | Response body (raw) |
| `text` | `str` | Response body (decoded) |
| `url` | `str` | Final URL (after redirects) |
| `elapsed` | `float` | Time in seconds |
| `json()` | `Any` | Parse body as JSON |
| `ok` | `bool` | True if status < 400 |

## Proxy Isolation

The DLL ignores ALL proxy environment variables and system proxy settings:

```python
import os
os.environ["http_proxy"] = "http://127.0.0.1:1"  # Ignored
os.environ["https_proxy"] = "http://127.0.0.1:1"  # Ignored
os.environ["ALL_PROXY"] = "http://127.0.0.1:1"    # Ignored

# System Windows proxy (registry) — also ignored

with Session(impersonate="chrome144") as s:
    r = s.get("https://www.baidu.com")  # Works! Direct connection.
    # No proxy leak.

# Explicit proxy still works:
with Session(impersonate="chrome144", proxies={"https": "http://proxy:8080"}) as s:
    r = s.get("https://www.baidu.com")  # Uses the proxy.
```

## Supported Platforms

| Platform | Status |
|----------|--------|
| Windows x64 | ✅ Supported |
| Windows x86 | ✅ Supported |
| Linux | ❌ Not yet |
| macOS | ❌ Not yet |

## License

MIT

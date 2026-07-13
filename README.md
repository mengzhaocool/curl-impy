# curl-impy

Python binding for [curl-impersonate](https://github.com/lwthiker/curl-impersonate) via CFFI ABI mode.

No compilation required — DLLs are bundled in the package.

## Install

```bash
pip install git+https://github.com/mengzhaocool/curl-impy.git
```

## Quick Start

```python
from curl_impy.requests import Session

with Session(impersonate="chrome") as s:
    r = s.get("https://www.example.com", verify=True)
    print(r.status_code)  # 200
```

## Impersonate Targets

```python
import curl_impy

# List built-in targets (38 targets from DLL)
print(curl_impy.impersonate_list())

# Register custom fingerprint at runtime
curl_impy.impersonate_register("my_browser", '{"ja3": "...", "user_agent": "..."}')

# Use it
with Session(impersonate="my_browser") as s:
    r = s.get("https://www.example.com")
```

## Low-level API

```python
from curl_impy import Curl, CurlOpt, CurlInfo
import io

c = Curl()
c.setopt(CurlOpt.URL, b"https://www.example.com")
c.setopt(CurlOpt.SSL_VERIFYPEER, 1)
buf = io.BytesIO()
c.setopt(CurlOpt.WRITEDATA, buf)
c.perform()
print(c.getinfo(CurlInfo.RESPONSE_CODE))  # 200
c.close()
```

## License

MIT

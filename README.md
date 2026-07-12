# curl-impy

[中文](#中文) | [English](#english)

---

## 中文

Python 浏览器指纹模拟库 —— 通过 JSON 配置模拟任意 Chrome 版本的 TLS/HTTP2 指纹。

### 与其他 curl 版本的区别

| 特性 | curl-impy | 其他 curl 版本 |
|------|-----------|---------------|
| Chrome 120+ 指纹模拟 | ✅ 支持后量子密钥交换 (X25519MLKEM768) | ❌ 缺少后量子加密套件 |
| ECH (Encrypted Client Hello) | ✅ 支持 GREASE | ❌ 不支持 |
| 任意 Chrome 版本模拟 | ✅ 提供 JSON 即可 | ❌ 仅内置固定版本 |
| 代理环境变量隔离 | ✅ 完全忽略 http_proxy/https_proxy/ALL_PROXY | ❌ 受环境变量影响 |
| 系统全局代理隔离 | ✅ 忽略 Windows 注册表代理设置 | ❌ 受系统代理影响 |
| HTTP 头部大小写 | ✅ 大小写不敏感，无重复头 | ❌ 可能出现同名重复头 |
| SSL 证书验证 | ✅ 自动配置 CA 证书路径 | ⚠️ 需手动配置 |
| 外部依赖 | ✅ 零依赖（DLL 静态链接 BoringSSL/zlib/brotli/zstd） | ⚠️ 依赖动态链接库 |

### 安装

```bash
pip install git+https://github.com/mengzhaocool/curl-impy.git
```

### 快速开始

```python
from curl_impy import Session

# Chrome 144 指纹（内置）
with Session(impersonate="chrome144") as s:
    r = s.get("https://httpbin.org/get")
    print(r.status_code)        # 200
    print(r.json()["headers"]["User-Agent"])  # Chrome/144.0.0.0
```

### 自定义指纹

注册任意 Chrome 版本，只需提供 JSON 指纹配置：

```python
from curl_impy import Session

Session.register("chrome120", "path/to/Chrome120.json")

with Session(impersonate="chrome120") as s:
    r = s.get("https://httpbin.org/get")
```

### API

```python
with Session(
    impersonate="chrome144",   # 指纹目标名
    timeout=30,                # 超时秒数
    verify=True,               # SSL 验证（默认开启）
    proxies={"https": "..."},  # 显式代理
    headers={"X-Key": "val"},  # 默认请求头
) as s:
    r = s.get(url, params={"q": "1"})
    r = s.post(url, json={"key": "value"})
    r = s.put(url, data=b"bytes")
    r = s.patch(url, headers={"X-Extra": "1"})
    r = s.delete(url)
    r = s.head(url)

    print(r.status_code, r.headers, r.text, r.json())
    print(r.url, r.elapsed)
```

### 代理隔离

```python
import os
os.environ["http_proxy"] = "http://127.0.0.1:1"   # 被忽略
os.environ["https_proxy"] = "http://127.0.0.1:1"   # 被忽略
os.environ["ALL_PROXY"] = "http://127.0.0.1:1"     # 被忽略

with Session(impersonate="chrome144") as s:
    r = s.get("https://www.baidu.com")  # 直连成功

# 显式代理仍然生效
with Session(impersonate="chrome144", proxies={"https": "http://proxy:8080"}) as s:
    r = s.get("https://www.baidu.com")  # 走代理
```

### 支持平台

| 平台 | 状态 |
|------|------|
| Windows x64 | ✅ |
| Windows x86 | ✅ |
| Linux x64 | ✅ (CI 自动构建) |
| macOS (Universal) | ✅ (CI 自动构建) |

---

## English

Python browser fingerprint impersonation library — impersonate any Chrome version's TLS/HTTP2 fingerprint via JSON config.

### What Makes It Different

| Feature | curl-impy | Other curl versions |
|---------|-----------|---------------------|
| Chrome 120+ fingerprint | ✅ Post-quantum key exchange (X25519MLKEM768) | ❌ Missing post-quantum ciphers |
| ECH (Encrypted Client Hello) | ✅ GREASE supported | ❌ Not supported |
| Any Chrome version | ✅ Just provide a JSON config | ❌ Only built-in fixed versions |
| Proxy env isolation | ✅ Ignores http_proxy/https_proxy/ALL_PROXY | ❌ Affected by env vars |
| System proxy isolation | ✅ Ignores Windows registry proxy | ❌ Affected by system proxy |
| Header case handling | ✅ Case-insensitive, no duplicates | ❌ May produce duplicate headers |
| SSL verification | ✅ Auto-configures CA bundle | ⚠️ Manual setup needed |
| External dependencies | ✅ Zero (DLL statically links BoringSSL/zlib/brotli/zstd) | ⚠️ Depends on dynamic libraries |

### Installation

```bash
pip install git+https://github.com/mengzhaocool/curl-impy.git
```

### Quick Start

```python
from curl_impy import Session

with Session(impersonate="chrome144") as s:
    r = s.get("https://httpbin.org/get")
    print(r.status_code)        # 200
    print(r.json()["headers"]["User-Agent"])  # Chrome/144.0.0.0
```

### Custom Fingerprint

Register any Chrome version by providing a JSON fingerprint config:

```python
from curl_impy import Session

Session.register("chrome120", "path/to/Chrome120.json")

with Session(impersonate="chrome120") as s:
    r = s.get("https://httpbin.org/get")
```

### API

```python
with Session(
    impersonate="chrome144",   # fingerprint target
    timeout=30,                # timeout in seconds
    verify=True,               # SSL verification (default on)
    proxies={"https": "..."},  # explicit proxy
    headers={"X-Key": "val"},  # default headers
) as s:
    r = s.get(url, params={"q": "1"})
    r = s.post(url, json={"key": "value"})
    r = s.put(url, data=b"bytes")
    r = s.patch(url, headers={"X-Extra": "1"})
    r = s.delete(url)
    r = s.head(url)

    print(r.status_code, r.headers, r.text, r.json())
    print(r.url, r.elapsed)
```

### Proxy Isolation

```python
import os
os.environ["http_proxy"] = "http://127.0.0.1:1"   # Ignored
os.environ["https_proxy"] = "http://127.0.0.1:1"   # Ignored
os.environ["ALL_PROXY"] = "http://127.0.0.1:1"     # Ignored

with Session(impersonate="chrome144") as s:
    r = s.get("https://www.baidu.com")  # Direct connection works

# Explicit proxy still works
with Session(impersonate="chrome144", proxies={"https": "http://proxy:8080"}) as s:
    r = s.get("https://www.baidu.com")  # Goes through proxy
```

### Supported Platforms

| Platform | Status |
|----------|--------|
| Windows x64 | ✅ |
| Windows x86 | ✅ |
| Linux x64 | ✅ (CI auto-build) |
| macOS (Universal) | ✅ (CI auto-build) |

## License

MIT

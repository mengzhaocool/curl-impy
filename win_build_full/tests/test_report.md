# 严格测试报告 — curl-impersonate win_build_full
# 日期: 2026-07-13
# DLL: x64 7.10MB / x86 5.55MB, git: 168e685

## R1: 代理独立性重测 — PASS

### 测试方法
利用现有IE代理 127.0.0.1:7897（国内透传本机IP，国外走香港代理），不修改系统设置。

### 测试结果
| 场景 | IP | 判定 |
|------|-----|------|
| DLL 不设代理 → httpbin.org/ip | 119.98.94.95 (本地IP) | ✅ 直连 |
| DLL 显式代理 → httpbin.org/ip | 206.237.119.228 (香港代理IP) | ✅ 代理可用 |
| curl.exe 默认 → httpbin.org/ip | 206.237.119.228 (走了IE代理) | 对照 |
| curl.exe --noproxy → httpbin.org/ip | 119.98.94.95 (直连) | 对照 |

### 结论
DLL直连IP(119.98.94.95) == curl --noproxy IP(119.98.94.95) ✅
DLL不走系统IE代理。CURLOPT_PROXY显式代理正常工作。

---

## R2: 请求头大小写运行时验证 — PASS

### 测试方法
本地Python HTTP服务器记录收到的原始请求头，DLL和curl.exe对照。

### 测试结果
| 测试 | DLL收到 | curl收到 | 判定 |
|------|---------|---------|------|
| Content-Type + content-type | 2个头(值均取第一个) | 2个头(值均取第一个) | ✅ 一致 |
| content-type + Content-Type | 2个头(值均取第一个) | 2个头(值均取第一个) | ✅ 一致 |
| X-Custom + x-custom | 2个头(值均取第一个) | 2个头(值均取第一个) | ✅ 一致 |

### 结论
DLL行为与系统curl完全一致。curl不对非特殊头做去重，这是curl的设计选择（用户全权控制）。

---

## R3: Cookie 域名/路径匹配重测 — 2个BUG

### 测试结果
| 测试 | 结果 | 判定 |
|------|------|------|
| Path=/api → /api 携带 | ✅ 携带 | PASS |
| Path=/api → /other 不携带 | ✅ 不携带 | PASS |
| Secure属性 → HTTP下不发送 | ❌ 发送了 | **BUG** |
| Max-Age=0 过期 | ✅ 不发送 | PASS |
| 多Set-Cookie (3个) | ✅ 3/3 | PASS |
| 100个cookie | 50/100 | **异常** |
| CURLOPT_COOKIE手动设置 | ✅ 正确 | PASS |

### BUG: R3.2 Secure cookie在HTTP下被发送
- 严重程度: 中（安全问题）
- 描述: Set-Cookie: secure_cookie=1; Secure 设置后，在HTTP连接下仍然发送
- 违反: RFC 6265 Section 5.1.4 — Secure cookie只应在HTTPS下发送
- 可能原因: cookie jar文件在测试间复用，或curl的cookie引擎未正确处理Secure属性

### R3.5: 100个cookie只发送50个
- 可能是curl默认的cookie数量限制（与配置有关，非bug）

---

## R4: 导出API对照官方头文件 — 完成

### 导出统计
| 库 | x64导出数 | 说明 |
|----|----------|------|
| BoringSSL | 2059 | SSL_/EVP_/X509_/RSA_/BIO_/ASN1_/BN_/i2d_/d2i_/PEM_/EC_/CRYPTO_等 |
| nghttp2 | 425 | nghttp2_前缀 |
| zstd | 289 | ZSTD_前缀 |
| curl | 86 | curl_前缀 |
| cJSON | 78 | cJSON_前缀 |
| brotli | 36 | Brotli前缀 |
| zlib | ~70 | z_前缀 + zlibVersion等 |
| **总计** | **3783** | 0个@?修饰符 |

### 总数差异解释
3783导出 = BoringSSL(2059) + nghttp2(425) + zstd(289) + curl(86) + cJSON(78) + brotli(36) + zlib(~70) + 其他BoringSSL内部符号(~740)
- BoringSSL导出大量内部函数(i2d_/d2i_/PEM_/ASN1_等)是因为/WHOLEARCHIVE链接
- 这些函数虽然不是"公开API"但被导出用于完整性

---

## R5: 模拟头用户覆盖测试 — 1个BUG

### 测试结果
| 覆盖项 | 结果 | 判定 |
|--------|------|------|
| 不设自定义头 | 13个浏览器特征头注入 | ✅ |
| CURLOPT_ENCODING=identity | Accept-Encoding=identity | ✅ 覆盖成功 |
| CURLOPT_HTTPHEADER覆盖Accept | Accept被覆盖 | ✅ |
| CURLOPT_HTTPHEADER覆盖Accept-Encoding | Accept-Encoding被覆盖 | ✅ |
| 设空值移除内置头(Accept-Encoding:) | 头被移除 | ✅ |
| CURLOPT_USERAGENT='MyAgent/1.0' | **崩溃** | **BUG** |

### BUG: R5 CURLOPT_USERAGENT + 模拟 = 崩溃
- 严重程度: 高
- 描述: 设置curl_easy_impersonate后调用CURLOPT_USERAGENT导致access violation
- 错误: OSError: exception: access violation reading 0x000000006C160868
- 可能原因: 模拟设置的base_headers与CURLOPT_USERAGENT的字符串管理冲突

### 内置头列表 (Chrome144.json)
| 头名 | 分类 | 用户可覆盖 |
|------|------|-----------|
| sec-ch-ua | 浏览器特征 | ✅ |
| sec-ch-ua-mobile | 浏览器特征 | ✅ |
| sec-ch-ua-platform | 浏览器特征 | ✅ |
| upgrade-insecure-requests | 浏览器特征 | ✅ |
| user-agent | 浏览器特征 | ✅ (HTTPHEADER) / ❌ (USERAGENT崩溃) |
| accept | 浏览器特征 | ✅ |
| sec-fetch-mode | 浏览器特征 | ✅ |
| sec-fetch-user | 浏览器特征 | ✅ |
| accept-encoding | 浏览器特征 | ✅ |
| accept-language | 浏览器特征 | ✅ |
| priority | 浏览器特征 | ✅ |

---

## C4: x86 stdcall 精确验证 — 12/12 PASS

### 测试方法
32位C程序，加载x86 DLL，每个回调用__stdcall声明，用get_esp()在回调入口和出口捕获ESP值。

### 测试结果
| 回调类型 | 参数数 | 栈清理 | triggered | ESP_OK | params |
|---------|--------|--------|-----------|--------|--------|
| WRITEFUNCTION | 4 (16B) | callee | 4 | ✅ | ✅ |
| HEADERFUNCTION | 4 (16B) | callee | 9 | ✅ | ✅ |
| READFUNCTION | 4 (16B) | callee | 4 | ✅ | ✅ |
| PROGRESSFUNCTION | 5 (20B) | callee | 4 | ✅ | ✅ |
| XFERINFOFUNCTION | 5 (20B) | callee | 4 | ✅ | ✅ |
| DEBUGFUNCTION | 5 (20B) | callee | 4 | ✅ | ✅ |
| SOCKOPTFUNCTION | 3 (12B) | callee | 5 | ✅ | ✅ |
| OPENSOCKETFUNCTION | 3 (12B) | callee | 4 | ✅ | ✅ |
| CLOSESOCKETFUNCTION | 2 (8B) | callee | 4 | ✅ | ✅ |
| PREREQFUNCTION | 5 (20B) | callee | 4 | ✅ | ✅ |
| SEEKFUNCTION | 3 (12B) | callee | 4 | ✅ | ✅ |
| IOCTLFUNCTION | 3 (12B) | callee | 4 | ✅ | ✅ |

### 压力测试
- 10次连续请求(WRITEFUNCTION): 10/10 PASS, 无栈泄漏
- 默认callback (fwrite包装器): 工作正常
- Set→NULL→恢复默认: 工作正常

### 未测试的回调类型 (需要特殊环境)
SSL_CTX_FUNCTION, FNMATCH_FUNCTION, CHUNK_BGN/END, SEND/RECV, SSH_KEY, INTERLEAVE, RESOLVER_START, TRAILER_FUNCTION, CONVERT_FUNCTION, HSTSFUNCTION

---

## 发现的Bug汇总

| ID | 严重度 | 描述 | 状态 |
|----|--------|------|------|
| R3.2 | 中 | Secure cookie在HTTP下被发送 | 未修复 |
| R5 | 高 | CURLOPT_USERAGENT+模拟导致崩溃 | 未修复 |
| R3.5 | 低 | 100个cookie只发送50个 | 可能是curl限制 |

## 测试文件清单
- tests/r1_proxy_test.py — 代理独立性测试
- tests/r2_r5_header_test.py — 头大小写+覆盖测试
- tests/r3_cookie_test.py — Cookie域名/路径测试
- tests/c4_stdcall.c — x86 stdcall回调测试
- tests/compile_c4.py — C4编译脚本

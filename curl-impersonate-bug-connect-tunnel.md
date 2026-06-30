# curl-impersonate CONNECT 隧道 Bug 记录

## 发现日期
2026-06-29

## 问题描述

curl-impersonate（miniblink 使用的 HTTP 客户端库）在处理 HTTPS 代理 CONNECT 隧道时存在严重 bug：

1. **CONNECT 隧道处理异常**：当系统设置了 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量时，curl-impersonate 对 HTTPS 请求创建 CONNECT 隧道。但与标准 libcurl 不同，curl-impersonate 的 CONNECT 隧道处理存在以下问题：
   - `CURLINFO_RESPONSE_CODE` 返回 0（应为实际 HTTP 响应状态码）
   - `CURLOPT_HEADERFUNCTION` 回调不被调用（响应头丢失）
   - 响应通过 `CURLOPT_WRITEFUNCTION`（数据回调）路径传递

2. **`CURLOPT_PROXY=""` 无效**：设置 `CURLOPT_PROXY` 为空字符串无法禁用代理。curl-impersonate 仍然读取环境变量中的代理设置。

3. **`CURLOPT_NOPROXY="*"` 无效**：同样被忽略。

## 影响范围

- 所有 HTTPS 跨域 XHR 请求的 `status` 返回 0
- `getAllResponseHeaders()` 返回 NULL
- 导致 AliExpress 登录页 ET 安全模块（et_f.js）报 `oe.substr is not a function` 错误
- ET token 生成失败 → 服务端风控判定高风险 → 弹出滑动验证码

## 根因分析

### 为什么 DLL 内部无法修复

miniblink 的 DLL 使用 `/MT`（静态 CRT）编译。curl-impersonate 作为静态库链接进来，拥有自己独立的 CRT 实例和 `_environ`。

- `SetEnvironmentVariableA` — 只更新 Windows 进程环境块，不影响 curl-impersonate 的 `getenv()`
- `_putenv_s` — 只更新当前 CRT 的 `_environ`，不影响 curl-impersonate 的 `_environ`
- `CURLOPT_PROXY=""` — curl-impersonate 忽略此设置

curl-impersonate 的 `getenv("HTTP_PROXY")` 读取的是它自己 CRT 的 `_environ`，该 `_environ` 在 CRT 启动时从 Windows 进程环境块复制，之后不再同步。

### 正确的修复方式

**宿主 EXE 必须在调用 `wkeInitialize()` 之前清除代理环境变量：**

```c
// 在 wkeInitialize() 之前调用
SetEnvironmentVariableA("HTTP_PROXY", nullptr);
SetEnvironmentVariableA("HTTPS_PROXY", nullptr);
SetEnvironmentVariableA("ALL_PROXY", nullptr);
SetEnvironmentVariableA("http_proxy", nullptr);
SetEnvironmentVariableA("https_proxy", nullptr);
SetEnvironmentVariableA("all_proxy", nullptr);

wkeInitialize();
```

这样在 DLL 加载时，curl-impersonate 的 CRT 从已清空的进程环境块初始化 `_environ`，`getenv()` 返回空值。

### 验证结果

| 条件 | XHR status | getAllResponseHeaders | 页面渲染 |
|------|-----------|----------------------|---------|
| Clash 开启（env vars 设置） | 0 | NULL | 失败 |
| Clash 关闭（env vars 清空） | 200 | 正常返回 CORS 头 | 成功 |
| EXE 清除 env vars 后 wkeInitialize | 200 | 正常返回 CORS 头 | 成功 |
| DLL 内 _putenv_s 后 wkeInitialize | 0 | NULL | 失败 |
| DLL 内 SetEnvironmentVariableA | 0 | NULL | 失败 |
| DLL 内 CURLOPT_PROXY="" | 0 | NULL | 失败 |

## 后续修复方向

1. **重新编译 curl-impersonate**：从源码编译，在编译时禁用代理环境变量读取，或改用 `/MD`（动态 CRT）编译以共享 `_environ`
2. **Hook getenv()**：在 curl-impersonate 的 CRT 中 hook `getenv()` 函数，拦截 `HTTP_PROXY` 等查询
3. **修改 curl-impersonate 源码**：在 `create_conn()` 函数中跳过环境变量代理检测
4. **改用标准 libcurl**：标准 libcurl 不存在此 CONNECT 隧道处理 bug

## 相关文件

- `build/maindll/dllmain.cpp` — curl_global_init 调用位置
- `mbnet/WebURLLoaderManager.cpp` — curl_easy_init 和请求处理
- `mbvip/core/mb.cpp` — mbInit 初始化
- `mbvip/core/mb.h` — mbSetCorsCheckEnabled API 声明
- `content/browser/MbWebview.h` — m_corsCheckEnabled 成员

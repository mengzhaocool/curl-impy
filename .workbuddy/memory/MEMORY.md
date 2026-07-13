# curl-impersonate 项目记忆

## 项目结构
- `D:\curl-impersonate` — 主项目目录（当前从 Xweb5 复制）
- `D:\curl-impersonate-Xweb5` — Xweb5 参考项目（完好，未被修改）
- `D:\curl-impersonate-8.20.0` — 符号链接，指向 `D:\curl-impersonate-Xweb5\`

## 构建系统（关键！）
- **`_build_all.py`** 是真正的完整构建脚本：下载 → 打补丁(patches_new/) → 编译 → 验证 → 清理
- 构建流程纯patch驱动：apply patches → copy files → compile（0个py脚本改源码）
- win_build: 5个patch + 文件复制（cdecl回调）
- win_build_full: 6个patch + 文件复制（stdcall回调，额外curl-stdcall-callbacks.patch）
- patches_new/curl.patch 自包含所有修改（merge/slist.h/static/reset/slist_free_all）
- patches_new/curl-share-stdcall.patch: Curl_share_lock/unlock的__stdcall
- win_build_full/patches/curl-stdcall-callbacks.patch: 23个typedef+CRT包装器

## 补丁体系
- `patches_new/` 目录包含所有补丁：curl.patch, boringssl.patch, brotli.patch, nghttp2.patch, nghttp3.patch, ngtcp2.patch, zlib.patch, zstd.patch
- curl-disable-proxy-env.patch, curl-suppress-connect-headers.patch, fix-h2-header-value-case.patch
- curl-share-stdcall.patch (Curl_share_lock/unlock __stdcall)
- 源文件：cJSON.c/h, impersonate.c/h, impersonate_register.c/h, xweb5_config.h, libcurl-impersonate.def

## 依赖版本
- curl: 8.20.0
- BoringSSL: commit 673e61fc215b178a90c0e67858bbf162c8158993
- brotli: 1.2.0, nghttp2: 1.63.0, ngtcp2: 1.20.0, nghttp3: 1.15.0
- zlib: 1.3.1, zstd: 1.5.7, libssh2: 1.11.1

## Xweb5 构建方法（用户分享）
```powershell
Remove-Item "D:\curl-impersonate-Xweb5\build\curl-dll" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "D:\curl-impersonate-Xweb5\build\curl" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "D:\curl-impersonate-Xweb5\install\curl" -Recurse -Force -ErrorAction SilentlyContinue
# 然后运行 _step6_build.py（从已打补丁源码构建）
```

## 教训
- 2026-07-12: 我错误地用 git checkout 回退了 win_build/ 下被用户修改但未提交的 .bat 文件
- Xweb5 未被修改

## curl-impy项目
- GitHub: mengzhaocool/curl-impy
- 当前状态: ctypes绑定层(core.py) + 基础session.py
- 主要问题: 无cookie管理/无content-encoding/无异步/header解析不完整
- 改造方案: 保留core.py(含register_fingerprint特色), 替换session.py为curl-cffi的requests/
- 适配难点: CFFI→ctypes桥接(ffi.new/ffi.new_handle/ffi.from_handle/@ffi.def_extern)
- curl-cffi用CFFI+_wrapper.pyd(静态链接curl), 我们用ctypes+独立DLL

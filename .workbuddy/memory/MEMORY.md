# curl-impersonate 项目记忆

## 项目结构
- `D:\curl-impersonate` — 主项目目录（当前从 Xweb5 复制）
- `D:\curl-impersonate-Xweb5` — Xweb5 参考项目（完好，未被修改）
- `D:\curl-impersonate-8.20.0` — 符号链接，指向 `D:\curl-impersonate-Xweb5\`

## 构建系统（关键！）
- **`_build_all.py`** 是真正的完整构建脚本：下载 → 打补丁(patches_new/) → 编译 → 验证 → 清理
- **`_step6_build.py`** 是从已打补丁源码构建的脚本（不下载，不重新打补丁）
- **`.bat` 文件**（build_all.bat, build_curl_dll.bat 等）是另一套构建系统，与 _build_all.py 不同
- 今天早上成功构建用的是 `_step6_build.py`，不是 .bat 文件
- **不要用 .bat 文件构建！用 _build_all.py 或 _step6_build.py**

## 补丁体系
- `patches_new/` 目录包含所有补丁：curl.patch, boringssl.patch, brotli.patch, nghttp2.patch, nghttp3.patch, ngtcp2.patch, zlib.patch, zstd.patch
- 还有源文件：cJSON.c/h, impersonate.c/h, impersonate_register.c/h, xweb5_config.h, libcurl-impersonate.def
- `_build_all.py` 的 `apply_all_patches()` 函数从 patches_new/ 应用所有补丁
- `apply_patch()` 函数用 git apply 应用补丁（先 git init + commit baseline）

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
- 2026-07-12: 我错误地用 git checkout 回退了 win_build/ 下被用户修改但未提交的 .bat 文件，导致 ZSTD 变量、NASM fallback 等丢失。然后又用 .bat 文件构建（应该用 _build_all.py）。最终 rm -rf 了 D:\curl-impersonate 的原始内容。
- Xweb5 未被修改（时间戳确认所有改动都是今天早上 04:58 之前的 AI 会话所为）

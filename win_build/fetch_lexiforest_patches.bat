@echo off
::: fetch_lexiforest_patches.bat - Download lexiforest/curl-impersonate patches
::: These patches are based on curl 8.15.0 and need adaptation for curl 8.20.0
setlocal enabledelayedexpansion

call "%~dp0config.bat"

set "PATCH_DIR=%WIN_BUILD_ROOT%\lexiforest_patches"
if not exist "%PATCH_DIR%" mkdir "%PATCH_DIR%"

set "BASE_URL=https://ghfast.top/https://raw.githubusercontent.com/lexiforest/curl-impersonate/refs/heads/main/patches"

echo [patches] Downloading lexiforest patches...

::: curl.patch (main impersonation patch - based on curl 8.15.0)
if not exist "%PATCH_DIR%\curl.patch" (
    echo [patches] Downloading curl.patch...
    curl -L --retry 3 -o "%PATCH_DIR%\curl.patch" "%BASE_URL%/curl.patch"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] curl.patch download failed & exit /b 1 )
)

::: boringssl.patch (BoringSSL modifications for TLS fingerprinting)
if not exist "%PATCH_DIR%\boringssl.patch" (
    echo [patches] Downloading boringssl.patch...
    curl -L --retry 3 -o "%PATCH_DIR%\boringssl.patch" "%BASE_URL%/boringssl.patch"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] boringssl.patch download failed & exit /b 1 )
)

::: ngtcp2.patch (QUIC transport params raw API)
if not exist "%PATCH_DIR%\ngtcp2.patch" (
    echo [patches] Downloading ngtcp2.patch...
    curl -L --retry 3 -o "%PATCH_DIR%\ngtcp2.patch" "%BASE_URL%/ngtcp2.patch"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] ngtcp2.patch download failed & exit /b 1 )
)

::: nghttp3.patch (HTTP/3 settings submission API)
if not exist "%PATCH_DIR%\nghttp3.patch" (
    echo [patches] Downloading nghttp3.patch...
    curl -L --retry 3 -o "%PATCH_DIR%\nghttp3.patch" "%BASE_URL%/nghttp3.patch"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp3.patch download failed & exit /b 1 )
)

::: brotli.patch (minor LoongArch64 fix)
if not exist "%PATCH_DIR%\brotli.patch" (
    echo [patches] Downloading brotli.patch...
    curl -L --retry 3 -o "%PATCH_DIR%\brotli.patch" "%BASE_URL%/brotli.patch"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] brotli.patch download failed & exit /b 1 )
)

echo [patches] All lexiforest patches downloaded to: %PATCH_DIR%
dir /b "%PATCH_DIR%\*.patch"

endlocal
exit /b 0

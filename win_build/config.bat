@echo off
::: config.bat - Build configuration for curl-impersonate Windows build
::: Centralizes all version numbers, download URLs, and path constants
::: Synced with lexiforest/curl-impersonate main branch CMakeLists.txt
::: curl upgraded to 8.20.0 (above lexiforest's 8.15.0)

::: ==============================================================================
::: Version Numbers (synced with lexiforest + curl 8.20.0)
::: ==============================================================================
::: NOTE: nghttp2 MUST be <=1.63.0 — 1.64+ removed the priority flag
:::       See: https://nghttp2.org/blog/2025/03/02/nghttp2-v1-65-0/
::: NOTE: ngtcp2 MUST be 1.20.0 — lexiforest ngtcp2.patch modifies core files
:::       (ngtcp2_conn.c, ngtcp2.h) and won't apply cleanly to newer versions
::: NOTE: nghttp3 MUST be 1.15.0 — lexiforest nghttp3.patch modifies core files
:::       (nghttp3_conn.c, nghttp3.h) and won't apply cleanly to newer versions

set CURL_VERSION=8.20.0
set CURL_VERSION_DIR=curl-8.20.0
set BROTLI_VERSION=1.2.0
set NGHTTP2_VERSION=1.63.0
set NGHTTP2_VERSION_DIR=nghttp2-%NGHTTP2_VERSION%
set NGTCP2_VERSION=1.20.0
set NGTCP2_VERSION_DIR=ngtcp2-%NGTCP2_VERSION%
set NGHTTP3_VERSION=1.15.0
set NGHTTP3_VERSION_DIR=nghttp3-%NGHTTP3_VERSION%
set BORINGSSL_COMMIT=673e61fc215b178a90c0e67858bbf162c8158993
set ZLIB_VERSION=1.3.1
set ZSTD_VERSION=1.5.7

::: ==============================================================================
::: Download URLs (use ghfast.top mirror for GitHub to bypass DNS issues)
::: ==============================================================================
set CURL_URL=https://curl.se/download/curl-%CURL_VERSION%.tar.xz
set BROTLI_URL=https://ghfast.top/https://github.com/google/brotli/archive/refs/tags/v%BROTLI_VERSION%.tar.gz
set NGHTTP2_URL=https://ghfast.top/https://github.com/nghttp2/nghttp2/releases/download/v%NGHTTP2_VERSION%/nghttp2-%NGHTTP2_VERSION%.tar.bz2
set NGTCP2_URL=https://ghfast.top/https://github.com/ngtcp2/ngtcp2/releases/download/v%NGTCP2_VERSION%/ngtcp2-%NGTCP2_VERSION%.tar.bz2
set NGHTTP3_URL=https://ghfast.top/https://github.com/ngtcp2/nghttp3/releases/download/v%NGHTTP3_VERSION%/nghttp3-%NGHTTP3_VERSION%.tar.bz2
set BORINGSSL_URL=https://ghfast.top/https://github.com/google/boringssl/archive/%BORINGSSL_COMMIT%.zip
set ZLIB_URL=https://ghfast.top/https://github.com/madler/zlib/archive/refs/tags/v%ZLIB_VERSION%.tar.gz
set ZSTD_URL=https://ghfast.top/https://github.com/facebook/zstd/releases/download/v%ZSTD_VERSION%/zstd-%ZSTD_VERSION%.tar.gz

::: ==============================================================================
::: Architecture and CRT Configuration
::: ==============================================================================
if not defined ARCH set ARCH=x64
if not defined CRT set CRT=MT
if not defined VS_VERSION set VS_VERSION=2022
if not defined BUILD_TYPE set BUILD_TYPE=Release

::: ==============================================================================
::: Path Configuration
::: ==============================================================================
set WIN_BUILD_ROOT=%~dp0
::: Remove trailing backslash
if "%WIN_BUILD_ROOT:~-1%"=="\" set WIN_BUILD_ROOT=%WIN_BUILD_ROOT:~0,-1%

set DEPS_DIR=%WIN_BUILD_ROOT%\deps
set PATCHES_DIR=%WIN_BUILD_ROOT%\patches
set LEXIFOREST_PATCHES_DIR=%WIN_BUILD_ROOT%\lexiforest_patches
set SRC_PATCHES_DIR=%WIN_BUILD_ROOT%\..\chrome\patches

::: Architecture-specific directories
::: x64 uses the default paths (backward compatible)
::: x86 uses subdirectories to avoid conflicts
if "%ARCH%"=="x86" (
    set BUILD_DIR=%WIN_BUILD_ROOT%\build_x86
    set INSTALL_DIR=%WIN_BUILD_ROOT%\install_x86
    set OUTPUT_DIR=%WIN_BUILD_ROOT%\output_x86
) else (
    set BUILD_DIR=%WIN_BUILD_ROOT%\build
    set INSTALL_DIR=%WIN_BUILD_ROOT%\install
    set OUTPUT_DIR=%WIN_BUILD_ROOT%\output
)

::: Install subdirectories for each dependency
set ZLIB_INSTALL_DIR=%INSTALL_DIR%\zlib
set BROTLI_INSTALL_DIR=%INSTALL_DIR%\brotli
set NGHTTP2_INSTALL_DIR=%INSTALL_DIR%\nghttp2
set NGTCP2_INSTALL_DIR=%INSTALL_DIR%\ngtcp2
set NGHTTP3_INSTALL_DIR=%INSTALL_DIR%\nghttp3
set BORINGSSL_INSTALL_DIR=%INSTALL_DIR%\boringssl
set ZSTD_INSTALL_DIR=%INSTALL_DIR%\zstd
set CURL_INSTALL_DIR=%INSTALL_DIR%\curl

::: Source directories under deps/
set ZLIB_SRC_DIR=%DEPS_DIR%\zlib-%ZLIB_VERSION%
set BROTLI_SRC_DIR=%DEPS_DIR%\brotli-%BROTLI_VERSION%
set NGHTTP2_SRC_DIR=%DEPS_DIR%\%NGHTTP2_VERSION_DIR%
set NGTCP2_SRC_DIR=%DEPS_DIR%\%NGTCP2_VERSION_DIR%
set NGHTTP3_SRC_DIR=%DEPS_DIR%\%NGHTTP3_VERSION_DIR%
set BORINGSSL_SRC_DIR=%DEPS_DIR%\boringssl
set ZSTD_SRC_DIR=%DEPS_DIR%\zstd-%ZSTD_VERSION%
set CURL_SRC_DIR=%DEPS_DIR%\%CURL_VERSION_DIR%

::: Build directories under build/
set ZLIB_BUILD_DIR=%BUILD_DIR%\zlib
set BROTLI_BUILD_DIR=%BUILD_DIR%\brotli
set NGHTTP2_BUILD_DIR=%BUILD_DIR%\nghttp2
set NGTCP2_BUILD_DIR=%BUILD_DIR%\ngtcp2
set NGHTTP3_BUILD_DIR=%BUILD_DIR%\nghttp3
set BORINGSSL_BUILD_DIR=%BUILD_DIR%\boringssl
set ZSTD_BUILD_DIR=%BUILD_DIR%\zstd
set CURL_BUILD_DIR=%BUILD_DIR%\curl

::: ==============================================================================
::: Tool overrides (use Windows native tar to avoid MSYS2 path issues)
::: ==============================================================================
set TAR=C:\Windows\System32\tar.exe

::: ==============================================================================
::: Build Findings File
::: ==============================================================================
set BUILD_FINDINGS=%WIN_BUILD_ROOT%\build_findings.md

::: ==============================================================================
::: CRT Flags for MSVC static linking
::: ==============================================================================
if "%CRT%"=="MT" (
    set CRT_C_FLAGS=/MT /O2 /DNDEBUG
    set CRT_CXX_FLAGS=/MT /O2 /DNDEBUG
    set CRT_CMAKE_C_FLAGS=/MT /O2 /DNDEBUG
    set CRT_CMAKE_CXX_FLAGS=/MT /O2 /DNDEBUG
) else if "%CRT%"=="MTd" (
    set CRT_C_FLAGS=/MTd /Zi /D_DEBUG
    set CRT_CXX_FLAGS=/MTd /Zi /D_DEBUG
    set CRT_CMAKE_C_FLAGS=/MTd /Zi /D_DEBUG
    set CRT_CMAKE_CXX_FLAGS=/MTd /Zi /D_DEBUG
) else if "%CRT%"=="MD" (
    set CRT_C_FLAGS=/MD /O2 /DNDEBUG
    set CRT_CXX_FLAGS=/MD /O2 /DNDEBUG
    set CRT_CMAKE_C_FLAGS=/MD /O2 /DNDEBUG
    set CRT_CMAKE_CXX_FLAGS=/MD /O2 /DNDEBUG
) else if "%CRT%"=="MDd" (
    set CRT_C_FLAGS=/MDd /Zi /D_DEBUG
    set CRT_CXX_FLAGS=/MDd /Zi /D_DEBUG
    set CRT_CMAKE_C_FLAGS=/MDd /Zi /D_DEBUG
    set CRT_CMAKE_CXX_FLAGS=/MDd /Zi /D_DEBUG
) else (
    echo [ERROR] Invalid CRT type: %CRT%. Must be MT, MTd, MD, or MDd.
    exit /b 1
)

::: ==============================================================================
::: System DLL whitelist (for dependency verification)
::: ==============================================================================
set SYSTEM_DLLS=kernel32.dll ntdll.dll ws2_32.dll advapi32.dll crypt32.dll secur32.dll user32.dll gdi32.dll shell32.dll shlwapi.dll ole32.dll oleaut32.dll uuid.dll msvcrt.dll bcrypt.dll ncrypt.dll imm32.dll comdlg32.dll version.dll winmm.dll wsock32.dll wldap32.dll normaliz.dll iphlpapi.dll

goto :eof

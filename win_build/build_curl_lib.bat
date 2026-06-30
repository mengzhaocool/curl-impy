@echo off
::: build_curl_lib.bat - Build curl-impersonate as static library
::: Uses lexiforest curl.patch (options 999-1030, 35+ browser presets)
::: All browsers (Chrome/Firefox/Safari/Tor/OkHttp) in single library
::: Supports HTTP/2 and HTTP/3 (QUIC) fingerprinting
setlocal enabledelayedexpansion

echo ========================================
echo [8/10] Building curl-impersonate static lib
echo ========================================

::: ============================================
::: Step 1: Download curl source
::: ============================================
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\curl-%CURL_VERSION%.tar.xz"
if not exist "%ARCHIVE%" (
    echo [curl-lib] Downloading curl %CURL_VERSION%...
    python -c "import urllib.request; urllib.request.urlretrieve(r'%CURL_URL%', r'%ARCHIVE%')"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] curl download failed & exit /b 1 )
)

::: ============================================
::: Step 2: Extract (always clean to ensure patch applies cleanly)
::: ============================================
if exist "%CURL_SRC_DIR%" (
    echo [curl-lib] Removing old source directory...
    rmdir /s /q "%CURL_SRC_DIR%"
)
echo [curl-lib] Extracting...
python -c "import tarfile,shutil,os; d=r'%DEPS_DIR%'; t=tarfile.open(r'%ARCHIVE%','r:xz'); tmp=d+'\\\\_curl_extract_tmp'; os.makedirs(tmp,exist_ok=True); t.extractall(tmp); t.close(); src=os.path.join(tmp,'%CURL_VERSION_DIR%'); dst=r'%CURL_SRC_DIR%'; shutil.move(src,dst); shutil.rmtree(tmp,ignore_errors=True)"
if %ERRORLEVEL% neq 0 ( echo [ERROR] curl extract failed & exit /b 1 )

::: ============================================
::: Step 3: Apply patches
::: ============================================
pushd "%CURL_SRC_DIR%"
echo [curl-lib] Initializing git repo for patch application...
if exist ".git" rmdir /s /q ".git"
"%GIT_EXE%" init
"%GIT_EXE%" config user.email "build@local"
"%GIT_EXE%" config user.name "Build"
"%GIT_EXE%" add -A
"%GIT_EXE%" commit -q -m "curl %CURL_VERSION% original" --allow-empty

::: Patch 1: lexiforest curl.patch (main impersonation patch)
::: Based on curl 8.15.0, applies with fuzz to 8.20.0
::: Adds: impersonate.c/h (35+ presets), CURLOPT 999-1030,
::: HTTP/2 settings/priority, header ordering, split cookies,
::: webkit/firefox form boundary, QUIC SOCKS5 support
set "PATCH1=%LEXIFOREST_PATCHES_DIR%\curl.patch"
echo [curl-lib] Applying lexiforest curl.patch...
"%GIT_EXE%" apply --check "%PATCH1%" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARN] git apply --check failed, trying --3way...
    "%GIT_EXE%" apply --3way "%PATCH1%" 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] curl.patch failed to apply
        popd
        exit /b 1
    )
) else (
    "%GIT_EXE%" apply "%PATCH1%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] git apply failed for curl.patch
        popd
        exit /b 1
    )
)
echo [curl-lib] echo [curl-lib] curl.patch applied.

::: Patch 1a: Disable proxy environment variable reading (fixes CONNECT tunnel bug)
set "PATCH1A=%PATCHES_DIR%\curl-disable-proxy-env.patch"
if exist "%PATCH1A%" (
    echo [curl-lib] Applying curl-disable-proxy-env.patch...
    "%GIT_EXE%" apply --check "%PATCH1A%" 2>nul
    if %ERRORLEVEL% neq 0 (
        "%GIT_EXE%" apply --3way "%PATCH1A%" 2>nul
    ) else (
        "%GIT_EXE%" apply "%PATCH1A%"
    )
    if %ERRORLEVEL% neq 0 (
        echo [WARN] curl-disable-proxy-env.patch failed, may already be applied
    ) else (
        echo [curl-lib] curl-disable-proxy-env.patch applied.
    )
)

::: Patch 1b: Copy cJSON and impersonate_register source files
echo [curl-lib] Copying cJSON and impersonate_register source files...
copy /Y "%PATCHES_DIR%\cJSON.h" "%CURL_SRC_DIR%\lib\cJSON.h" >nul 2>&1
copy /Y "%PATCHES_DIR%\cJSON.c" "%CURL_SRC_DIR%\lib\cJSON.c" >nul 2>&1
copy /Y "%PATCHES_DIR%\impersonate_register.h" "%CURL_SRC_DIR%\lib\impersonate_register.h" >nul 2>&1
copy /Y "%PATCHES_DIR%\impersonate_register.c" "%CURL_SRC_DIR%\lib\impersonate_register.c" >nul 2>&1
echo [curl-lib] Source files copied.

::: Patch 1c: Add cJSON and impersonate_register to Makefile.inc
echo [curl-lib] Adding cJSON and impersonate_register to Makefile.inc...
python -c "p=r'%CURL_SRC_DIR%\lib\Makefile.inc';c=open(p,'r',encoding='utf-8').read();c=c.replace(' impersonate.c',' impersonate.c impersonate_register.c cJSON.c');c=c.replace(' impersonate.h',' impersonate.h impersonate_register.h cJSON.h');open(p,'w',encoding='utf-8').write(c)"
echo [curl-lib] Makefile.inc updated.

::: Patch 1d: Apply custom impersonate_register patches to curl source files
echo [curl-lib] Applying custom impersonate_register patches...
python "%PATCHES_DIR%\apply_custom_impersonate.py" "%CURL_SRC_DIR%"
if %ERRORLEVEL% neq 0 (
    echo [WARN] Custom impersonate patches had warnings
) else (
    echo [curl-lib] Custom impersonate patches applied.
)

::: Patch 2: CMake Windows adaptation (output name change) CMake Windows adaptation (output name change)
set "PATCH2=%PATCHES_DIR%\curl-cmake-windows.patch"
if exist "%PATCH2%" (
    echo [curl-lib] Applying curl-cmake-windows.patch...
    "%GIT_EXE%" apply --check "%PATCH2%" 2>nul
    if %ERRORLEVEL% neq 0 (
        "%GIT_EXE%" apply --3way "%PATCH2%" 2>nul
    ) else (
        "%GIT_EXE%" apply "%PATCH2%"
    )
    if %ERRORLEVEL% neq 0 (
        echo [WARN] CMake Windows patch failed, will fix output name manually
    ) else (
        echo [curl-lib] CMake Windows patch applied.
    )
)

::: Ensure output name is set correctly (lexiforest: single multi-browser binary)
echo [curl-lib] Ensuring output name is libcurl-impersonate...
python -c "p=r'%CURL_SRC_DIR%\lib\CMakeLists.txt';c=open(p,'r',encoding='utf-8').read();c=c.replace('set(LIBCURL_OUTPUT_NAME libcurl CACHE','set(LIBCURL_OUTPUT_NAME libcurl-impersonate CACHE');open(p,'w',encoding='utf-8').write(c)"
python -c "p=r'%CURL_SRC_DIR%\src\CMakeLists.txt';c=open(p,'r',encoding='utf-8').read();c=c.replace('set(EXE_NAME curl)','set(EXE_NAME curl-impersonate)');open(p,'w',encoding='utf-8').write(c)"

::: Patch 3: Fix BoringSSL detection
set "PATCH3=%PATCHES_DIR%\fix-boringssl-detection.patch"
if exist "%PATCH3%" (
    echo [curl-lib] Applying fix-boringssl-detection.patch...
    "%GIT_EXE%" apply --check "%PATCH3%" 2>nul
    if %ERRORLEVEL% neq 0 (
        "%GIT_EXE%" apply --3way "%PATCH3%" 2>nul
    ) else (
        "%GIT_EXE%" apply "%PATCH3%"
    )
    if %ERRORLEVEL% neq 0 (
        echo [WARN] BoringSSL detection fix patch failed, may already be applied
    ) else (
        echo [curl-lib] BoringSSL detection fix patch applied.
    )
)

::: Patch 4: Fix VLA for MSVC
set "PATCH4=%PATCHES_DIR%\fix-vla-msvc.patch"
if exist "%PATCH4%" (
    echo [curl-lib] Applying fix-vla-msvc.patch...
    "%GIT_EXE%" apply --check "%PATCH4%" 2>nul
    if %ERRORLEVEL% neq 0 (
        "%GIT_EXE%" apply --3way "%PATCH4%" 2>nul
    ) else (
        "%GIT_EXE%" apply "%PATCH4%"
    )
    if %ERRORLEVEL% neq 0 (
        echo [WARN] VLA fix patch failed, may already be applied
    ) else (
        echo [curl-lib] VLA fix patch applied.
    )
)

popd

::: ============================================
::: Step 4: Fix VLA issue for MSVC
::: ============================================
echo [curl-lib] Fixing VLA issue for MSVC...
cd /d "%CURL_SRC_DIR%"
python "%WIN_BUILD_ROOT%\fix_vla.py"
cd /d "%WIN_BUILD_ROOT%"
if %ERRORLEVEL% neq 0 (
    echo [WARN] Failed to fix VLA issue
) else (
    echo [curl-lib] VLA fix applied.
)

::: ============================================
::: Step 5: Fix BoringSSL detection in CMakeLists.txt
::: ============================================
echo [curl-lib] Fixing BoringSSL detection in CMakeLists.txt...
set "CMAKELISTS=%CURL_SRC_DIR%\lib\CMakeLists.txt"
if exist "%CMAKELISTS%" (
    python "%WIN_BUILD_ROOT%\patch_boringssl_def.py" "%CMAKELISTS%"
    if %ERRORLEVEL% neq 0 (
        echo [WARN] Failed to patch CMakeLists.txt for BoringSSL
    ) else (
        echo [curl-lib] BoringSSL detection fix applied.
    )
)

::: ============================================
::: Step 6: Patch CMakeLists.txt for /WHOLEARCHIVE
::: ============================================
echo [curl-lib] Patching CMakeLists.txt for DLL export compatibility...
set "CMAKELISTS=%CURL_SRC_DIR%\lib\CMakeLists.txt"
if exist "%CMAKELISTS%" (
    python "%WIN_BUILD_ROOT%\patch_cmake_dll.py" "%CMAKELISTS%"
    if %ERRORLEVEL% neq 0 (
        echo [WARN] CMakeLists.txt patch failed
    ) else (
        echo [curl-lib] CMakeLists.txt patched.
    )
)

::: ============================================
::: Step 7: CMake configure for static lib build
::: ============================================
echo [curl-lib] CMake configure (static lib)...
if not exist "%CURL_BUILD_DIR%" mkdir "%CURL_BUILD_DIR%"
if not exist "%CURL_INSTALL_DIR%" mkdir "%CURL_INSTALL_DIR%"

::: Determine CRT runtime library flag for CMake
if "%CRT%"=="MT" (
    set "CMAKE_CRT=MultiThreaded"
) else if "%CRT%"=="MTd" (
    set "CMAKE_CRT=MultiThreadedDebug"
) else if "%CRT%"=="MD" (
    set "CMAKE_CRT=MultiThreadedDLL"
) else if "%CRT%"=="MDd" (
    set "CMAKE_CRT=MultiThreadedDebugDLL"
) else (
    set "CMAKE_CRT=MultiThreaded"
)

"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%CURL_INSTALL_DIR%" ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_CXX_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=%CMAKE_CRT% ^
    -DCMAKE_C_FLAGS="%CRT_C_FLAGS% /DNGHTTP2_STATICLIB /DCURL_STATICLIB" ^
    -DCMAKE_CXX_FLAGS="%CRT_CXX_FLAGS% /DNGHTTP2_STATICLIB /DCURL_STATICLIB" ^
    -DCMAKE_C_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_CXX_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_C_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DCMAKE_CXX_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DBUILD_SHARED_LIBS=OFF ^
    -DBUILD_STATIC_LIBS=ON ^
    -DCURL_USE_OPENSSL=ON ^
    -DHAVE_BORINGSSL=ON ^
    -DOPENSSL_ROOT_DIR="%BORINGSSL_INSTALL_DIR%" ^
    -DOPENSSL_INCLUDE_DIR="%BORINGSSL_INSTALL_DIR%\include" ^
    -DOPENSSL_LIBRARIES="%BORINGSSL_INSTALL_DIR%\lib\libssl.lib;%BORINGSSL_INSTALL_DIR%\lib\libcrypto.lib" ^
    -DCURL_BROTLI=ON ^
    -DBROTLI_INCLUDE_DIR="%BROTLI_INSTALL_DIR%\include" ^
    -DBROTLI_LIBRARY="%BROTLI_INSTALL_DIR%\lib\brotlidec-static.lib" ^
    -DBROTLIDEC_LIBRARY="%BROTLI_INSTALL_DIR%\lib\brotlidec-static.lib" ^
    -DBROTLIENC_LIBRARY="%BROTLI_INSTALL_DIR%\lib\brotlienc-static.lib" ^
    -DBROTLI_ENCODER_LIBRARY="%BROTLI_INSTALL_DIR%\lib\brotlienc-static.lib" ^
    -DBROTLI_COMMON_LIBRARY="%BROTLI_INSTALL_DIR%\lib\brotlicommon-static.lib" ^
    -DBROTLICOMMON_LIBRARY="%BROTLI_INSTALL_DIR%\lib\brotlicommon-static.lib" ^
    -DUSE_NGHTTP2=ON ^
    -DNGHTTP2_INCLUDE_DIR="%NGHTTP2_INSTALL_DIR%\include" ^
    -DNGHTTP2_LIBRARY="%NGHTTP2_INSTALL_DIR%\lib\nghttp2.lib" ^
    -DNGHTTP2_ROOT="%NGHTTP2_INSTALL_DIR%" ^
    -DUSE_NGTCP2=ON ^
    -DNGTCP2_INCLUDE_DIR="%NGTCP2_INSTALL_DIR%\include" ^
    -DNGTCP2_LIBRARY="%NGTCP2_INSTALL_DIR%\lib\ngtcp2.lib" ^
    -DNGTCP2_CRYPTO_LIBRARY="%NGTCP2_INSTALL_DIR%\lib\ngtcp2_crypto_boringssl.lib" ^
    -DUSE_NGHTTP3=ON ^
    -DNGHTTP3_INCLUDE_DIR="%NGHTTP3_INSTALL_DIR%\include" ^
    -DNGHTTP3_LIBRARY="%NGHTTP3_INSTALL_DIR%\lib\nghttp3.lib" ^
    -DZLIB_INCLUDE_DIR="%ZLIB_INSTALL_DIR%\include" ^
    -DZLIB_LIBRARY="%ZLIB_INSTALL_DIR%\lib\zlibstatic.lib" ^
    -DZLIB_ROOT="%ZLIB_INSTALL_DIR%" ^
    -DCURL_ZSTD=ON ^
    -DZSTD_INCLUDE_DIR="%ZSTD_INSTALL_DIR%\include" ^
    -DZSTD_LIBRARY="%ZSTD_INSTALL_DIR%\lib\zstd_static.lib" ^
    -DZSTD_ROOT="%ZSTD_INSTALL_DIR%" ^
    -DHTTP_ONLY=OFF ^
    -DENABLE_WEBSOCKETS=ON ^
    -DUSE_LIBIDN2=OFF ^
    -DUSE_LIBPSL=OFF ^
    -DUSE_QUICHE=OFF ^
    -DENABLE_MANUAL=OFF ^
    -DCURL_USE_LIBSSH2=OFF ^
    -DCURL_USE_GSSAPI=OFF ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -S "%CURL_SRC_DIR%" ^
    -B "%CURL_BUILD_DIR%"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] curl static lib CMake configure failed
    exit /b 1
)

::: ============================================
::: Step 8: Build
::: ============================================
echo [curl-lib] Building static lib...
"%CMAKE_EXE%" --build "%CURL_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 (
    echo [ERROR] curl static lib build failed
    exit /b 1
)

::: ============================================
::: Step 9: Verify static lib was built
::: ============================================
set "CURL_STATIC_LIB="
for %%f in (
    "%CURL_BUILD_DIR%\lib\libcurl-impersonate.lib"
    "%CURL_BUILD_DIR%\lib\Release\libcurl-impersonate.lib"
) do (
    if exist "%%f" set "CURL_STATIC_LIB=%%f"
)
if not defined CURL_STATIC_LIB (
    echo [curl-lib] Searching for static lib...
    for /f "tokens=*" %%f in ('dir /s /b "%CURL_BUILD_DIR%\*libcurl-impersonate*.lib" 2^>nul') do (
        set "CURL_STATIC_LIB=%%f"
    )
)
if not defined CURL_STATIC_LIB (
    echo [ERROR] libcurl-impersonate.lib not found after build
    dir /s /b "%CURL_BUILD_DIR%\*.lib" 2>nul
    exit /b 1
)

echo [curl-lib] Static lib built: %CURL_STATIC_LIB%

::: ============================================
::: Step 10: Install
::: ============================================
echo [curl-lib] Installing...
"%CMAKE_EXE%" --install "%CURL_BUILD_DIR%" --config %BUILD_TYPE%

::: ============================================
::: Step 11: Merge static lib with all dependencies
::: Use lib.exe to combine curl + BoringSSL + zlib + brotli + nghttp2 + ngtcp2 + nghttp3
::: into a single merged static library that exports all symbols
::: ============================================
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo [curl-lib] Merging static lib with all dependencies...
set "MERGED_LIB=%OUTPUT_DIR%\libcurl-impersonate.lib"
set "MERGED_TMPDIR=%BUILD_DIR%\merge_tmp"
if exist "%MERGED_TMPDIR%" rmdir /s /q "%MERGED_TMPDIR%"
mkdir "%MERGED_TMPDIR%"

::: Merge all static libs into one
lib.exe /OUT:"%MERGED_LIB%" ^
    "%CURL_STATIC_LIB%" ^
    "%BORINGSSL_INSTALL_DIR%\lib\libssl.lib" ^
    "%BORINGSSL_INSTALL_DIR%\lib\libcrypto.lib" ^
    "%ZLIB_INSTALL_DIR%\lib\zlibstatic.lib" ^
    "%BROTLI_INSTALL_DIR%\lib\brotlidec-static.lib" ^
    "%BROTLI_INSTALL_DIR%\lib\brotlienc-static.lib" ^
    "%BROTLI_INSTALL_DIR%\lib\brotlicommon-static.lib" ^
    "%NGHTTP2_INSTALL_DIR%\lib\nghttp2.lib" ^
    "%NGTCP2_INSTALL_DIR%\lib\ngtcp2.lib" ^
    "%NGTCP2_INSTALL_DIR%\lib\ngtcp2_crypto_boringssl.lib" ^
    "%NGHTTP3_INSTALL_DIR%\lib\nghttp3.lib" ^
    "%ZSTD_INSTALL_DIR%\lib\zstd_static.lib"

if %ERRORLEVEL% neq 0 (
    echo [WARN] lib.exe merge failed, falling back to simple copy
    copy /y "%CURL_STATIC_LIB%" "%MERGED_LIB%" >nul
) else (
    echo [curl-lib] Merged static lib created.
)

::: Clean up
if exist "%MERGED_TMPDIR%" rmdir /s /q "%MERGED_TMPDIR%"

::: Copy headers
if not exist "%OUTPUT_DIR%\include" mkdir "%OUTPUT_DIR%\include"
if exist "%CURL_INSTALL_DIR%\include\curl" (
    xcopy /E /I /Y /Q "%CURL_INSTALL_DIR%\include\curl" "%OUTPUT_DIR%\include\curl" >nul 2>&1
)

echo [curl-lib] Build complete.

:endlocal
exit /b 0

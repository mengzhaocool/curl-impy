@echo off
::: build_boringssl.bat - Build BoringSSL as static library
::: Applies lexiforest boringssl.patch (TLS fingerprinting extensions)
::: Patch adds: new ciphers, DHE key exchange, extension order API,
::: key shares limit, delegated credentials, Windows RNG fallback
setlocal enabledelayedexpansion

echo ========================================
echo [6/10] Building BoringSSL (%BORINGSSL_COMMIT:~0,12%...)
echo ========================================

::: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\boringssl-%BORINGSSL_COMMIT%.zip"
if not exist "%ARCHIVE%" (
    echo [boringssl] Downloading BoringSSL...
    curl -L --retry 3 --retry-delay 5 -o "%ARCHIVE%" "%BORINGSSL_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] BoringSSL download failed & exit /b 1 )
)

::: Extract
if not exist "%BORINGSSL_SRC_DIR%" (
    echo [boringssl] Extracting...
    powershell -NoProfile -Command "Expand-Archive -Path '%ARCHIVE%' -DestinationPath '%DEPS_DIR%' -Force"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] BoringSSL extract failed & exit /b 1 )
    :: Rename from boringssl-<commit> to boringssl
    if exist "%DEPS_DIR%\boringssl-%BORINGSSL_COMMIT%" (
        ren "%DEPS_DIR%\boringssl-%BORINGSSL_COMMIT%" "boringssl"
    )
)

::: Apply lexiforest boringssl.patch
set "BORINGSSL_PATCH=%LEXIFOREST_PATCHES_DIR%\boringssl.patch"
if exist "%BORINGSSL_PATCH%" (
    if not exist "%BORINGSSL_SRC_DIR%\.patched" (
        echo [boringssl] Applying lexiforest boringssl.patch...
        pushd "%BORINGSSL_SRC_DIR%"
        :: Initialize git repo for patch application
        if not exist ".git" (
            "%GIT_EXE%" init
            "%GIT_EXE%" add -A
            "%GIT_EXE%" commit -q -m "init" --allow-empty 2>nul
        )
        "%GIT_EXE%" apply --check "%BORINGSSL_PATCH%" 2>nul
        if %ERRORLEVEL% neq 0 (
            echo [WARN] git apply --check failed, trying --3way...
            "%GIT_EXE%" apply --3way "%BORINGSSL_PATCH%" 2>nul
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] BoringSSL patch failed. Trying patch command...
                :: Fallback: try using patch from MSYS2/Git
                patch -p1 < "%BORINGSSL_PATCH%" 2>nul
                if %ERRORLEVEL% neq 0 (
                    echo [ERROR] All patch methods failed for BoringSSL
                    popd
                    exit /b 1
                )
            )
        ) else (
            "%GIT_EXE%" apply "%BORINGSSL_PATCH%"
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] git apply failed for BoringSSL
                popd
                exit /b 1
            )
        )
        echo .patched> ".patched"
        popd
    )
) else (
    echo [WARN] boringssl.patch not found at: %BORINGSSL_PATCH%
    echo [WARN] Run fetch_lexiforest_patches.bat first
)

:::: Fix MSVC compilation errors in patched BoringSSL
echo [boringssl] Applying MSVC compatibility fixes...
python "%WIN_BUILD_ROOT%\fix_boringssl_msvc.py"

::: CMake configure + Ninja build
if not exist "%BORINGSSL_BUILD_DIR%" mkdir "%BORINGSSL_BUILD_DIR%"
if not exist "%BORINGSSL_INSTALL_DIR%" mkdir "%BORINGSSL_INSTALL_DIR%"

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

echo [boringssl] CMake configure (CRT=%CRT%, CMAKE_CRT=%CMAKE_CRT%)...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_CXX_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=%CMAKE_CRT% ^
    -DCMAKE_C_FLAGS="%CRT_C_FLAGS% /D_CRT_NONSTDC_NO_DEPRECATE" ^
    -DCMAKE_CXX_FLAGS="%CRT_CXX_FLAGS% /D_CRT_NONSTDC_NO_DEPRECATE" ^
    -DCMAKE_C_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_CXX_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_C_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DCMAKE_CXX_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -DCMAKE_ASM_NASM_COMPILER="%NASM_EXE%" ^
    -DBUILD_TESTING=OFF ^
    -DBENCHMARK_ENABLE_TESTING=OFF ^
    -S "%BORINGSSL_SRC_DIR%" ^
    -B "%BORINGSSL_BUILD_DIR%"
if %ERRORLEVEL% neq 0 ( echo [ERROR] BoringSSL CMake failed & exit /b 1 )

echo [boringssl] Building...
"%CMAKE_EXE%" --build "%BORINGSSL_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] BoringSSL build failed & exit /b 1 )

::: Fix directory structure for curl compatibility
::: See https://everything.curl.dev/source/build/tls/boringssl
echo [boringssl] Fixing directory structure for curl...
if not exist "%BORINGSSL_BUILD_DIR%\lib" mkdir "%BORINGSSL_BUILD_DIR%\lib"

::: Copy SSL and Crypto libraries to lib/ directory
if exist "%BORINGSSL_BUILD_DIR%\ssl\ssl.lib" (
    copy /y "%BORINGSSL_BUILD_DIR%\ssl\ssl.lib" "%BORINGSSL_BUILD_DIR%\lib\libssl.lib" >nul
) else if exist "%BORINGSSL_BUILD_DIR%\ssl\ssl_static.lib" (
    copy /y "%BORINGSSL_BUILD_DIR%\ssl\ssl_static.lib" "%BORINGSSL_BUILD_DIR%\lib\libssl.lib" >nul
) else if exist "%BORINGSSL_BUILD_DIR%\ssl.lib" (
    copy /y "%BORINGSSL_BUILD_DIR%\ssl.lib" "%BORINGSSL_BUILD_DIR%\lib\libssl.lib" >nul
)
if exist "%BORINGSSL_BUILD_DIR%\crypto\crypto.lib" (
    copy /y "%BORINGSSL_BUILD_DIR%\crypto\crypto.lib" "%BORINGSSL_BUILD_DIR%\lib\libcrypto.lib" >nul
) else if exist "%BORINGSSL_BUILD_DIR%\crypto\crypto_static.lib" (
    copy /y "%BORINGSSL_BUILD_DIR%\crypto\crypto_static.lib" "%BORINGSSL_BUILD_DIR%\lib\libcrypto.lib" >nul
) else if exist "%BORINGSSL_BUILD_DIR%\crypto.lib" (
    copy /y "%BORINGSSL_BUILD_DIR%\crypto.lib" "%BORINGSSL_BUILD_DIR%\lib\libcrypto.lib" >nul
)

::: Copy include directory
if not exist "%BORINGSSL_BUILD_DIR%\include" (
    xcopy /E /I /Y /Q "%BORINGSSL_SRC_DIR%\include" "%BORINGSSL_BUILD_DIR%\include" >nul
)

::: Also install to install directory
echo [boringssl] Installing to %BORINGSSL_INSTALL_DIR%...
if not exist "%BORINGSSL_INSTALL_DIR%\lib" mkdir "%BORINGSSL_INSTALL_DIR%\lib"
if not exist "%BORINGSSL_INSTALL_DIR%\include" mkdir "%BORINGSSL_INSTALL_DIR%\include"
copy /y "%BORINGSSL_BUILD_DIR%\lib\*.lib" "%BORINGSSL_INSTALL_DIR%\lib\" >nul
xcopy /E /I /Y /Q "%BORINGSSL_BUILD_DIR%\include" "%BORINGSSL_INSTALL_DIR%\include" >nul

::: Create opensslconf.h stub (BoringSSL doesn't provide this, but curl expects it)
if not exist "%BORINGSSL_INSTALL_DIR%\include\openssl\opensslconf.h" (
    echo [boringssl] Creating opensslconf.h stub for curl compatibility...
    (
        echo /* opensslconf.h - Stub for BoringSSL compatibility */
        echo #ifndef OPENSSL_OPENSSLCONF_H
        echo #define OPENSSL_OPENSSLCONF_H
        echo #endif
    ) > "%BORINGSSL_INSTALL_DIR%\include\openssl\opensslconf.h"
)

::: Create ocsp.h stub (BoringSSL doesn't provide OCSP API, but curl expects it)
if not exist "%BORINGSSL_INSTALL_DIR%\include\openssl\ocsp.h" (
    echo [boringssl] Creating ocsp.h stub for curl compatibility...
    copy /y "%~dp0patches\boringssl-ocsp-stub.h" "%BORINGSSL_INSTALL_DIR%\include\openssl\ocsp.h" >nul
)

::: Verify
echo [boringssl] Verifying install...
if not exist "%BORINGSSL_INSTALL_DIR%\lib\libssl.lib" (
    echo [ERROR] libssl.lib not found
    dir /s /b "%BORINGSSL_BUILD_DIR%\ssl\*.lib" 2>nul
    dir /s /b "%BORINGSSL_BUILD_DIR%\crypto\*.lib" 2>nul
    exit /b 1
)
if not exist "%BORINGSSL_INSTALL_DIR%\lib\libcrypto.lib" (
    echo [ERROR] libcrypto.lib not found
    exit /b 1
)
echo [boringssl] Installed to: %BORINGSSL_INSTALL_DIR%
dir /b "%BORINGSSL_INSTALL_DIR%\lib\*.lib"

echo [boringssl] Build complete.

:endlocal
exit /b 0

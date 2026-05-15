@echo off
::: build_ngtcp2.bat - Build ngtcp2 (QUIC transport library)
::: Required for HTTP/3 fingerprinting support
::: Depends on BoringSSL (must be built before this)
setlocal enabledelayedexpansion

echo ========================================
echo [7/10] Building ngtcp2 %NGTCP2_VERSION%...
echo ========================================

::: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\ngtcp2-%NGTCP2_VERSION%.tar.bz2"
if not exist "%ARCHIVE%" (
    echo [ngtcp2] Downloading ngtcp2 %NGTCP2_VERSION%...
    curl -L --retry 3 --retry-delay 5 -o "%ARCHIVE%" "%NGTCP2_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] ngtcp2 download failed & exit /b 1 )
)

::: Extract
if not exist "%NGTCP2_SRC_DIR%" (
    echo [ngtcp2] Extracting...
    python -c "import tarfile,os;t=tarfile.open(r'%ARCHIVE%','r:bz2');t.extractall(r'%DEPS_DIR%',filter='data');t.close()"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] ngtcp2 extract failed & exit /b 1 )
)

::: Apply ngtcp2.patch from lexiforest
::: Adds ngtcp2_transport_params_raw API for raw QUIC transport parameters
set "NGTCP2_PATCH=%LEXIFOREST_PATCHES_DIR%\ngtcp2.patch"
if exist "%NGTCP2_PATCH%" (
    if not exist "%NGTCP2_SRC_DIR%\.patched" (
        echo [ngtcp2] Applying ngtcp2.patch...
        pushd "%NGTCP2_SRC_DIR%"
        if not exist ".git" (
            "%GIT_EXE%" init
            "%GIT_EXE%" add -A
            "%GIT_EXE%" commit -q -m "init" --allow-empty 2>nul
        )
        "%GIT_EXE%" apply --check "%NGTCP2_PATCH%" 2>nul
        if %ERRORLEVEL% neq 0 (
            echo [WARN] git apply --check failed, trying --3way...
            "%GIT_EXE%" apply --3way "%NGTCP2_PATCH%" 2>nul
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] ngtcp2 patch failed
                popd
                exit /b 1
            )
        ) else (
            "%GIT_EXE%" apply "%NGTCP2_PATCH%"
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] ngtcp2 patch apply failed
                popd
                exit /b 1
            )
        )
        echo .patched> ".patched"
        popd
    )
) else (
    echo [WARN] ngtcp2.patch not found at: %NGTCP2_PATCH%
    echo [WARN] Run fetch_lexiforest_patches.bat first
)

::: CMake configure
if not exist "%NGTCP2_BUILD_DIR%" mkdir "%NGTCP2_BUILD_DIR%"
if not exist "%NGTCP2_INSTALL_DIR%" mkdir "%NGTCP2_INSTALL_DIR%"

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

:::: Fix BoringSSL opensslv.h for CMake FindOpenSSL compatibility
echo [ngtcp2] Fixing BoringSSL opensslv.h for FindOpenSSL...
python "%WIN_BUILD_ROOT%\fix_installed_opensslv.py"

echo [ngtcp2] CMake configure...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%NGTCP2_INSTALL_DIR%" ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_CXX_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=%CMAKE_CRT% ^
    -DCMAKE_C_FLAGS="%CRT_C_FLAGS%" ^
    -DCMAKE_CXX_FLAGS="%CRT_CXX_FLAGS%" ^
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -DENABLE_STATIC_LIB=ON ^
    -DENABLE_SHARED_LIB=OFF ^
    -DENABLE_EXAMPLES=OFF ^
    -DENABLE_TESTS=OFF ^
    -DENABLE_OPENSSL=OFF ^
    -DENABLE_BORINGSSL=ON ^
    -DHAVE_BORINGSSL=TRUE ^
    -DBORINGSSL_INCLUDE_DIR="%BORINGSSL_INSTALL_DIR%\include" ^
    -DBORINGSSL_LIBRARIES="%BORINGSSL_INSTALL_DIR%\lib\libssl.lib;%BORINGSSL_INSTALL_DIR%\lib\libcrypto.lib" ^
    -DOPENSSL_ROOT_DIR="%BORINGSSL_INSTALL_DIR%" ^
    -DOPENSSL_INCLUDE_DIR="%BORINGSSL_INSTALL_DIR%\include" ^
    -DOPENSSL_LIBRARIES="%BORINGSSL_INSTALL_DIR%\lib\libssl.lib;%BORINGSSL_INSTALL_DIR%\lib\libcrypto.lib" ^
    -DOPENSSL_CRYPTO_LIBRARY="%BORINGSSL_INSTALL_DIR%\lib\libcrypto.lib" ^
    -DOPENSSL_SSL_LIBRARY="%BORINGSSL_INSTALL_DIR%\lib\libssl.lib" ^
    -DOPENSSL_FOUND=TRUE ^
    -DOPENSSL_VERSION="3.0.0" ^
    -DCMAKE_PREFIX_PATH="%BORINGSSL_INSTALL_DIR%;%NGHTTP3_INSTALL_DIR%" ^
    -S "%NGTCP2_SRC_DIR%" ^
    -B "%NGTCP2_BUILD_DIR%"

if %ERRORLEVEL% neq 0 ( echo [ERROR] ngtcp2 CMake failed & exit /b 1 )

echo [ngtcp2] Building...
"%CMAKE_EXE%" --build "%NGTCP2_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] ngtcp2 build failed & exit /b 1 )

echo [ngtcp2] Installing...
"%CMAKE_EXE%" --install "%NGTCP2_BUILD_DIR%" --config %BUILD_TYPE%

echo [ngtcp2] Build complete.

:endlocal
exit /b 0

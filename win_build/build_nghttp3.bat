@echo off
::: build_nghttp3.bat - Build nghttp3 (HTTP/3 framing library)
::: Required for HTTP/3 fingerprinting support
::: No crypto dependency (framing only)
setlocal enabledelayedexpansion

echo ========================================
echo [5/10] Building nghttp3 %NGHTTP3_VERSION%...
echo ========================================

::: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\nghttp3-%NGHTTP3_VERSION%.tar.bz2"
if not exist "%ARCHIVE%" (
    echo [nghttp3] Downloading nghttp3 %NGHTTP3_VERSION%...
    curl -L --retry 3 --retry-delay 5 -o "%ARCHIVE%" "%NGHTTP3_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp3 download failed & exit /b 1 )
)

::: Extract
if not exist "%NGHTTP3_SRC_DIR%" (
    echo [nghttp3] Extracting...
    python -c "import tarfile,os;t=tarfile.open(r'%ARCHIVE%','r:bz2');t.extractall(r'%DEPS_DIR%',filter='data');t.close()"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp3 extract failed & exit /b 1 )
)

::: Apply nghttp3.patch from lexiforest
::: Adds nghttp3_conn_submit_settings API for custom HTTP/3 SETTINGS frame
set "NGHTTP3_PATCH=%LEXIFOREST_PATCHES_DIR%\nghttp3.patch"
if exist "%NGHTTP3_PATCH%" (
    if not exist "%NGHTTP3_SRC_DIR%\.patched" (
        echo [nghttp3] Applying nghttp3.patch...
        pushd "%NGHTTP3_SRC_DIR%"
        if not exist ".git" (
            "%GIT_EXE%" init
            "%GIT_EXE%" add -A
            "%GIT_EXE%" commit -q -m "init" --allow-empty 2>nul
        )
        "%GIT_EXE%" apply --check "%NGHTTP3_PATCH%" 2>nul
        if %ERRORLEVEL% neq 0 (
            echo [WARN] git apply --check failed, trying --3way...
            "%GIT_EXE%" apply --3way "%NGHTTP3_PATCH%" 2>nul
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] nghttp3 patch failed
                popd
                exit /b 1
            )
        ) else (
            "%GIT_EXE%" apply "%NGHTTP3_PATCH%"
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] nghttp3 patch apply failed
                popd
                exit /b 1
            )
        )
        echo .patched> ".patched"
        popd
    )
) else (
    echo [WARN] nghttp3.patch not found at: %NGHTTP3_PATCH%
    echo [WARN] Run fetch_lexiforest_patches.bat first
)

::: CMake configure
if not exist "%NGHTTP3_BUILD_DIR%" mkdir "%NGHTTP3_BUILD_DIR%"
if not exist "%NGHTTP3_INSTALL_DIR%" mkdir "%NGHTTP3_INSTALL_DIR%"

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

echo [nghttp3] CMake configure...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%NGHTTP3_INSTALL_DIR%" ^
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
    -S "%NGHTTP3_SRC_DIR%" ^
    -B "%NGHTTP3_BUILD_DIR%"

if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp3 CMake failed & exit /b 1 )

echo [nghttp3] Building...
"%CMAKE_EXE%" --build "%NGHTTP3_BUILD_DIR%" --config %BUILD_TYPE% --target nghttp3_static
if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp3 build failed & exit /b 1 )

echo [nghttp3] Installing...
"%CMAKE_EXE%" --install "%NGHTTP3_BUILD_DIR%" --config %BUILD_TYPE% 2>nul
if %ERRORLEVEL% neq 0 (
    echo [nghttp3] CMake install failed, copying manually...
    if not exist "%NGHTTP3_INSTALL_DIR%\lib" mkdir "%NGHTTP3_INSTALL_DIR%\lib"
    if not exist "%NGHTTP3_INSTALL_DIR%\include" mkdir "%NGHTTP3_INSTALL_DIR%\include"
    copy /y "%NGHTTP3_BUILD_DIR%\lib\nghttp3.lib" "%NGHTTP3_INSTALL_DIR%\lib\" >nul 2>&1
    xcopy /E /I /Y /Q "%NGHTTP3_SRC_DIR%\lib\includes\nghttp3" "%NGHTTP3_INSTALL_DIR%\include\nghttp3" >nul 2>&1
    copy /y "%NGHTTP3_BUILD_DIR%\lib\includes\nghttp3\nghttp3.h" "%NGHTTP3_INSTALL_DIR%\include\nghttp3\" >nul 2>&1
    copy /y "%NGHTTP3_BUILD_DIR%\lib\includes\nghttp3\nghttp3ver.h" "%NGHTTP3_INSTALL_DIR%\include\nghttp3\" >nul 2>&1
)

echo [nghttp3] Build complete.

:endlocal
exit /b 0

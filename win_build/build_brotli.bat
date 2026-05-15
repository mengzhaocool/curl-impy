@echo off
::: build_brotli.bat - Build brotli as static library
::: Applies lexiforest brotli.patch (LoongArch64/IA64 model attribute fix)
setlocal enabledelayedexpansion

echo ========================================
echo [3/10] Building brotli %BROTLI_VERSION%
echo ========================================

::: Incremental build check
set "CONFIG_HASH=brotli-%BROTLI_VERSION%-%ARCH%-%CRT%-%BUILD_TYPE%"
set "MARK_FILE=%BROTLI_SRC_DIR%\.build_success"
if exist "%MARK_FILE%" (
    set /p STORED_HASH=<"%MARK_FILE%" 2>nul
    if "!STORED_HASH!"=="%CONFIG_HASH%" (
        echo [brotli] Already built. Skipping.
        goto :done
    )
)

::: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\brotli-%BROTLI_VERSION%.tar.gz"
if not exist "%ARCHIVE%" (
    echo [brotli] Downloading brotli %BROTLI_VERSION%...
    curl -L -o "%ARCHIVE%" "%BROTLI_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] brotli download failed & exit /b 1 )
)

::: Extract
if not exist "%BROTLI_SRC_DIR%" (
    echo [brotli] Extracting...
    "%TAR%" -xzf "%ARCHIVE%" -C "%DEPS_DIR%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] brotli extract failed & exit /b 1 )
)

::: Apply lexiforest brotli.patch (minor LoongArch64/IA64 fix)
set "BROTLI_PATCH=%LEXIFOREST_PATCHES_DIR%\brotli.patch"
if exist "%BROTLI_PATCH%" (
    if not exist "%BROTLI_SRC_DIR%\.patched" (
        echo [brotli] Applying lexiforest brotli.patch...
        pushd "%BROTLI_SRC_DIR%"
        if not exist ".git" (
            "%GIT_EXE%" init
            "%GIT_EXE%" add -A
            "%GIT_EXE%" commit -q -m "init" --allow-empty 2>nul
        )
        "%GIT_EXE%" apply --check "%BROTLI_PATCH%" 2>nul
        if %ERRORLEVEL% neq 0 (
            echo [WARN] git apply --check failed, trying --3way...
            "%GIT_EXE%" apply --3way "%BROTLI_PATCH%" 2>nul
            if %ERRORLEVEL% neq 0 (
                echo [WARN] brotli patch failed, non-critical for Windows
            )
        ) else (
            "%GIT_EXE%" apply "%BROTLI_PATCH%"
            if %ERRORLEVEL% neq 0 (
                echo [WARN] brotli patch apply failed, non-critical for Windows
            )
        )
        echo .patched> ".patched"
        popd
    )
) else (
    echo [INFO] brotli.patch not found (optional, non-critical for Windows)
)

::: CMake configure + Ninja build
if not exist "%BROTLI_BUILD_DIR%" mkdir "%BROTLI_BUILD_DIR%"
if not exist "%BROTLI_INSTALL_DIR%" mkdir "%BROTLI_INSTALL_DIR%"

echo [brotli] CMake configure...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%BROTLI_INSTALL_DIR%" ^
    -DCMAKE_INSTALL_LIBDIR=lib ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_CXX_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded ^
    -DCMAKE_C_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_CXX_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_C_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DCMAKE_CXX_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -S "%BROTLI_SRC_DIR%" ^
    -B "%BROTLI_BUILD_DIR%"
if %ERRORLEVEL% neq 0 ( echo [ERROR] brotli CMake failed & exit /b 1 )

echo [brotli] Building...
"%CMAKE_EXE%" --build "%BROTLI_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] brotli build failed & exit /b 1 )

echo [brotli] Installing...
"%CMAKE_EXE%" --install "%BROTLI_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] brotli install failed & exit /b 1 )

::: Verify
echo [brotli] Verifying install...
dir /b "%BROTLI_INSTALL_DIR%\lib\*.lib" 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARN] No .lib files found in brotli install dir
)

::: Write build mark
echo %CONFIG_HASH%> "%MARK_FILE%"
echo [brotli] Build complete.

:done
endlocal
exit /b 0

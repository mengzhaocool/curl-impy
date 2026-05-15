@echo off
:::: build_all.bat - One-click build script for curl-impersonate Windows
:::: Uses lexiforest/curl-impersonate patches, curl upgraded to 8.20.0
:::: Single binary with 35+ browser presets (Chrome/Firefox/Safari/Tor/OkHttp)
:::: Supports HTTP/2 and HTTP/3 (QUIC) fingerprinting + zstd compression
::::
:::: Usage: build_all.bat [command] [arch] [vs_version]
::::   command    - full (default): full build from scratch
::::                clean: clean all build artifacts then build
::::                buildonly: build without environment detection
::::                cleanonly: clean only, don't build
::::   arch       - Target architecture: x64 (default) or x86
::::   vs_version - VS version: 2022 (default) or 2019
::::
:::: Build order (11 steps):
::::   1.  Environment detection
::::   2.  Fetch lexiforest patches
::::   3.  zlib
::::   4.  zstd
::::   5.  brotli (with brotli.patch)
::::   6.  nghttp2 (MUST be <=1.63.0, priority flag removed in 1.64+)
::::   7.  nghttp3 (with nghttp3.patch, MUST be 1.15.0)
::::   8.  BoringSSL (with boringssl.patch)
::::   9.  ngtcp2 (with ngtcp2.patch, requires BoringSSL, MUST be 1.20.0)
::::   10. curl-impersonate static lib + DLL (with curl.patch)
::::   11. Verify and collect artifacts
::::
:::: DLL dependency guarantee:
::::   All dependencies are statically linked (/MT CRT + static libs)
::::   The final DLL only depends on Windows system DLLs

setlocal enabledelayedexpansion

:::: Parse command line arguments
set "COMMAND=%~1"
set "ARCH=%~2"
set "VS_VERSION=%~3"

if not defined COMMAND set "COMMAND=full"
if not defined ARCH set "ARCH=x64"
if not defined VS_VERSION set "VS_VERSION=2022"

:::: Normalize command
if /i "%COMMAND%"=="clean" set "DO_CLEAN=1" & set "DO_BUILD=1"
if /i "%COMMAND%"=="full" set "DO_CLEAN=0" & set "DO_BUILD=1"
if /i "%COMMAND%"=="buildonly" set "DO_CLEAN=0" & set "DO_BUILD=1"
if /i "%COMMAND%"=="cleanonly" set "DO_CLEAN=1" & set "DO_BUILD=0"
if not defined DO_CLEAN set "DO_CLEAN=0"
if not defined DO_BUILD set "DO_BUILD=1"

echo ================================================
echo  curl-impersonate Windows Build Script
echo  (lexiforest patches + curl 8.20.0 + zstd)
echo ================================================
echo  Command:      %COMMAND%
echo  Architecture: %ARCH%
echo  VS Version:   %VS_VERSION%
echo ================================================
echo.

:::: ==============================================
:::: Step 0: Load configuration
:::: ==============================================
echo [0/11] Loading configuration...
call "%~dp0config.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to load configuration
    exit /b 1
)

:::: ==============================================
:::: Clean if requested
:::: ==============================================
if "%DO_CLEAN%"=="1" (
    echo.
    echo ================================================
    echo  CLEANING ALL BUILD ARTIFACTS
    echo ================================================

    :: Remove deps directory (downloaded source)
    if exist "%DEPS_DIR%" (
        echo [clean] Removing deps directory...
        rmdir /s /q "%DEPS_DIR%"
    )

    :: Remove build directory (build intermediates)
    if exist "%BUILD_DIR%" (
        echo [clean] Removing build directory...
        rmdir /s /q "%BUILD_DIR%"
    )

    :: Remove install directory (installed libraries)
    if exist "%INSTALL_DIR%" (
        echo [clean] Removing install directory...
        rmdir /s /q "%INSTALL_DIR%"
    )

    :: Remove output directory (final artifacts)
    if exist "%OUTPUT_DIR%" (
        echo [clean] Removing output directory...
        rmdir /s /q "%OUTPUT_DIR%"
    )

    :: Remove build findings
    if exist "%BUILD_FINDINGS%" (
        del /f "%BUILD_FINDINGS%"
    )

    :: Recreate empty directories
    mkdir "%DEPS_DIR%" 2>nul
    mkdir "%BUILD_DIR%" 2>nul
    mkdir "%INSTALL_DIR%" 2>nul
    mkdir "%OUTPUT_DIR%" 2>nul

    echo [clean] Clean complete.
    echo.

    if "%DO_BUILD%"=="0" (
        echo Clean-only mode. Exiting.
        endlocal
        exit /b 0
    )
)

:::: ==============================================
:::: Initialize build findings
:::: ==============================================
echo # Build Findings Record> "%BUILD_FINDINGS%"
echo.>> "%BUILD_FINDINGS%"
echo ^| ID ^| Category ^| Description ^| Impact ^| Status ^| Reference ^|>> "%BUILD_FINDINGS%"
echo ^|------^|----------^|-------------^|--------^|--------^|-----------^|>> "%BUILD_FINDINGS%"

:::: ==============================================
:::: Step 1: Environment detection
:::: ==============================================
echo.
echo [1/11] Detecting build environment...
call "%~dp0detect_env.bat" %ARCH% %VS_VERSION%
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Environment detection failed
    echo Please install missing tools and try again.
    exit /b 1
)

:::: Check for Windows 10 SDK
if defined WIN10_SDK_MISSING (
    echo [ERROR] Windows 10 SDK is required but not found.
    echo Install it via Visual Studio Installer and try again.
    exit /b 1
)

:::: Re-load config after environment is set (ARCH may have been updated)
call "%~dp0config.bat"

:::: ==============================================
:::: Step 2: Fetch lexiforest patches
:::: ==============================================
echo.
echo [2/11] Fetching lexiforest patches...
call "%~dp0fetch_lexiforest_patches.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to fetch lexiforest patches
    exit /b 1
)

:::: ==============================================
:::: Step 3: Build zlib
:::: ==============================================
echo.
echo [3/11] Building zlib...
call "%~dp0build_zlib.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] zlib build failed
    exit /b 1
)

:::: ==============================================
:::: Step 4: Build zstd
:::: ==============================================
echo.
echo [4/11] Building zstd...
call "%~dp0build_zstd.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] zstd build failed
    exit /b 1
)

:::: ==============================================
:::: Step 5: Build brotli
:::: ==============================================
echo.
echo [5/11] Building brotli...
call "%~dp0build_brotli.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] brotli build failed
    exit /b 1
)

:::: ==============================================
:::: Step 6: Build nghttp2 (MUST be <=1.63.0)
:::: ==============================================
echo.
echo [6/11] Building nghttp2...
call "%~dp0build_nghttp2.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] nghttp2 build failed
    exit /b 1
)

:::: ==============================================
:::: Step 7: Build nghttp3 (with patch, MUST be 1.15.0)
:::: ==============================================
echo.
echo [7/11] Building nghttp3...
call "%~dp0build_nghttp3.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] nghttp3 build failed
    exit /b 1
)

:::: ==============================================
:::: Step 8: Build BoringSSL
:::: ==============================================
echo.
echo [8/11] Building BoringSSL...
call "%~dp0build_boringssl.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] BoringSSL build failed
    exit /b 1
)

:::: ==============================================
:::: Step 9: Build ngtcp2 (requires BoringSSL, MUST be 1.20.0)
:::: ==============================================
echo.
echo [9/11] Building ngtcp2...
call "%~dp0build_ngtcp2.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] ngtcp2 build failed
    exit /b 1
)

:::: ==============================================
:::: Step 10: Build curl-impersonate (static lib + DLL)
:::: ==============================================
echo.
echo [10/11] Building curl-impersonate...

:::: Build static lib first
call "%~dp0build_curl_lib.bat"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] curl static lib build failed
    exit /b 1
)

:::: Build DLL
:::: Set GIT_EXE if not already set
if not defined GIT_EXE (
    where git >nul 2>&1 && set "GIT_EXE=git"
    if not defined GIT_EXE (
        if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_EXE=C:\Program Files\Git\cmd\git.exe"
    )
)

:::: Set CURL_DEF_SOURCE for .def file
set "CURL_DEF_SOURCE=%WIN_BUILD_ROOT%\libcurl-impersonate.def"

:::: Regenerate .def file to include current symbols
if defined CMAKE_EXE (
    echo [10/11] Regenerating .def file...
    python "%WIN_BUILD_ROOT%\generate_def_file.py" --curl-include "%CURL_SRC_DIR%\include" --boringssl-lib-dir "%BORINGSSL_INSTALL_DIR%\lib" --zlib-def "%ZLIB_SRC_DIR%\win32\zlib.def" --brotli-lib-dir "%BROTLI_INSTALL_DIR%\lib" --nghttp2-lib-dir "%NGHTTP2_INSTALL_DIR%\lib" --output "%CURL_DEF_SOURCE%" --dll-name libcurl-impersonate
    if %ERRORLEVEL% neq 0 (
        echo [WARN] .def file generation failed, using existing file
    )
)

call "%~dp0build_curl_dll.bat"
if %ERRORLEVEL% neq 0 (
    echo [WARN] curl DLL build failed (non-fatal, exe still available)
) else (
    echo [10/11] DLL build complete.
)

:::: ==============================================
:::: Step 11: Verify and collect artifacts
:::: ==============================================
echo.
echo [11/11] Verifying and collecting artifacts...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:::: Verify build - check for DLL dependency on non-system DLLs
set "CURL_DLL=%OUTPUT_DIR%\libcurl-impersonate.dll"
if exist "%CURL_DLL%" (
    echo [verify] Checking DLL dependencies...
    echo [verify] DLL: %CURL_DLL%
    for /f "tokens=*" %%d in ('dumpbin /dependents "%CURL_DLL%" 2^>nul ^| findstr /i ".dll"') do (
        set "DEP=%%d"
        set "IS_SYSTEM=0"
        for %%s in (%SYSTEM_DLLS%) do (
            if /i "!DEP!"=="%%s" set "IS_SYSTEM=1"
        )
        if "!IS_SYSTEM!"=="0" (
            echo [WARN] Non-system DLL dependency found: !DEP!
        )
    )
    echo [verify] DLL dependency check complete.
)

:::: Copy exe if available
if exist "%CURL_BUILD_DIR%\src\curl-impersonate.exe" (
    copy /y "%CURL_BUILD_DIR%\src\curl-impersonate.exe" "%OUTPUT_DIR%\" >nul
)

:::: Copy build findings
if exist "%BUILD_FINDINGS%" (
    copy /y "%BUILD_FINDINGS%" "%OUTPUT_DIR%\" >nul
)

:::: ==============================================
:::: Done!
:::: ==============================================
echo.
echo ================================================
echo  BUILD COMPLETE
echo ================================================
echo  Output directory: %OUTPUT_DIR%
echo.
echo  Artifacts:
dir /b "%OUTPUT_DIR%\*.*" 2>nul
echo.
echo  To test: %OUTPUT_DIR%\curl-impersonate.exe -V
echo ================================================

::endlocal
exit /b 0

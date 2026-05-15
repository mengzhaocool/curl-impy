@echo off
:::: build_zstd.bat - Build zstd as static library
:::: Required for zstd content-encoding support in curl (Chrome 123+)
:::: zstd is also used by BoringSSL for certificate compression
:setlocal enabledelayedexpansion

echo ========================================
echo [4/11] Building zstd %ZSTD_VERSION%
echo ========================================

:::: Incremental build check
set "CONFIG_HASH=zstd-%ZSTD_VERSION%-%ARCH%-%CRT%-%BUILD_TYPE%"
set "MARK_FILE=%ZSTD_SRC_DIR%\.build_success"
if exist "%MARK_FILE%" (
    set /p STORED_HASH=<"%MARK_FILE%" 2>nul
    if "!STORED_HASH!"=="%CONFIG_HASH%" (
        echo [zstd] Already built. Skipping.
        goto :done
    )
)

:::: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\zstd-%ZSTD_VERSION%.tar.gz"
if not exist "%ARCHIVE%" (
    echo [zstd] Downloading zstd %ZSTD_VERSION%...
    curl -L --retry 3 --retry-delay 5 -o "%ARCHIVE%" "%ZSTD_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] zstd download failed & exit /b 1 )
)

:::: Extract
if not exist "%ZSTD_SRC_DIR%" (
    echo [zstd] Extracting...
    "%TAR%" -xzf "%ARCHIVE%" -C "%DEPS_DIR%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] zstd extract failed & exit /b 1 )
)

:::: CMake configure + Ninja build
:::: zstd CMake is in build/cmake/ subdirectory
if not exist "%ZSTD_BUILD_DIR%" mkdir "%ZSTD_BUILD_DIR%"
if not exist "%ZSTD_INSTALL_DIR%" mkdir "%ZSTD_INSTALL_DIR%"

:::: Determine CRT runtime library flag for CMake
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

echo [zstd] CMake configure...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%ZSTD_INSTALL_DIR%" ^
    -DCMAKE_INSTALL_LIBDIR=lib ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_CXX_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=%CMAKE_CRT% ^
    -DCMAKE_C_FLAGS="%CRT_C_FLAGS%" ^
    -DCMAKE_CXX_FLAGS="%CRT_CXX_FLAGS%" ^
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -DZSTD_BUILD_STATIC=ON ^
    -DZSTD_BUILD_SHARED=OFF ^
    -DZSTD_BUILD_PROGRAMS=OFF ^
    -DZSTD_BUILD_TESTS=OFF ^
    -DZSTD_MULTITHREAD_SUPPORT=OFF ^
    -S "%ZSTD_SRC_DIR%\build\cmake" ^
    -B "%ZSTD_BUILD_DIR%"
if %ERRORLEVEL% neq 0 ( echo [ERROR] zstd CMake failed & exit /b 1 )

echo [zstd] Building...
"%CMAKE_EXE%" --build "%ZSTD_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] zstd build failed & exit /b 1 )

echo [zstd] Installing...
"%CMAKE_EXE%" --install "%ZSTD_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] zstd install failed & exit /b 1 )

:::: Verify
echo [zstd] Verifying install...
if not exist "%ZSTD_INSTALL_DIR%\include\zstd.h" (
    echo [ERROR] zstd.h not found in install dir
    exit /b 1
)
echo [zstd] Installed to: %ZSTD_INSTALL_DIR%
dir /b "%ZSTD_INSTALL_DIR%\lib\*.lib" 2>nul

:::: Write build mark
echo %CONFIG_HASH%> "%MARK_FILE%"
echo [zstd] Build complete.

:done
endlocal
exit /b 0

@echo off
:: build_zlib.bat - Build zlib as static library
setlocal enabledelayedexpansion

echo ========================================
echo [1/5] Building zlib %ZLIB_VERSION%
echo ========================================

:: Incremental build check
set "CONFIG_HASH=zlib-%ZLIB_VERSION%-%ARCH%-%CRT%-%BUILD_TYPE%"
set "MARK_FILE=%ZLIB_SRC_DIR%\.build_success"
if exist "%MARK_FILE%" (
    set /p STORED_HASH=<"%MARK_FILE%" 2>nul
    if "!STORED_HASH!"=="%CONFIG_HASH%" (
        echo [zlib] Already built. Skipping.
        goto :done
    )
)

:: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\zlib-%ZLIB_VERSION%.tar.gz"
if not exist "%ARCHIVE%" (
    echo [zlib] Downloading zlib %ZLIB_VERSION%...
    curl -L -o "%ARCHIVE%" "%ZLIB_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] zlib download failed & exit /b 1 )
)

:: Extract
if not exist "%ZLIB_SRC_DIR%" (
    echo [zlib] Extracting...
    "%TAR%" -xzf "%ARCHIVE%" -C "%DEPS_DIR%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] zlib extract failed & exit /b 1 )
)

:: CMake configure + Ninja build
if not exist "%ZLIB_BUILD_DIR%" mkdir "%ZLIB_BUILD_DIR%"
if not exist "%ZLIB_INSTALL_DIR%" mkdir "%ZLIB_INSTALL_DIR%"

echo [zlib] CMake configure...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%ZLIB_INSTALL_DIR%" ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded ^
    -DCMAKE_C_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_C_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DCMAKE_INSTALL_LIBDIR=lib ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -S "%ZLIB_SRC_DIR%" ^
    -B "%ZLIB_BUILD_DIR%"
if %ERRORLEVEL% neq 0 ( echo [ERROR] zlib CMake failed & exit /b 1 )

echo [zlib] Building...
"%CMAKE_EXE%" --build "%ZLIB_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] zlib build failed & exit /b 1 )

echo [zlib] Installing...
"%CMAKE_EXE%" --install "%ZLIB_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] zlib install failed & exit /b 1 )

:: Verify
echo [zlib] Verifying install...
if not exist "%ZLIB_INSTALL_DIR%\include\zlib.h" (
    echo [ERROR] zlib.h not found in install dir
    exit /b 1
)
echo [zlib] Installed to: %ZLIB_INSTALL_DIR%
dir /b "%ZLIB_INSTALL_DIR%\lib\*.lib" 2>nul

:: Write build mark
echo %CONFIG_HASH%> "%MARK_FILE%"
echo [zlib] Build complete.

:done
endlocal
exit /b 0

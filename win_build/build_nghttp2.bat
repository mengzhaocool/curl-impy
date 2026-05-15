@echo off
:: build_nghttp2.bat - Build nghttp2 as static library
setlocal enabledelayedexpansion

echo ========================================
echo [3/5] Building nghttp2 %NGHTTP2_VERSION%
echo ========================================

:: Incremental build check
set "CONFIG_HASH=nghttp2-%NGHTTP2_VERSION%-%ARCH%-%CRT%-%BUILD_TYPE%"
set "MARK_FILE=%NGHTTP2_SRC_DIR%\.build_success"
if exist "%MARK_FILE%" (
    set /p STORED_HASH=<"%MARK_FILE%" 2>nul
    if "!STORED_HASH!"=="%CONFIG_HASH%" (
        echo [nghttp2] Already built. Skipping.
        goto :done
    )
)

:: Download
if not exist "%DEPS_DIR%" mkdir "%DEPS_DIR%"
set "ARCHIVE=%DEPS_DIR%\nghttp2-%NGHTTP2_VERSION%.tar.bz2"
if not exist "%ARCHIVE%" (
    echo [nghttp2] Downloading nghttp2 %NGHTTP2_VERSION%...
    curl -L -o "%ARCHIVE%" "%NGHTTP2_URL%"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp2 download failed & exit /b 1 )
)

:: Extract
if not exist "%NGHTTP2_SRC_DIR%" (
    echo [nghttp2] Extracting...
    python -c "import tarfile; tarfile.open(r'%ARCHIVE%', 'r:bz2').extractall(r'%DEPS_DIR%')"
    if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp2 extract failed & exit /b 1 )
)

:: CMake configure + Ninja build
if not exist "%NGHTTP2_BUILD_DIR%" mkdir "%NGHTTP2_BUILD_DIR%"
if not exist "%NGHTTP2_INSTALL_DIR%" mkdir "%NGHTTP2_INSTALL_DIR%"

echo [nghttp2] CMake configure...
"%CMAKE_EXE%" -G Ninja ^
    -DCMAKE_BUILD_TYPE=%BUILD_TYPE% ^
    -DCMAKE_INSTALL_PREFIX="%NGHTTP2_INSTALL_DIR%" ^
    -DCMAKE_INSTALL_LIBDIR=lib ^
    -DCMAKE_C_COMPILER=cl ^
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded ^
    -DCMAKE_C_FLAGS_RELEASE="/MT /O2 /DNDEBUG" ^
    -DCMAKE_C_FLAGS_DEBUG="/MTd /Zi /D_DEBUG" ^
    -DENABLE_LIB_ONLY=ON ^
    -DENABLE_SHARED_LIB=OFF ^
    -DENABLE_STATIC_LIB=ON ^
    -DCMAKE_MAKE_PROGRAM="%NINJA_EXE%" ^
    -S "%NGHTTP2_SRC_DIR%" ^
    -B "%NGHTTP2_BUILD_DIR%"
if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp2 CMake failed & exit /b 1 )

echo [nghttp2] Building...
"%CMAKE_EXE%" --build "%NGHTTP2_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp2 build failed & exit /b 1 )

echo [nghttp2] Installing...
"%CMAKE_EXE%" --install "%NGHTTP2_BUILD_DIR%" --config %BUILD_TYPE%
if %ERRORLEVEL% neq 0 ( echo [ERROR] nghttp2 install failed & exit /b 1 )

:: Copy static library as nghttp2.lib (replacing the DLL import lib)
if exist "%NGHTTP2_BUILD_DIR%\lib\nghttp2_static.lib" (
    copy /y "%NGHTTP2_BUILD_DIR%\lib\nghttp2_static.lib" "%NGHTTP2_INSTALL_DIR%\lib\nghttp2.lib" >nul
    echo [nghttp2] Copied nghttp2_static.lib as nghttp2.lib (static library)
) else (
    echo [WARN] nghttp2_static.lib not found, using default nghttp2.lib
)

:: Verify
echo [nghttp2] Verifying install...
dir /b "%NGHTTP2_INSTALL_DIR%\lib\*.lib" 2>nul
if not exist "%NGHTTP2_INSTALL_DIR%\include\nghttp2\nghttp2.h" (
    echo [WARN] nghttp2.h not found at expected path
)

:: Write build mark
echo %CONFIG_HASH%> "%MARK_FILE%"
echo [nghttp2] Build complete.

:done
endlocal
exit /b 0

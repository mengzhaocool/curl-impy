@echo off
:::: _build_all.bat - One-click build entry point
:::: Builds x64 and x86 DLL+lib from scratch
::::
:::: Usage: _build_all.bat [options]
::::   --only-arch=x64    Build only x64
::::   --only-arch=x86    Build only x86
::::   --skip-clean       Skip initial cleanup
::::   --keep-intermediates  Keep intermediate files

echo ================================================================
echo   curl-impersonate Unified Build Script
echo ================================================================

python "%~dp0_build_all.py" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo Build completed successfully!

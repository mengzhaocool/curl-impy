@echo off
echo Installing libidn2, libpsl, libssh2 via vcpkg (without libidn2 feature for libpsl)...
C:\vcpkg\vcpkg.exe install libidn2:x64-windows-static libpsl:x64-windows-static libssh2:x64-windows-static --recurse 2>&1
echo EXIT_CODE=%ERRORLEVEL%

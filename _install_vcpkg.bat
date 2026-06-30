@echo off
C:\vcpkg\vcpkg.exe install libidn2:x64-windows-static "libpsl[libidn2]:x64-windows-static" --recurse > d:\curl-impersonate-8.20.0\_vcpkg_install.txt 2>&1
echo EXIT_CODE=%ERRORLEVEL%

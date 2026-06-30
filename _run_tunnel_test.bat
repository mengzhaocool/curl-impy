@echo off
REM Compile and run CONNECT tunnel test
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64

cd /d D:\curl-impersonate-8.20.0

echo Compiling test_connect_tunnel.c...
cl /nologo /MT /Fe:test_connect_tunnel.exe test_connect_tunnel.c ^
   /I output\include ^
   /link /LIBPATH:output libcurl-impersonate.lib ws2_32.lib advapi32.lib crypt32.lib secur32.lib bcrypt.lib ncrypt.lib normaliz.lib iphlpapi.lib user32.lib gdi32.lib

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Compilation failed
    exit /b 1
)

echo.
echo Running test...
test_connect_tunnel.exe

exit /b %ERRORLEVEL%

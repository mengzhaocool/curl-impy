@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1

echo Compiling test...
cl /MT /O2 /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB d:\curl-impersonate-8.20.0\_test_all_proto.c /I d:\curl-impersonate-8.20.0\deps\curl-8.20.0\include /link d:\curl-impersonate-8.20.0\output\libcurl-impersonate_imp.lib WS2_32.lib CRYPT32.lib WLDAP32.lib IPHLPAPI.lib /OUT:d:\curl-impersonate-8.20.0\_test_all_proto.exe

if %ERRORLEVEL% NEQ 0 (
    echo Build FAILED!
    exit /b 1
)

echo.
echo Running test...
d:\curl-impersonate-8.20.0\_test_all_proto.exe

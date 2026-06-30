@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d d:\curl-impersonate-8.20.0
cl /MT /O2 /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB test_xweb_fingerprint.c /I deps\curl-8.20.0\include /link output\libcurl-impersonate_imp.lib WS2_32.lib CRYPT32.lib WLDAP32.lib IPHLPAPI.lib /OUT:test_xweb_fingerprint.exe
if %ERRORLEVEL% equ 0 (
    echo BUILD OK
    test_xweb_fingerprint.exe
) else (
    echo BUILD FAILED
)

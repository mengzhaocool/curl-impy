@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d d:\curl-impersonate-8.20.0
cmake --build build/curl-dll --config Release
copy /Y build\curl-dll\lib\libcurl-impersonate.dll .
copy /Y build\curl-dll\lib\libcurl-impersonate.dll output\
cl /nologo /MT /Ioutput\include test_xweb_debug.c /link /LIBPATH:output libcurl-impersonate_imp.lib ws2_32.lib advapi32.lib crypt32.lib user32.lib normaliz.lib /OUT:test_xweb_debug.exe
if %errorlevel% neq 0 exit /b 1
d:\curl-impersonate-8.20.0\test_xweb_debug.exe > d:\curl-impersonate-8.20.0\_debug_output.txt 2>&1

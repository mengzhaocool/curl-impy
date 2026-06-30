@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d d:\curl-impersonate-8.20.0

echo === Rebuilding DLL ===
cmake --build build/curl-dll --config Release
if %errorlevel% neq 0 (
    echo BUILD FAILED
    exit /b 1
)

echo === Copying DLL ===
copy /Y build\curl-dll\lib\libcurl-impersonate.dll output\
copy /Y build\curl-dll\lib\libcurl-impersonate.dll .

echo === Rebuilding test ===
cl /nologo /MT /Ioutput\include test_xweb_fingerprint.c /link /LIBPATH:output libcurl-impersonate_imp.lib ws2_32.lib advapi32.lib crypt32.lib user32.lib normaliz.lib /OUT:test_xweb_fingerprint.exe
if %errorlevel% neq 0 (
    echo TEST BUILD FAILED
    exit /b 1
)

echo === Running test ===
test_xweb_fingerprint.exe > _test_output.txt 2>&1
type _test_output.txt

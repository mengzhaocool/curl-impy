@echo off
setlocal

set DLL_DIR=D:\curl-impersonate-8.20.0\output
set BUILD_DIR=D:\curl-impersonate-8.20.0\build\curl\lib
set INC_DIR=D:\curl-impersonate-8.20.0\output\include
set XWEB_JSON=D:\curl-impersonate\XWEB.json

echo [1/2] Compiling verify_impersonate.c ...
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1

cl /MT /O2 /W3 /D_CRT_SECURE_NO_WARNINGS ^
   /I"%INC_DIR%" ^
   D:\curl-impersonate-8.20.0\verify_impersonate.c ^
   /link /LIBPATH:"%BUILD_DIR%" libcurl-impersonate_imp.lib ws2_32.lib crypt32.lib normaliz.lib advapi32.lib kernel32.lib user32.lib iphlpapi.lib ^
   /OUT:D:\curl-impersonate-8.20.0\verify_impersonate.exe

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Compilation failed!
    exit /b 1
)

echo [2/2] Running verification ...
echo.
copy /Y "%BUILD_DIR%\libcurl-impersonate.dll" "%DLL_DIR%\libcurl-impersonate.dll" >nul 2>&1

D:\curl-impersonate-8.20.0\verify_impersonate.exe "%XWEB_JSON%"

echo.
echo Done. Exit code: %ERRORLEVEL%

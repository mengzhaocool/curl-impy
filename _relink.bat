@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
del /q "d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.dll" 2>nul
cmake --build "d:\curl-impersonate-8.20.0\build\curl-dll" --config Release
if %ERRORLEVEL% neq 0 (
    echo BUILD FAILED
    exit /b 1
)
copy /y "d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.dll" "d:\curl-impersonate-8.20.0\output\" >nul
copy /y "d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate_imp.lib" "d:\curl-impersonate-8.20.0\output\" >nul
copy /y "d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.dll" "d:\curl-impersonate-8.20.0\" >nul
echo BUILD OK
for %%f in ("d:\curl-impersonate-8.20.0\output\libcurl-impersonate.dll" "d:\curl-impersonate-8.20.0\output\libcurl-impersonate_imp.lib") do echo   %%~nxf: %%~zf bytes

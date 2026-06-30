@echo off
:: Quick rebuild of curl-impersonate DLL after .def file changes
:: This only relinks the DLL (no recompile needed since we only changed .def)

:: Set up VS environment
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
if %ERRORLEVEL% neq 0 (
    echo ERROR: vcvarsall.bat failed
    exit /b 1
)

:: Find Ninja
set "NINJA_EXE="
where ninja >nul 2>&1 && set "NINJA_EXE=ninja"
if not defined NINJA_EXE (
    set "NINJA_EXE=C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"
)

echo Using Ninja: %NINJA_EXE%
echo Using CMake: cmake

:: Rebuild - touch the .def file to force relink
copy /b "d:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\libcurl.def" +,, "d:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\libcurl.def"

cd /d d:\curl-impersonate-8.20.0\build\curl-dll

:: Build using cmake
cmake --build . --config Release 2>&1

if %ERRORLEVEL% neq 0 (
    echo BUILD FAILED
    exit /b 1
)

:: Copy to output
copy /y "d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.dll" "d:\curl-impersonate-8.20.0\output\libcurl-impersonate.dll"
copy /y "d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.lib" "d:\curl-impersonate-8.20.0\output\libcurl-impersonate.lib" 2>nul

echo.
echo === REBUILD COMPLETE ===
dir "d:\curl-impersonate-8.20.0\output\libcurl-impersonate.dll"

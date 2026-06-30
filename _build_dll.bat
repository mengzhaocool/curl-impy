@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d d:\curl-impersonate-8.20.0
cmake --build build/curl-dll --config Release 2>&1
echo EXIT=%errorlevel%

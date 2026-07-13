@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul 2>&1
cd /d D:\curl-impersonate\win_build_full\tests
cl /arch:SSE2 /nologo /W3 /Fe:c4_supplement.exe c4_supplement.c /link

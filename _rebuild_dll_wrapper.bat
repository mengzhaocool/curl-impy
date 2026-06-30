@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
cd /d d:\curl-impersonate-8.20.0
python _rebuild_dll2.py

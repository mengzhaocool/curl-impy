@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
where normaliz.lib
link /lib /list:"D:\Program Files (x86)\Windows Kits\10\lib\10.0.26100.0\um\x64\normaliz.lib" 2>&1 | findstr /c:"normaliz" /c:"error"

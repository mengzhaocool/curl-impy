@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64
cd /d d:\curl-impersonate-8.20.0
cl /nologo /MT /Ioutput\include test_xweb_fingerprint.c /link /LIBPATH:output libcurl-impersonate_imp.lib ws2_32.lib advapi32.lib crypt32.lib user32.lib normaliz.lib /OUT:test_xweb_fingerprint.exe

@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1

echo Reconfiguring CMake...
cmake -S d:\curl-impersonate-8.20.0\deps\curl-8.20.0 -B d:\curl-impersonate-8.20.0\build\curl-dll -G Ninja ^
    -DCMAKE_BUILD_TYPE=Release ^
    -DCMAKE_INSTALL_PREFIX=d:\curl-impersonate-8.20.0\install\curl-dll ^
    -DCMAKE_PREFIX_PATH=d:\curl-impersonate-8.20.0\install\boringssl;d:\curl-impersonate-8.20.0\install\brotli;d:\curl-impersonate-8.20.0\install\zlib;d:\curl-impersonate-8.20.0\install\nghttp2;d:\curl-impersonate-8.20.0\install\nghttp3;d:\curl-impersonate-8.20.0\install\ngtcp2;d:\curl-impersonate-8.20.0\install\zstd ^
    -DBUILD_SHARED_LIBS=ON ^
    -DBUILD_STATIC_LIBS=OFF ^
    -DBUILD_CURL_EXE=OFF ^
    -DBUILD_TESTING=OFF ^
    -DHTTP_ONLY=OFF ^
    -DCURL_USE_OPENSSL=ON ^
    -DCURL_BROTLI=ON ^
    -DCURL_ZSTD=ON ^
    -DUSE_NGHTTP2=ON ^
    -DUSE_NGTCP2=ON ^
    -DUSE_NGHTTP3=ON ^
    -DCURL_HIDDEN_SYMBOLS=ON ^
    -DOPENSSL_ROOT_DIR=d:\curl-impersonate-8.20.0\install\boringssl ^
    -DZLIB_ROOT=d:\curl-impersonate-8.20.0\install\zlib ^
    -DCURL_DISABLE_LDAP=ON ^
    -DCURL_DISABLE_LDAPS=ON ^
    -DCURL_DISABLE_RTSP=ON ^
    -DCURL_DISABLE_DICT=ON ^
    -DCURL_DISABLE_TELNET=ON ^
    -DCURL_DISABLE_TFTP=ON ^
    -DCURL_DISABLE_POP3=ON ^
    -DCURL_DISABLE_IMAP=ON ^
    -DCURL_DISABLE_SMB=ON ^
    -DCURL_DISABLE_SMTP=ON ^
    -DCURL_DISABLE_GOPHER=ON ^
    -DCURL_DISABLE_MQTT=ON ^
    -DCURL_ENABLE_EXPORT_TARGET=OFF

echo Building DLL...
cmake --build d:\curl-impersonate-8.20.0\build\curl-dll --config Release

echo Copying files...
copy /y d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.dll d:\curl-impersonate-8.20.0\output\
copy /y d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate_imp.lib d:\curl-impersonate-8.20.0\output\
copy /y d:\curl-impersonate-8.20.0\build\curl-dll\lib\libcurl-impersonate.dll d:\curl-impersonate-8.20.0\

echo Done!

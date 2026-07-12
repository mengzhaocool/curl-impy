#!/usr/bin/env bash
# CI-only build script (not shipped to users)
# Builds libcurl-impersonate-chrome.so / .dylib on Linux/macOS
set -ex

ROOT="${1:-.}"
DEPS="$ROOT/ci_deps"
BUILD="$ROOT/ci_build"
INSTALL="$ROOT/ci_install"
PATCHES="$ROOT/win_build/patches"
SRC_PATCHES="$ROOT/chrome/patches"

BORINGSSL_COMMIT="92316dc661f0a8aad68b8783889dc6a355e27735"
CURL_VERSION="8.20.0"
PIC="-fPIC -O2"

mkdir -p "$DEPS" "$BUILD" "$INSTALL"

# 1. zlib
cd "$DEPS"
[ -f "zlib-1.3.1.tar.gz" ] || curl -sL -o zlib-1.3.1.tar.gz https://zlib.net/zlib-1.3.1.tar.gz
[ -d "zlib-1.3.1" ] || tar xf zlib-1.3.1.tar.gz
rm -rf "$BUILD/zlib" && mkdir "$BUILD/zlib" && cd "$BUILD/zlib"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
  -DCMAKE_INSTALL_PREFIX="$INSTALL/zlib" "$DEPS/zlib-1.3.1"
cmake --build . && cmake --install . 2>/dev/null || true

# 2. brotli
cd "$DEPS"
[ -f "brotli-1.0.9.tar.gz" ] || curl -sL -o brotli-1.0.9.tar.gz https://github.com/google/brotli/archive/refs/tags/v1.0.9.tar.gz
[ -d "brotli-1.0.9" ] || tar xf brotli-1.0.9.tar.gz
rm -rf "$BUILD/brotli" && mkdir "$BUILD/brotli" && cd "$BUILD/brotli"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_INSTALL_PREFIX="$INSTALL/brotli" "$DEPS/brotli-1.0.9"
cmake --build . && cmake --install . 2>/dev/null || true

# 3. nghttp2
cd "$DEPS"
[ -f "nghttp2-1.56.0.tar.bz2" ] || curl -sL -o nghttp2-1.56.0.tar.bz2 "https://github.com/nghttp2/nghttp2/releases/download/v1.56.0/nghttp2-1.56.0.tar.bz2"
[ -d "nghttp2-1.56.0" ] || tar xf nghttp2-1.56.0.tar.bz2
rm -rf "$BUILD/nghttp2" && mkdir "$BUILD/nghttp2" && cd "$BUILD/nghttp2"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
  -DENABLE_SHARED_LIB=OFF -DENABLE_STATIC_LIB=ON -DENABLE_APP=OFF \
  -DENABLE_EXAMPLES=OFF -DENABLE_HPACK_TOOLS=OFF \
  -DCMAKE_INSTALL_PREFIX="$INSTALL/nghttp2" "$DEPS/nghttp2-1.56.0"
cmake --build . && cmake --install . 2>/dev/null || true

# 4. zstd
cd "$DEPS"
[ -f "zstd-1.5.7.tar.gz" ] || curl -sL -o zstd-1.5.7.tar.gz "https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz"
[ -d "zstd-1.5.7" ] || tar xf zstd-1.5.7.tar.gz
rm -rf "$BUILD/zstd" && mkdir "$BUILD/zstd" && cd "$BUILD/zstd"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
  -DZSTD_BUILD_STATIC=ON -DZSTD_BUILD_SHARED=OFF -DZSTD_BUILD_PROGRAMS=OFF \
  -DCMAKE_INSTALL_PREFIX="$INSTALL/zstd" "$DEPS/zstd-1.5.7/build/cmake"
cmake --build . && cmake --install . 2>/dev/null || true

# 5. BoringSSL
cd "$DEPS"
[ -f "boringssl.zip" ] || curl -sL -o boringssl.zip "https://github.com/google/boringssl/archive/$BORINGSSL_COMMIT.zip"
[ -d "boringssl" ] || unzip -q boringssl.zip && mv "boringssl-$BORINGSSL_COMMIT" boringssl 2>/dev/null || true
rm -rf "$BUILD/boringssl" && mkdir "$BUILD/boringssl" && cd "$BUILD/boringssl"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="$PIC" -DCMAKE_CXX_FLAGS="$PIC" \
  -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_TESTING=OFF "$DEPS/boringssl"
cmake --build . --target ssl crypto
mkdir -p "$INSTALL/boringssl/lib" "$INSTALL/boringssl/include"
cp ssl/libssl.a crypto/libcrypto.a "$INSTALL/boringssl/lib/" 2>/dev/null || \
  find . -name "libssl.a" -exec cp {} "$INSTALL/boringssl/lib/" \; && \
  find . -name "libcrypto.a" -exec cp {} "$INSTALL/boringssl/lib/" \;
cp -r "$DEPS/boringssl/include/"* "$INSTALL/boringssl/include/"

# 6. Download + patch curl
cd "$DEPS"
[ -f "curl-$CURL_VERSION.tar.xz" ] || curl -sL -o "curl-$CURL_VERSION.tar.xz" "https://curl.se/download/curl-$CURL_VERSION.tar.xz"
rm -rf "curl-$CURL_VERSION"
tar xf "curl-$CURL_VERSION.tar.xz"
CURL_SRC="$DEPS/curl-$CURL_VERSION"

# Apply base impersonate patch
cd "$CURL_SRC"
if [ -f "$SRC_PATCHES_DIR/curl-impersonate-$CURL_VERSION.patch" ]; then
  patch -p1 < "$SRC_PATCHES_DIR/curl-impersonate-$CURL_VERSION.patch" || true
fi

# Copy impersonate_register source
cp "$PATCHES_DIR/impersonate_register.c" "$PATCHES_DIR/impersonate_register.h" lib/ 2>/dev/null || true
# impersonate.h might be in different locations
for h in "$PATCHES_DIR/impersonate.h" "$ROOT/chrome/curl/lib/impersonate.h" "$SRC_PATCHES_DIR/../curl/lib/impersonate.h"; do
  [ -f "$h" ] && cp "$h" lib/ && break
done
# cJSON
for c in "$ROOT/chrome/curl/lib/cJSON.c" "$ROOT/chrome/curl/lib/cJSON.h"; do
  [ -f "$c" ] && cp "$c" lib/ && break
done

# Apply our custom patches (Python scripts are cross-platform)
python3 "$PATCHES_DIR/apply_h2_fingerprint_patch.py" "$CURL_SRC" || true
python3 "$PATCHES_DIR/apply_no_env_no_proxy.py" "$CURL_SRC" || true

# 7. Build curl as shared library
rm -rf "$BUILD/curl" && mkdir "$BUILD/curl" && cd "$BUILD/curl"
cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="$PIC" \
  -DCMAKE_INSTALL_PREFIX="$INSTALL/curl" \
  -DCMAKE_C_COMPILER=${CC:-gcc} \
  -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_WINDOWS_EXPORT_ALL_SYMBOLS=OFF \
  -DBUILD_TESTING=OFF \
  -DBUILD_CURL_EXE=OFF \
  -DCURL_USE_OPENSSL=ON \
  -DOPENSSL_ROOT_DIR="$INSTALL/boringssl" \
  -DOPENSSL_INCLUDE_DIR="$INSTALL/boringssl/include" \
  -DOPENSSL_CRYPTO_LIBRARY="$INSTALL/boringssl/lib/libcrypto.a" \
  -DOPENSSL_SSL_LIBRARY="$INSTALL/boringssl/lib/libssl.a" \
  -DZLIB_ROOT="$INSTALL/zlib" \
  -DZLIB_INCLUDE_DIR="$INSTALL/zlib/include" \
  -DZLIB_LIBRARY="$INSTALL/zlib/lib/libz.a" \
  -DCURL_BROTLI=ON \
  -DBROTLI_INCLUDE_DIR="$INSTALL/brotli/include" \
  -DBROTLICOMMON_LIBRARY="$INSTALL/brotli/lib/libbrotlicommon.a" \
  -DBROTLIDEC_LIBRARY="$INSTALL/brotli/lib/libbrotlidec.a" \
  -DBROTLIENC_LIBRARY="$INSTALL/brotli/lib/libbrotlienc.a" \
  -DCURL_ZSTD=ON \
  -DZSTD_INCLUDE_DIR="$INSTALL/zstd/include" \
  -DZSTD_LIBRARY="$INSTALL/zstd/lib/libzstd.a" \
  -DUSE_NGHTTP2=ON \
  -DNGHTTP2_INCLUDE_DIR="$INSTALL/nghttp2/include" \
  -DNGHTTP2_LIBRARY="$INSTALL/nghttp2/lib/libnghttp2.a" \
  -DNGHTTP2_STATICLIB=ON \
  -DCMAKE_SHARED_LINKER_FLAGS="-Wl,--whole-archive $INSTALL/boringssl/lib/libssl.a $INSTALL/boringssl/lib/libcrypto.a -Wl,--no-whole-archive $INSTALL/zlib/lib/libz.a $INSTALL/brotli/lib/libbrotlicommon.a $INSTALL/brotli/lib/libbrotlidec.a $INSTALL/brotli/lib/libbrotlienc.a $INSTALL/zstd/lib/libzstd.a $INSTALL/nghttp2/lib/libnghttp2.a -lpthread -ldl" \
  "$CURL_SRC"

cmake --build . --target libcurl

# 8. Copy output
LIB_OUT="$BUILD/curl/lib/libcurl-impersonate-chrome.${LIB_EXT:-so}"
[ -f "$LIB_OUT" ] || LIB_OUT=$(find "$BUILD/curl" -name "libcurl*" -name "*.so" -o -name "*.dylib" | head -1)
# Rename to our expected name
cd "$BUILD/curl/lib"
for f in libcurl.so* libcurl.dylib* libcurl-*.so* libcurl-*.dylib*; do
  [ -f "$f" ] || continue
  NEWNAME=$(echo "$f" | sed 's/libcurl/libcurl-impersonate-chrome/')
  cp "$f" "$ROOT/curl_impy/libs/${PLATFORM}/$NEWNAME" 2>/dev/null || true
done
# Fallback: just copy whatever we found
[ -f "$ROOT/curl_impy/libs/${PLATFORM}/libcurl-impersonate-chrome.${LIB_EXT:-so}" ] || \
  cp "$BUILD/curl/lib/libcurl.so" "$ROOT/curl_impy/libs/${PLATFORM}/libcurl-impersonate-chrome.so" 2>/dev/null || \
  cp "$BUILD/curl/lib/libcurl.dylib" "$ROOT/curl_impy/libs/${PLATFORM}/libcurl-impersonate-chrome.dylib" 2>/dev/null || true

echo "=== Build complete ==="
ls -la "$ROOT/curl_impy/libs/${PLATFORM}/"

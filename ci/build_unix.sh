#!/usr/bin/env bash
# CI-only build script (not shipped to users)
# Builds libcurl-impersonate-chrome.so / .dylib on Linux/macOS
set -ex

# MUST resolve to absolute path before any cd
ROOT="$(cd "${1:-.}" && pwd)"
DEPS="$ROOT/ci_deps"
BUILD="$ROOT/ci_build"
INSTALL="$ROOT/ci_install"
PATCHES="$ROOT/ci/patches"
SRC_PATCHES="$ROOT/ci/patches"
PLATFORM="${PLATFORM:-linux_x64}"
LIB_EXT="${LIB_EXT:-so}"

BORINGSSL_COMMIT="92316dc661f0a8aad68b8783889dc6a355e27735"
CURL_VERSION="8.20.0"
PIC="-fPIC -O2"

mkdir -p "$DEPS" "$BUILD" "$INSTALL" "$ROOT/curl_impy/libs/$PLATFORM"

# ============================================================================
# Helper: download and extract
# ============================================================================
download() {
  local url="$1" dest="$2"
  if [ ! -f "$dest" ]; then
    curl -sL --fail -o "$dest" "$url" || { echo "FAILED to download $url"; return 1; }
  fi
}

# ============================================================================
# 1. zlib
# ============================================================================
if [ ! -f "$INSTALL/zlib/lib/libz.a" ]; then
  echo "=== Building zlib ==="
  cd "$DEPS"
  download "https://github.com/madler/zlib/releases/download/v1.3.1/zlib-1.3.1.tar.gz" "zlib-1.3.1.tar.gz"
  [ -d "zlib-1.3.1" ] || tar xf "zlib-1.3.1.tar.gz"
  rm -rf "$BUILD/zlib" && mkdir -p "$BUILD/zlib" && cd "$BUILD/zlib"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
    -DCMAKE_INSTALL_PREFIX="$INSTALL/zlib" "$DEPS/zlib-1.3.1"
  cmake --build . && cmake --install . 2>/dev/null || true
  echo "[OK] zlib"
fi

# ============================================================================
# 2. brotli
# ============================================================================
if [ ! -f "$INSTALL/brotli/lib/libbrotlienc.a" ]; then
  echo "=== Building brotli ==="
  cd "$DEPS"
  download "https://github.com/google/brotli/archive/refs/tags/v1.0.9.tar.gz" "brotli-1.0.9.tar.gz"
  [ -d "brotli-1.0.9" ] || tar xf "brotli-1.0.9.tar.gz"
  rm -rf "$BUILD/brotli" && mkdir -p "$BUILD/brotli" && cd "$BUILD/brotli"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
    -DBUILD_SHARED_LIBS=OFF -DCMAKE_INSTALL_PREFIX="$INSTALL/brotli" "$DEPS/brotli-1.0.9"
  cmake --build . && cmake --install . 2>/dev/null || true
  echo "[OK] brotli"
fi

# ============================================================================
# 3. nghttp2
# ============================================================================
if [ ! -f "$INSTALL/nghttp2/lib/libnghttp2.a" ]; then
  echo "=== Building nghttp2 ==="
  cd "$DEPS"
  download "https://github.com/nghttp2/nghttp2/releases/download/v1.56.0/nghttp2-1.56.0.tar.bz2" "nghttp2-1.56.0.tar.bz2"
  [ -d "nghttp2-1.56.0" ] || tar xf "nghttp2-1.56.0.tar.bz2"
  rm -rf "$BUILD/nghttp2" && mkdir -p "$BUILD/nghttp2" && cd "$BUILD/nghttp2"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
    -DENABLE_SHARED_LIB=OFF -DENABLE_STATIC_LIB=ON -DENABLE_APP=OFF \
    -DENABLE_EXAMPLES=OFF -DENABLE_HPACK_TOOLS=OFF \
    -DCMAKE_INSTALL_PREFIX="$INSTALL/nghttp2" "$DEPS/nghttp2-1.56.0"
  cmake --build . && cmake --install . 2>/dev/null || true
  echo "[OK] nghttp2"
fi

# ============================================================================
# 4. zstd
# ============================================================================
if [ ! -f "$INSTALL/zstd/lib/libzstd.a" ]; then
  echo "=== Building zstd ==="
  cd "$DEPS"
  download "https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz" "zstd-1.5.7.tar.gz"
  [ -d "zstd-1.5.7" ] || tar xf "zstd-1.5.7.tar.gz"
  rm -rf "$BUILD/zstd" && mkdir -p "$BUILD/zstd" && cd "$BUILD/zstd"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
    -DZSTD_BUILD_STATIC=ON -DZSTD_BUILD_SHARED=OFF -DZSTD_BUILD_PROGRAMS=OFF \
    -DCMAKE_INSTALL_PREFIX="$INSTALL/zstd" "$DEPS/zstd-1.5.7/build/cmake"
  cmake --build . && cmake --install . 2>/dev/null || true
  echo "[OK] zstd"
fi

# ============================================================================
# 5. BoringSSL
# ============================================================================
if [ ! -f "$INSTALL/boringssl/lib/libssl.a" ]; then
  echo "=== Building BoringSSL ==="
  cd "$DEPS"
  download "https://github.com/google/boringssl/archive/$BORINGSSL_COMMIT.zip" "boringssl.zip"
  [ -d "boringssl" ] || { unzip -q boringssl.zip && mv "boringssl-$BORINGSSL_COMMIT" boringssl; }
  rm -rf "$BUILD/boringssl" && mkdir -p "$BUILD/boringssl" && cd "$BUILD/boringssl"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$PIC" -DCMAKE_CXX_FLAGS="$PIC" \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_TESTING=OFF "$DEPS/boringssl"
  cmake --build . --target ssl crypto
  mkdir -p "$INSTALL/boringssl/lib" "$INSTALL/boringssl/include"
  # BoringSSL puts .a files in build root, not ssl/ or crypto/ subdirs
  find . -name "libssl.a" -exec cp {} "$INSTALL/boringssl/lib/" \;
  find . -name "libcrypto.a" -exec cp {} "$INSTALL/boringssl/lib/" \;
  cp -r "$DEPS/boringssl/include/"* "$INSTALL/boringssl/include/"
  echo "[OK] BoringSSL"
fi

# ============================================================================
# 6. Download, patch, and build curl
# ============================================================================
echo "=== Building curl $CURL_VERSION ==="
cd "$DEPS"
download "https://curl.se/download/curl-$CURL_VERSION.tar.xz" "curl-$CURL_VERSION.tar.xz"
rm -rf "curl-$CURL_VERSION"
tar xf "curl-$CURL_VERSION.tar.xz"
CURL_SRC="$DEPS/curl-$CURL_VERSION"

# Apply base impersonate patch
cd "$CURL_SRC"
if [ -f "$PATCHES/curl-impersonate-$CURL_VERSION.patch" ]; then
  patch -p1 < "$PATCHES/curl-impersonate-$CURL_VERSION.patch" || true
fi

# Copy impersonate_register, impersonate.h, cJSON source files
cp "$PATCHES/impersonate_register.c" "$PATCHES/impersonate_register.h" lib/ 2>/dev/null || true
cp "$PATCHES/impersonate.h" lib/ 2>/dev/null || true
cp "$PATCHES/cJSON.c" "$PATCHES/cJSON.h" lib/ 2>/dev/null || true

# Apply our custom patches (Python scripts are cross-platform)
python3 "$PATCHES/apply_h2_fingerprint_patch.py" "$CURL_SRC" || true
python3 "$PATCHES/apply_no_env_no_proxy.py" "$CURL_SRC" || true

# Build curl as shared library
rm -rf "$BUILD/curl" && mkdir -p "$BUILD/curl" && cd "$BUILD/curl"

# Build linker flags: statically link all deps into the shared lib
STATIC_LIBS="$INSTALL/boringssl/lib/libssl.a $INSTALL/boringssl/lib/libcrypto.a \
$INSTALL/zlib/lib/libz.a \
$INSTALL/brotli/lib/libbrotlicommon.a $INSTALL/brotli/lib/libbrotlidec.a $INSTALL/brotli/lib/libbrotlienc.a \
$INSTALL/zstd/lib/libzstd.a \
$INSTALL/nghttp2/lib/libnghttp2.a"

cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="$PIC" \
  -DCMAKE_C_COMPILER="${CC:-gcc}" \
  -DBUILD_SHARED_LIBS=ON \
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
  -DCMAKE_SHARED_LINKER_FLAGS="-Wl,--whole-archive $STATIC_LIBS -Wl,--no-whole-archive -lpthread -ldl" \
  "$CURL_SRC"

cmake --build . --target libcurl

# Find and copy the output library
OUT_DIR="$ROOT/curl_impy/libs/$PLATFORM"
FOUND=""
for f in \
  "$BUILD/curl/lib/libcurl-impersonate-chrome.$LIB_EXT" \
  "$BUILD/curl/lib/libcurl.$LIB_EXT" \
  "$BUILD/curl/lib/libcurl-impersonate-chrome.$LIB_EXT.4" \
  "$BUILD/curl/lib/libcurl.$LIB_EXT.4"; do
  if [ -f "$f" ]; then
    cp "$f" "$OUT_DIR/"
    FOUND="$f"
    break
  fi
done

# Also copy versioned symlinks
cd "$BUILD/curl/lib"
for f in libcurl*.$LIB_EXT*; do
  [ -f "$f" ] && cp "$f" "$OUT_DIR/" 2>/dev/null || true
done

# Ensure the main file exists
if [ ! -f "$OUT_DIR/libcurl-impersonate-chrome.$LIB_EXT" ]; then
  # Rename libcurl.so to libcurl-impersonate-chrome.so
  if [ -f "$OUT_DIR/libcurl.$LIB_EXT" ]; then
    cp "$OUT_DIR/libcurl.$LIB_EXT" "$OUT_DIR/libcurl-impersonate-chrome.$LIB_EXT"
  fi
fi

echo "=== Build complete ==="
ls -la "$OUT_DIR/"

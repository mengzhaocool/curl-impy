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
PLATFORM="${PLATFORM:-linux_x64}"
LIB_EXT="${LIB_EXT:-so}"

BORINGSSL_COMMIT="92316dc661f0a8aad68b8783889dc6a355e27735"
CURL_VERSION="8.20.0"
PIC="-fPIC -O2"

# Platform-specific linker flags
OS_TYPE="$(uname -s)"
if [ "$OS_TYPE" = "Darwin" ]; then
  # macOS: no --whole-archive, no -ldl, no -lpthread
  LD_WRAP_START="-Wl,-all_load"
  LD_WRAP_END=""
  LD_EXTRA="-framework Security -framework CoreFoundation"
  export CXX="${CXX:-clang++}"
else
  # Linux
  LD_WRAP_START="-Wl,--whole-archive"
  LD_WRAP_END="-Wl,--no-whole-archive"
  LD_EXTRA="-lpthread -ldl"
fi

mkdir -p "$DEPS" "$BUILD" "$INSTALL" "$ROOT/curl_impy/libs/$PLATFORM"

# ============================================================================
# Helper: download with fallback
# ============================================================================
download() {
  local url="$1" dest="$2" alt_url="$3"
  if [ ! -f "$dest" ]; then
    curl -sL --fail -o "$dest" "$url" || {
      if [ -n "$alt_url" ]; then
        echo "Primary URL failed, trying fallback..."
        curl -sL --fail -o "$dest" "$alt_url" || { echo "FAILED to download $url and $alt_url"; return 1; }
      else
        echo "FAILED to download $url"; return 1
      fi
    }
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
# Check for either libbrotlienc.a or libbrotlienc-static.a
# Create symlinks so both names exist (FindBrotli looks for non-static name)
BROTLI_COMMON=""
BROTLI_DEC=""
BROTLI_ENC=""
if [ -d "$INSTALL/brotlib" ] || [ -d "$INSTALL/brotli" ]; then
  for lib in brotlicommon brotlidec brotlienc; do
    target="$INSTALL/brotli/lib/lib${lib}.a"
    if [ ! -f "$target" ] && [ -f "$INSTALL/brotli/lib/lib${lib}-static.a" ]; then
      ln -sf "lib${lib}-static.a" "$target"
    fi
    [ -f "$target" ] && case "$lib" in
      brotlicommon) BROTLI_COMMON="$target" ;;
      brotlidec)    BROTLI_DEC="$target" ;;
      brotlienc)    BROTLI_ENC="$target" ;;
    esac
  done
fi

if [ -z "$BROTLI_ENC" ]; then
  echo "=== Building brotli ==="
  cd "$DEPS"
  download "https://github.com/google/brotli/archive/refs/tags/v1.0.9.tar.gz" "brotli-1.0.9.tar.gz"
  [ -d "brotli-1.0.9" ] || tar xf "brotli-1.0.9.tar.gz"
  rm -rf "$BUILD/brotli" && mkdir -p "$BUILD/brotli" && cd "$BUILD/brotli"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="$PIC" \
    -DBUILD_SHARED_LIBS=OFF -DCMAKE_INSTALL_PREFIX="$INSTALL/brotli" "$DEPS/brotli-1.0.9"
  cmake --build . && cmake --install . 2>/dev/null || true
  echo "[OK] brotli"
  # Resolve actual library names + create symlinks so FindBrotli can find them
  for lib in brotlicommon brotlidec brotlienc; do
    for suffix in "" "-static"; do
      f="$INSTALL/brotli/lib/lib${lib}${suffix}.a"
      if [ -f "$f" ]; then
        # Create symlink without suffix if it doesn't exist
        target="$INSTALL/brotli/lib/lib${lib}.a"
        [ -f "$target" ] || ln -sf "lib${lib}${suffix}.a" "$target"
        # Set variable
        case "$lib" in
          brotlicommon) BROTLI_COMMON="$target" ;;
          brotlidec)    BROTLI_DEC="$target" ;;
          brotlienc)    BROTLI_ENC="$target" ;;
        esac
        break
      fi
    done
  done
fi

# ============================================================================
# 3. nghttp2
# ============================================================================
# Check for either libnghttp2.a or libnghttp2_static.a
NGHTTP2_LIB=""
if [ -f "$INSTALL/nghttp2/lib/libnghttp2.a" ]; then
  NGHTTP2_LIB="$INSTALL/nghttp2/lib/libnghttp2.a"
elif [ -f "$INSTALL/nghttp2/lib/libnghttp2_static.a" ]; then
  NGHTTP2_LIB="$INSTALL/nghttp2/lib/libnghttp2_static.a"
fi

if [ -z "$NGHTTP2_LIB" ]; then
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
  # Create symlink so FindNGHTTP2 can find it
  NGHTTP2_LIB="$INSTALL/nghttp2/lib/libnghttp2.a"
  if [ ! -f "$NGHTTP2_LIB" ]; then
    if [ -f "$INSTALL/nghttp2/lib/libnghttp2_static.a" ]; then
      ln -sf libnghttp2_static.a "$NGHTTP2_LIB"
    fi
  fi
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
  rm -rf boringssl "boringssl-$BORINGSSL_COMMIT"
  unzip -q boringssl.zip
  mv "boringssl-$BORINGSSL_COMMIT" boringssl
  rm -rf "$BUILD/boringssl" && mkdir -p "$BUILD/boringssl" && cd "$BUILD/boringssl"
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$PIC" -DCMAKE_CXX_FLAGS="$PIC" \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_TESTING=OFF "$DEPS/boringssl"
  cmake --build . --target ssl crypto
  mkdir -p "$INSTALL/boringssl/lib" "$INSTALL/boringssl/include"
  # BoringSSL puts .a files in build root
  find . -name "libssl.a" | head -1 | xargs -I{} cp {} "$INSTALL/boringssl/lib/"
  find . -name "libcrypto.a" | head -1 | xargs -I{} cp {} "$INSTALL/boringssl/lib/"
  # Verify
  [ -f "$INSTALL/boringssl/lib/libssl.a" ] || { echo "ERROR: libssl.a not found after BoringSSL build"; exit 1; }
  [ -f "$INSTALL/boringssl/lib/libcrypto.a" ] || { echo "ERROR: libcrypto.a not found after BoringSSL build"; exit 1; }
  cp -r "$DEPS/boringssl/include/"* "$INSTALL/boringssl/include/"
  echo "[OK] BoringSSL"
fi

# ============================================================================
# 6. Download, patch, and build curl
# ============================================================================
echo "=== Building curl $CURL_VERSION ==="
cd "$DEPS"
# Use curl.se primary, GitHub mirror as fallback
download "https://curl.se/download/curl-$CURL_VERSION.tar.xz" "curl-$CURL_VERSION.tar.xz" \
         "https://github.com/curl/curl/releases/download/curl_${CURL_VERSION//./_}/curl-$CURL_VERSION.tar.xz"
rm -rf "curl-$CURL_VERSION"
tar xf "curl-$CURL_VERSION.tar.xz"
CURL_SRC="$DEPS/curl-$CURL_VERSION"

# Apply base impersonate patch (fail hard if it doesn't apply)
cd "$CURL_SRC"
if [ -f "$PATCHES/curl-impersonate-$CURL_VERSION.patch" ]; then
  patch -p1 < "$PATCHES/curl-impersonate-$CURL_VERSION.patch"
  echo "[OK] Base impersonate patch applied"
fi

# Copy source files into lib/ directory
cp "$PATCHES/impersonate.c" lib/
cp "$PATCHES/impersonate_register.c" "$PATCHES/impersonate_register.h" lib/
cp "$PATCHES/impersonate.h" lib/
cp "$PATCHES/cJSON.c" "$PATCHES/cJSON.h" lib/

# Apply our custom patches (fail hard if they fail)
python3 "$PATCHES/apply_h2_fingerprint_patch.py" "$CURL_SRC"
python3 "$PATCHES/apply_no_env_no_proxy.py" "$CURL_SRC"
echo "[OK] All patches applied"

# Fix: base patch uses strcasecompare/Curl_safefree/aprintf macros (from
# impersonate.h) in multiple .c files without including impersonate.h.
# MSVC has these as built-in, gcc doesn't. Force-include impersonate.h globally.
# Also remove conflicting curl_easy_impersonate decl from easy.h (CURL* vs struct Curl_easy*)
python3 -c "
f = 'include/curl/easy.h'
with open(f, 'r') as fh: c = fh.read()
import re
# Remove the 2-line declaration
c = re.sub(r'CURL_EXTERN CURLcode curl_easy_impersonate\(CURL \*curl.*?default_headers\);', '', c, flags=re.DOTALL)
with open(f, 'w') as fh: fh.write(c)
"
echo "[OK] Removed conflicting decl from easy.h"

# Fix: base patch uses strcasecompare/strncasecompare/Curl_safefree/aprintf macros
# (defined in impersonate.h) in multiple .c files without including impersonate.h.
# MSVC has these built-in, gcc doesn't. Add #include "impersonate.h" to each file that needs it.
python3 -c "
import os, re

macros = ['strcasecompare', 'strncasecompare', 'Curl_safefree', 'aprintf']
lib_dir = 'lib'
vtls_dir = 'lib/vtls'
count = 0

for d in [lib_dir, vtls_dir]:
    if not os.path.isdir(d): continue
    for fname in os.listdir(d):
        if not fname.endswith('.c'): continue
        fpath = os.path.join(d, fname)
        with open(fpath, 'r', errors='replace') as f: content = f.read()
        if 'impersonate.h' in content: continue
        needs = False
        for macro in macros:
            if re.search(r'\b' + macro + r'\b', content):
                needs = True
                break
        if not needs: continue
        lines = content.split('\n')
        last_include = 0
        for i, line in enumerate(lines):
            if line.startswith('#include'): last_include = i
        lines.insert(last_include + 1, '#include \"impersonate.h\"')
        with open(fpath, 'w') as f: f.write('\n'.join(lines))
        count += 1
        print(f'  Added #include to {d}/{fname}')
print(f'[OK] Added impersonate.h to {count} files')
"

# Add forward declaration for Curl_http_merge_headers (called before defined in http.c)
python3 -c "
f = 'lib/http.c'
with open(f, 'r') as fh: c = fh.read()
if 'CURLcode Curl_http_merge_headers(struct Curl_easy *data);' not in c:
    c = c.replace('#include \"http.h\"', '#include \"http.h\"\nCURLcode Curl_http_merge_headers(struct Curl_easy *data);', 1)
    with open(f, 'w') as fh: fh.write(c)
    print('[OK] Forward declaration added to http.c')
else:
    print('[OK] Forward declaration already in http.c')
"

# ============================================================================
# 7. Build curl as shared library
# ============================================================================
rm -rf "$BUILD/curl" && mkdir -p "$BUILD/curl" && cd "$BUILD/curl"

# Static libraries to link into the shared lib (use resolved paths)
STATIC_LIBS="$INSTALL/boringssl/lib/libssl.a $INSTALL/boringssl/lib/libcrypto.a \
$INSTALL/zlib/lib/libz.a \
$BROTLI_COMMON $BROTLI_DEC $BROTLI_ENC \
$INSTALL/zstd/lib/libzstd.a \
$NGHTTP2_LIB"

cmake -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_FLAGS="$PIC -Wno-error -Wno-error=implicit-function-declaration" \
  -DCMAKE_C_COMPILER="${CC:-gcc}" \
  -DCMAKE_CXX_COMPILER="${CXX:-g++}" \
  -DCMAKE_PREFIX_PATH="$INSTALL/boringssl;$INSTALL/zlib;$INSTALL/brotli;$INSTALL/zstd;$INSTALL/nghttp2" \
  -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=OFF \
  -DBUILD_CURL_EXE=OFF \
  -DCURL_PICKY_COMPILER=OFF \
  -DCURL_USE_OPENSSL=ON \
  -DOPENSSL_ROOT_DIR="$INSTALL/boringssl" \
  -DOPENSSL_INCLUDE_DIR="$INSTALL/boringssl/include" \
  -DOPENSSL_CRYPTO_LIBRARY="$INSTALL/boringssl/lib/libcrypto.a" \
  -DOPENSSL_SSL_LIBRARY="$INSTALL/boringssl/lib/libssl.a" \
  -DOPENSSL_USE_STATIC_LIBS=ON \
  -DZLIB_ROOT="$INSTALL/zlib" \
  -DZLIB_INCLUDE_DIR="$INSTALL/zlib/include" \
  -DZLIB_LIBRARY="$INSTALL/zlib/lib/libz.a" \
  -DCURL_BROTLI=ON \
  -DBROTLI_INCLUDE_DIR="$INSTALL/brotli/include" \
  -DBROTLICOMMON_LIBRARY="$BROTLI_COMMON" \
  -DBROTLIDEC_LIBRARY="$BROTLI_DEC" \
  -DBROTLIENC_LIBRARY="$BROTLI_ENC" \
  -DCURL_ZSTD=ON \
  -DZSTD_INCLUDE_DIR="$INSTALL/zstd/include" \
  -DZSTD_LIBRARY="$INSTALL/zstd/lib/libzstd.a" \
  -DUSE_NGHTTP2=ON \
  -DNGHTTP2_INCLUDE_DIR="$INSTALL/nghttp2/include" \
  -DNGHTTP2_LIBRARY="$NGHTTP2_LIB" \
  -DCURL_USE_LIBPSL=OFF \
  -DCURL_USE_LIBIDN2=OFF \
  -DCURL_USE_LIBSSH2=OFF \
  -DCURL_USE_LIBRTMP=OFF \
  -DCURL_DISABLE_LDAP=ON \
  -DCMAKE_SHARED_LINKER_FLAGS="$LD_WRAP_START $STATIC_LIBS $LD_WRAP_END $LD_EXTRA" \
  "$CURL_SRC"

# Build (target is libcurl_shared for shared library build)
cmake --build . --target libcurl_shared || cmake --build .

# ============================================================================
# 8. Copy output library
# ============================================================================
OUT_DIR="$ROOT/curl_impy/libs/$PLATFORM"
mkdir -p "$OUT_DIR"

# Find the built library (check multiple name patterns)
BUILT_LIB=""
for pattern in \
  "$BUILD/curl/lib/libcurl-impersonate-chrome.$LIB_EXT" \
  "$BUILD/curl/lib/libcurl-impersonate-chrome.$LIB_EXT.*" \
  "$BUILD/curl/lib/libcurl.$LIB_EXT" \
  "$BUILD/curl/lib/libcurl.$LIB_EXT.*"; do
  for f in $pattern; do
    if [ -f "$f" ]; then
      BUILT_LIB="$f"
      break 2
    fi
  done
done

if [ -z "$BUILT_LIB" ]; then
  echo "ERROR: Built library not found. Searching..."
  find "$BUILD/curl" -name "*.$LIB_EXT" -type f
  exit 1
fi

echo "Found: $BUILT_LIB"

# Copy the actual file (resolve symlinks)
cp -L "$BUILT_LIB" "$OUT_DIR/libcurl-impersonate-chrome.$LIB_EXT"

# Also copy versioned symlinks if they exist
cd "$(dirname "$BUILT_LIB")"
for f in libcurl*.so* libcurl*.dylib*; do
  [ -f "$f" ] && [ "$f" != "$(basename $BUILT_LIB)" ] && cp -L "$f" "$OUT_DIR/" 2>/dev/null || true
done

echo "=== Build complete ==="
ls -la "$OUT_DIR/"

#!/usr/bin/env python3
# patch_cmake_dll.py - Patch curl's lib/CMakeLists.txt for DLL export
# Adds /WHOLEARCHIVE linking for all dependency static libraries so all
# symbols are exported in the combined DLL.
#
# IMPORTANT: We use target_link_options with /WHOLEARCHIVE: prefix because
# $<LINK_LIBRARY:WHOLE_ARCHIVE,...> generates GCC-style --whole-archive
# flags that MSVC link.exe does not understand.
#
# The WHOLEARCHIVE code must be placed BEFORE the ALIAS definition
# (add_library ${LIB_NAME} ALIAS ${LIB_SELECTED}) because target_link_options
# cannot be called on ALIAS targets. We use ${LIB_SHARED} directly.

import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python patch_cmake_dll.py <cmakelists_path>")
        sys.exit(1)

    cmake_path = sys.argv[1]

    if not os.path.isfile(cmake_path):
        print(f"[ERROR] File not found: {cmake_path}")
        sys.exit(1)

    with open(cmake_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Check if already patched
    if 'wholearchive_patched' in content:
        print('[cmake-patch] Already patched, skipping')
        sys.exit(0)

    # Find the line: target_link_libraries(${LIB_SHARED} PRIVATE ${CURL_LIBS})
    # Insert WHOLEARCHIVE code AFTER this line (inside the shared lib block,
    # BEFORE the ALIAS definition)
    shared_link_anchor = 'target_link_libraries(${LIB_SHARED} PRIVATE ${CURL_LIBS})'

    if shared_link_anchor not in content:
        print('[ERROR] Could not find anchor for shared lib link line')
        sys.exit(1)

    # The WHOLEARCHIVE patch - uses target_link_options with /WHOLEARCHIVE: prefix
    # This is the MSVC-compatible way to force-link all symbols from static libraries.
    wholearchive_patch = """
  # [wholearchive_patched] Force link all dependency static libraries with /WHOLEARCHIVE
  # This ensures ALL symbols from BoringSSL, zlib, brotli, nghttp2, ngtcp2, nghttp3, zstd, libssh2
  # are included in the DLL, not just the ones referenced by curl.
  # NOTE: We use target_link_options with /WHOLEARCHIVE: because
  # $<LINK_LIBRARY:WHOLE_ARCHIVE,...> generates GCC-style --whole-archive flags
  # that MSVC link.exe does not understand.
  if(WIN32)
    set(_wholearchive_libs "")

    # BoringSSL
    if(OPENSSL_LIBRARIES)
      foreach(_ssl_lib ${OPENSSL_LIBRARIES})
        if(EXISTS "${_ssl_lib}")
          list(APPEND _wholearchive_libs "${_ssl_lib}")
        endif()
      endforeach()
    endif()

    # NOTE: libssh2 is NOT included here.
    # libssh2 is disabled (CURL_USE_LIBSSH2=OFF).

    # zstd (has 291 symbols in .def file)
    # Previously excluded due to __imp_clock/__imp_qsort_s errors, but
    # those were resolved by building with /MT (static CRT).
    if(ZSTD_LIBRARY AND EXISTS "${ZSTD_LIBRARY}")
      list(APPEND _wholearchive_libs "${ZSTD_LIBRARY}")
    endif()

    # zlib (has 71 symbols in .def file)
    if(ZLIB_LIBRARY AND EXISTS "${ZLIB_LIBRARY}")
      list(APPEND _wholearchive_libs "${ZLIB_LIBRARY}")
    endif()

    # brotli - all three libraries (has 37 symbols in .def file)
    if(CURL_BROTLI AND BROTLIDEC_LIBRARY)
      get_filename_component(_brotli_lib_dir "${BROTLIDEC_LIBRARY}" DIRECTORY)
      find_library(BROTLI_ENC_LIB brotlienc PATHS "${_brotli_lib_dir}" NO_DEFAULT_PATH)
      find_library(BROTLI_DEC_LIB brotlidec PATHS "${_brotli_lib_dir}" NO_DEFAULT_PATH)
      find_library(BROTLI_COMMON_LIB brotlicommon PATHS "${_brotli_lib_dir}" NO_DEFAULT_PATH)
      if(BROTLI_ENC_LIB AND EXISTS "${BROTLI_ENC_LIB}")
        list(APPEND _wholearchive_libs "${BROTLI_ENC_LIB}")
      endif()
      if(BROTLI_DEC_LIB AND EXISTS "${BROTLI_DEC_LIB}")
        list(APPEND _wholearchive_libs "${BROTLI_DEC_LIB}")
      endif()
      if(BROTLI_COMMON_LIB AND EXISTS "${BROTLI_COMMON_LIB}")
        list(APPEND _wholearchive_libs "${BROTLI_COMMON_LIB}")
      endif()
    endif()

    # nghttp2
    if(NGHTTP2_LIBRARY AND EXISTS "${NGHTTP2_LIBRARY}")
      list(APPEND _wholearchive_libs "${NGHTTP2_LIBRARY}")
    endif()

    # ngtcp2 + crypto
    if(NGTCP2_LIBRARY AND EXISTS "${NGTCP2_LIBRARY}")
      list(APPEND _wholearchive_libs "${NGTCP2_LIBRARY}")
    endif()
    if(NGTCP2_CRYPTO_BORINGSSL_LIBRARY AND EXISTS "${NGTCP2_CRYPTO_BORINGSSL_LIBRARY}")
      list(APPEND _wholearchive_libs "${NGTCP2_CRYPTO_BORINGSSL_LIBRARY}")
    endif()

    # nghttp3
    if(NGHTTP3_LIBRARY AND EXISTS "${NGHTTP3_LIBRARY}")
      list(APPEND _wholearchive_libs "${NGHTTP3_LIBRARY}")
    endif()

    # Apply /WHOLEARCHIVE: for each dependency library (MSVC format)
    foreach(_lib ${_wholearchive_libs})
      target_link_options(${LIB_SHARED} PRIVATE "/WHOLEARCHIVE:${_lib}")
    endforeach()

    # Disable /OPT:REF and /OPT:ICF to prevent the linker from removing
    # any unreferenced code/data from WHOLEARCHIVE libraries. Without this,
    # MSVC still strips unused functions even though the object files are
    # included by /WHOLEARCHIVE, resulting in a much smaller DLL missing
    # most of BoringSSL and other dependency code.
    target_link_options(${LIB_SHARED} PRIVATE "/OPT:NOREF" "/OPT:NOICF")

    message(STATUS "DLL /WHOLEARCHIVE linking: ${_wholearchive_libs}")
    message(STATUS "DLL /OPT:NOREF /OPT:NOICF enabled (no dead code elimination)")
  endif()
"""

    # Insert the patch after the shared lib target_link_libraries line
    content = content.replace(
        shared_link_anchor,
        shared_link_anchor + wholearchive_patch,
        1
    )
    print('[cmake-patch] Added /WHOLEARCHIVE linking for shared library')

    if content != original:
        with open(cmake_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print('[cmake-patch] CMakeLists.txt patched successfully')
    else:
        print('[cmake-patch] No patches applied')

    sys.exit(0)


if __name__ == '__main__':
    main()

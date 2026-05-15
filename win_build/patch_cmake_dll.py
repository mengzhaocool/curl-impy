#!/usr/bin/env python3
# patch_cmake_dll.py - Patch curl's lib/CMakeLists.txt for DLL export
# Adds .def file linking and forces static linking of all brotli libraries
# Usage: python patch_cmake_dll.py <cmakelists_path> <brotli_lib_dir>

import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python patch_cmake_dll.py <cmakelists_path> [brotli_lib_dir]")
        sys.exit(1)

    cmake_path = sys.argv[1]
    brotli_lib_dir = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(cmake_path):
        print(f"[ERROR] File not found: {cmake_path}")
        sys.exit(1)

    with open(cmake_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    patched = False

    # 1. Add .def file linking for DLL export
    if '/DEF:' not in content and 'libcurl-impersonate.def' not in content:
        def_patch = """
# Multi-in-one DLL: link .def file for exporting all symbols
if(WIN32 AND BUILD_SHARED_LIBS AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/libcurl-impersonate.def")
  set_target_properties(${LIB_NAME} PROPERTIES
    LINK_FLAGS "/DEF:\\"${CMAKE_CURRENT_SOURCE_DIR}/libcurl-impersonate.def\\""
  )
endif()
"""
        anchor = 'target_link_libraries(${LIB_NAME} PRIVATE ${CURL_LIBS})'
        if anchor in content:
            content = content.replace(anchor, def_patch + '\n' + anchor, 1)
            print('[cmake-patch] Added .def file linking')
            patched = True
        else:
            print('[WARN] Could not find anchor for .def file patch')

    # 2. Force link all dependency static libraries with /WHOLEARCHIVE
    # This ensures ALL symbols from BoringSSL, zlib, brotli, nghttp2 are
    # included in the DLL, not just the ones referenced by curl.
    if 'WHOLEARCHIVE' not in content:
        wholearchive_patch = """
# Multi-in-one DLL: force link all dependency static libraries with /WHOLEARCHIVE
# This ensures all symbols from BoringSSL, zlib, brotli, nghttp2 are exported
if(WIN32 AND BUILD_SHARED_LIBS)
  # BoringSSL - link with /WHOLEARCHIVE to export all symbols
  if(OPENSSL_LIBRARIES)
    foreach(_ssl_lib ${OPENSSL_LIBRARIES})
      if(EXISTS "${_ssl_lib}")
        target_link_libraries(${LIB_NAME} PRIVATE "$<LINK_LIBRARY:WHOLE_ARCHIVE,${_ssl_lib}>")
      endif()
    endforeach()
  endif()

  # zlib
  if(ZLIB_LIBRARY AND EXISTS "${ZLIB_LIBRARY}")
    target_link_libraries(${LIB_NAME} PRIVATE "$<LINK_LIBRARY:WHOLE_ARCHIVE,${ZLIB_LIBRARY}>")
  endif()

  # brotli - all three libraries
  if(CURL_BROTLI AND BROTLI_INCLUDE_DIR)
    get_filename_component(_brotli_lib_dir "${BROTLI_INCLUDE_DIR}/../lib" ABSOLUTE)
    find_library(BROTLI_ENC_LIB brotlienc-static PATHS "${_brotli_lib_dir}" NO_DEFAULT_PATH)
    find_library(BROTLI_DEC_LIB brotlidec-static PATHS "${_brotli_lib_dir}" NO_DEFAULT_PATH)
    find_library(BROTLI_COMMON_LIB brotlicommon-static PATHS "${_brotli_lib_dir}" NO_DEFAULT_PATH)
    if(BROTLI_ENC_LIB AND EXISTS "${BROTLI_ENC_LIB}")
      target_link_libraries(${LIB_NAME} PRIVATE "$<LINK_LIBRARY:WHOLE_ARCHIVE,${BROTLI_ENC_LIB}>")
    endif()
    if(BROTLI_DEC_LIB AND EXISTS "${BROTLI_DEC_LIB}")
      target_link_libraries(${LIB_NAME} PRIVATE "$<LINK_LIBRARY:WHOLE_ARCHIVE,${BROTLI_DEC_LIB}>")
    endif()
    if(BROTLI_COMMON_LIB AND EXISTS "${BROTLI_COMMON_LIB}")
      target_link_libraries(${LIB_NAME} PRIVATE "$<LINK_LIBRARY:WHOLE_ARCHIVE,${BROTLI_COMMON_LIB}>")
    endif()
  endif()

  # nghttp2
  if(NGHTTP2_LIBRARY AND EXISTS "${NGHTTP2_LIBRARY}")
    target_link_libraries(${LIB_NAME} PRIVATE "$<LINK_LIBRARY:WHOLE_ARCHIVE,${NGHTTP2_LIBRARY}>")
  endif()
endif()
"""
        anchor = 'target_link_libraries(${LIB_NAME} PRIVATE ${CURL_LIBS})'
        if anchor in content:
            content = content.replace(anchor, wholearchive_patch + '\n' + anchor, 1)
            print('[cmake-patch] Added /WHOLEARCHIVE linking for all dependencies')
            patched = True
        else:
            content += wholearchive_patch
            print('[cmake-patch] Added /WHOLEARCHIVE linking (append)')
            patched = True

    if content != original:
        with open(cmake_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print('[cmake-patch] CMakeLists.txt patched successfully')
    else:
        print('[cmake-patch] No patches needed (already patched or anchors not found)')

    sys.exit(0)


if __name__ == '__main__':
    main()

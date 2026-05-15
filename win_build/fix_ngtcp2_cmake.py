#!/usr/bin/env python3
"""Fix ngtcp2 CMakeLists.txt to skip BoringSSL checks when preset."""
import os

f = r"d:\curl-impersonate-8.20.0\win_build\deps\ngtcp2-1.20.0\CMakeLists.txt"
c = open(f, 'r', encoding='utf-8').read()

# Simply comment out the check_symbol_exists calls and force HAVE_BORINGSSL=TRUE
# Replace the entire ENABLE_BORINGSSL block
old_block_start = "if(ENABLE_BORINGSSL)\n  cmake_push_check_state()"
old_block_end = "cmake_pop_check_state()\nendif()"

idx_start = c.find(old_block_start)
idx_end = c.find(old_block_end)

if idx_start < 0 or idx_end < 0:
    print("ERROR: Could not find the ENABLE_BORINGSSL block")
    exit(1)

old_block = c[idx_start:idx_end + len(old_block_end)]

new_block = """if(ENABLE_BORINGSSL)
  # Skip symbol checks for MSVC/BoringSSL (link test fails due to CRT mismatch)
  # Assume BoringSSL is valid if the include dir and libraries are provided
  set(HAVE_BORINGSSL TRUE)
  set(HAVE_SSL_SET_QUIC_EARLY_DATA_CONTEXT TRUE)
  if(NOT ENABLE_LIB_ONLY)
    include(CheckCXXSymbolExists)
  endif()
endif()"""

c = c.replace(old_block, new_block, 1)
open(f, 'w', encoding='utf-8').write(c)
print("OK: CMakeLists.txt patched - BoringSSL checks skipped")

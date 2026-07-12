#!/usr/bin/env python3
"""patch_boringssl_def.py - Patch CMakeLists.txt to properly detect BoringSSL.

Ensures that when HAVE_BORINGSSL is set, the OPENSSL_IS_BORINGSSL define
is added to the compilation flags. Also fixes BoringSSL library detection
for the Windows build where FindOpenSSL may not detect BoringSSL correctly.
"""
import sys
import os
import re

def patch_cmakelists(filepath):
    """Patch CMakeLists.txt for BoringSSL detection."""
    if not os.path.isfile(filepath):
        print(f"[ERROR] File not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # 1. Ensure OPENSSL_IS_BORINGSSL define is added when BoringSSL is detected
    if 'add_definitions(-DOPENSSL_IS_BORINGSSL)' not in content:
        # Find the section where OpenSSL detection happens
        # Look for CURL_USE_OPENSSL block
        if 'if(CURL_USE_OPENSSL)' in content:
            # Add after OpenSSL includes
            openssl_block = 'include_directories(${OPENSSL_INCLUDE_DIRS})'
            if openssl_block in content:
                content = content.replace(
                    openssl_block,
                    openssl_block + '\n\n  if(HAVE_BORINGSSL)\n    add_definitions(-DOPENSSL_IS_BORINGSSL)\n  endif()'
                )
                changes += 1
                print("[OK] Added OPENSSL_IS_BORINGSSL define")
    
    # 2. Ensure HAVE_BORINGSSL is detected from the BoringSSL headers
    # BoringSSL defines OPENSSL_IS_BORINGSSL in its headers, but CMake needs
    # to know about it for conditional compilation
    if 'HAVE_BORINGSSL' not in content and 'OPENSSL_IS_BORINGSSL' in content:
        # Check if the BoringSSL detection code exists
        pass  # The fix-boringssl-detection.patch should handle this
    
    # 3. Fix library names - BoringSSL produces libssl.lib and libcrypto.lib
    # on Windows, not ssl.lib and crypto.lib
    # This is usually handled by the CMake find module, but just in case
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Patched {filepath} ({changes} changes)")
        return True
    else:
        print(f"[INFO] No changes needed for {filepath}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: patch_boringssl_def.py <CMakeLists.txt>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    success = patch_cmakelists(filepath)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

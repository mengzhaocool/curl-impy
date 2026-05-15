#!/usr/bin/env python3
"""Fix installed BoringSSL opensslv.h to add version macros."""
import os

f = r"d:\curl-impersonate-8.20.0\win_build\install\boringssl\include\openssl\opensslv.h"
c = open(f, 'r').read()

if 'OPENSSL_VERSION_NUMBER' not in c:
    version_add = """/* Added for CMake FindOpenSSL compatibility */
#ifndef OPENSSL_VERSION_NUMBER
#define OPENSSL_VERSION_NUMBER 0x30300000L
#endif
#ifndef OPENSSL_VERSION_TEXT
#define OPENSSL_VERSION_TEXT "BoringSSL"
#endif
#ifndef OPENSSL_VERSION
#define OPENSSL_VERSION OPENSSL_VERSION_NUMBER
#endif

"""
    if '#include' in c:
        idx = c.find('#include')
        c = c[:idx] + version_add + c[idx:]
    open(f, 'w').write(c)
    print("OK: Installed opensslv.h patched")
else:
    print("Already has version macros")

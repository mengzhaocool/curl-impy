#!/usr/bin/env python3
"""Fix BoringSSL compilation errors for MSVC."""
import os

BORINGSSL_DIR = os.environ.get(
    "BORINGSSL_SRC_DIR",
    os.path.join(os.path.dirname(__file__), "..", "deps", "boringssl")
)

# Fix 1: handshake_client.cc - Span conversion error
# Replace the ternary chain that uses Span with explicit Span construction
hc_file = os.path.join(BORINGSSL_DIR, "ssl", "handshake_client.cc")
if os.path.isfile(hc_file):
    c = open(hc_file, 'r', encoding='utf-8', errors='replace').read()
    
    # Replace the Span initialization with explicit construction
    old = """    const bssl::Span<const uint16_t> ciphers =
      order == nullptr ?
        kCiphersAESHardware :
        strncmp(order, "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256", TLS13_CIPHER_LEN) == 0 ?
          kCiphersAESHardware :
        strncmp(order, "TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_256_GCM_SHA384", TLS13_CIPHER_LEN) == 0 ?
          kCiphersFirefox :
        strncmp(order, "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256", TLS13_CIPHER_LEN) == 0 ?
          kCiphersSafari26 :
        strncmp(order, "TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256", TLS13_CIPHER_LEN) == 0 ?
          kCiphersCNSA :
        strncmp(order, "TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384", TLS13_CIPHER_LEN) == 0 ?
          kCiphersNoAESHardware :
        strncmp(order, "TLS_CHACHA20_POLY1305_SHA256:TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256", TLS13_CIPHER_LEN) == 0 ?
          kCiphersOther :
          kCiphersAESHardware;  // default one"""
    
    new = """    const uint16_t *ciphers_ptr;
    size_t ciphers_len;
    if (order == nullptr) {
      ciphers_ptr = kCiphersAESHardware;
      ciphers_len = sizeof(kCiphersAESHardware) / sizeof(kCiphersAESHardware[0]);
    } else if (strncmp(order, "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256", TLS13_CIPHER_LEN) == 0) {
      ciphers_ptr = kCiphersAESHardware;
      ciphers_len = sizeof(kCiphersAESHardware) / sizeof(kCiphersAESHardware[0]);
    } else if (strncmp(order, "TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_256_GCM_SHA384", TLS13_CIPHER_LEN) == 0) {
      ciphers_ptr = kCiphersFirefox;
      ciphers_len = sizeof(kCiphersFirefox) / sizeof(kCiphersFirefox[0]);
    } else if (strncmp(order, "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256", TLS13_CIPHER_LEN) == 0) {
      ciphers_ptr = kCiphersSafari26;
      ciphers_len = sizeof(kCiphersSafari26) / sizeof(kCiphersSafari26[0]);
    } else if (strncmp(order, "TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256", TLS13_CIPHER_LEN) == 0) {
      ciphers_ptr = kCiphersCNSA;
      ciphers_len = sizeof(kCiphersCNSA) / sizeof(kCiphersCNSA[0]);
    } else if (strncmp(order, "TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384", TLS13_CIPHER_LEN) == 0) {
      ciphers_ptr = kCiphersNoAESHardware;
      ciphers_len = sizeof(kCiphersNoAESHardware) / sizeof(kCiphersNoAESHardware[0]);
    } else if (strncmp(order, "TLS_CHACHA20_POLY1305_SHA256:TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256", TLS13_CIPHER_LEN) == 0) {
      ciphers_ptr = kCiphersOther;
      ciphers_len = sizeof(kCiphersOther) / sizeof(kCiphersOther[0]);
    } else {
      ciphers_ptr = kCiphersAESHardware;
      ciphers_len = sizeof(kCiphersAESHardware) / sizeof(kCiphersAESHardware[0]);
    }
    bssl::Span<const uint16_t> ciphers(ciphers_ptr, ciphers_len);"""
    
    if old in c:
        c = c.replace(old, new, 1)
        open(hc_file, 'w', encoding='utf-8').write(c)
        print("OK: handshake_client.cc patched - Span conversion fix")
    else:
        print("WARN: old string not found in handshake_client.cc (may already be patched)")
else:
    print("SKIP: handshake_client.cc not found")

# Fix 2: extensions.cc - strdup deprecation warning
ext_file = os.path.join(BORINGSSL_DIR, "ssl", "extensions.cc")
if os.path.isfile(ext_file):
    c = open(ext_file, 'r', encoding='utf-8', errors='replace').read()
    # Add _CRT_NONSTDC_NO_DEPRECATE at the top
    if '_CRT_NONSTDC_NO_DEPRECATE' not in c:
        # Add after the first #include or at the top
        if '#include' in c:
            idx = c.find('#include')
            c = c[:idx] + '#define _CRT_NONSTDC_NO_DEPRECATE\n' + c[idx:]
            open(ext_file, 'w', encoding='utf-8').write(c)
            print("OK: extensions.cc patched - _CRT_NONSTDC_NO_DEPRECATE added")
        else:
            print("WARN: No #include found in extensions.cc")
    else:
        print("OK: extensions.cc already has _CRT_NONSTDC_NO_DEPRECATE")
else:
    print("SKIP: extensions.cc not found")

# Fix 3: Add standard OpenSSL version macros to opensslv.h for CMake FindOpenSSL
ovh_file = os.path.join(BORINGSSL_DIR, "include", "openssl", "opensslv.h")
if os.path.isfile(ovh_file):
    c = open(ovh_file, 'r', encoding='utf-8', errors='replace').read()
    if 'OPENSSL_VERSION_NUMBER' not in c:
        # Add version macros before the last #include
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
        # Insert after the license header, before the #include
        if '#include' in c:
            idx = c.find('#include')
            c = c[:idx] + version_add + c[idx:]
        else:
            c = version_add + c
        open(ovh_file, 'w', encoding='utf-8').write(c)
        print("OK: opensslv.h patched - OpenSSL version macros added")
    else:
        print("OK: opensslv.h already has version macros")
else:
    print("SKIP: opensslv.h not found")

print("\nDone. BoringSSL MSVC fixes applied.")

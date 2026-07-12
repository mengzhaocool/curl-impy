#!/usr/bin/env python3
"""
Test Chrome144 impersonation against https://120.26.33.71/json/detail
Uses ctypes to load libcurl-impersonate.dll and call impersonate APIs.
"""
import ctypes
import ctypes.wintypes
import json
import os
import sys

# Load DLL
dll_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
dll_path = os.path.join(dll_dir, "libcurl-impersonate.dll")
print(f"Loading DLL: {dll_path}")
dll = ctypes.WinDLL(dll_path)

# Function prototypes
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_easy_init.argtypes = []

dll.curl_easy_cleanup.restype = None
dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]

# curl_easy_setopt is variadic - use ctypes c_void_p for string/ptr args
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_setopt.argtypes = None  # variadic

def setopt_str(curl, opt, val):
    return dll.curl_easy_setopt(ctypes.c_void_p(curl), ctypes.c_int(opt), ctypes.c_char_p(val))

def setopt_long(curl, opt, val):
    return dll.curl_easy_setopt(ctypes.c_void_p(curl), ctypes.c_int(opt), ctypes.c_long(val))

def setopt_func(curl, opt, callback):
    return dll.curl_easy_setopt(ctypes.c_void_p(curl), ctypes.c_int(opt), callback)

dll.curl_easy_perform.restype = ctypes.c_int
dll.curl_easy_perform.argtypes = [ctypes.c_void_p]

dll.curl_easy_getinfo.restype = ctypes.c_int
dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

dll.curl_easy_impersonate.restype = ctypes.c_int
dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

dll.curl_easy_impersonate_register.restype = ctypes.c_int
dll.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]

dll.curl_version.restype = ctypes.c_char_p
dll.curl_version.argtypes = []

dll.curl_global_init.restype = ctypes.c_int
dll.curl_global_init.argtypes = [ctypes.c_long]

# Constants
CURLOPT_URL = 10002
CURLOPT_WRITEFUNCTION = 20011
CURLOPT_FOLLOWLOCATION = 52
CURLOPT_SSL_VERIFYPEER = 64
CURLOPT_SSL_VERIFYHOST = 81
CURLOPT_HEADER = 58
CURLOPT_NOBODY = 44
CURLINFO_RESPONSE_CODE = 0x200002

WRITE_CALLBACK = ctypes.CFUNCTYPE(
    ctypes.c_int,        # return
    ctypes.c_char_p,     # ptr
    ctypes.c_int,        # size
    ctypes.c_int         # nmemb
)

response_data = bytearray()
def write_callback(ptr, size, nmemb):
    length = size * nmemb
    response_data.extend(ptr[:length])
    return length

cb = WRITE_CALLBACK(write_callback)

# Init
print(f"curl version: {dll.curl_version().decode()}")
dll.curl_global_init(3)  # CURL_GLOBAL_ALL

# Read Chrome144.json
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Chrome144.json")
with open(json_path, "r", encoding="utf-8") as f:
    json_content = f.read()
print(f"Chrome144.json loaded: {len(json_content)} bytes")

# Register Chrome144 impersonation
print("\n=== Registering chrome144 impersonation ===")
ret = dll.curl_easy_impersonate_register(b"chrome144", json_content.encode("utf-8"))
print(f"curl_easy_impersonate_register result: {ret}")
if ret != 0:
    print("ERROR: Registration failed!")
    sys.exit(1)

# Create easy handle
curl = dll.curl_easy_init()
if not curl:
    print("ERROR: curl_easy_init() returned NULL")
    sys.exit(1)

# Apply impersonation
print("\n=== Applying chrome144 impersonation ===")
ret = dll.curl_easy_impersonate(curl, b"chrome144", 1)  # headers=1
print(f"curl_easy_impersonate result: {ret}")
if ret != 0:
    print("ERROR: Impersonation failed!")
    dll.curl_easy_cleanup(curl)
    sys.exit(1)

# Set URL
url = b"https://120.26.33.71/json/detail"
setopt_str(curl, CURLOPT_URL, url)
setopt_func(curl, CURLOPT_WRITEFUNCTION, cb)
setopt_long(curl, CURLOPT_FOLLOWLOCATION, 1)
setopt_long(curl, CURLOPT_SSL_VERIFYPEER, 0)
setopt_long(curl, CURLOPT_SSL_VERIFYHOST, 0)

# Perform request
print(f"\n=== Requesting {url.decode()} ===")
response_data.clear()
ret = dll.curl_easy_perform(curl)
print(f"curl_easy_perform result: {ret}")

# Get response code
resp_code = ctypes.c_long(0)
dll.curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, ctypes.byref(resp_code))
print(f"HTTP response code: {resp_code.value}")

# Print response
response_text = response_data.decode("utf-8", errors="replace")
print(f"\n=== Response ({len(response_data)} bytes) ===")
print(response_text[:2000])
if len(response_text) > 2000:
    print(f"... ({len(response_text) - 2000} more bytes)")

# If response is JSON, check fingerprint
try:
    resp_json = json.loads(response_text)
    if "detail" in resp_json:
        print(f"\n=== Fingerprint Verification ===")
        print(f"JA3:  {resp_json.get('ja3', 'N/A')}")
        print(f"JA4:  {resp_json.get('ja4', 'N/A')}")
        expected_ja3 = json.loads(json_content).get("ja3", "")
        expected_ja4 = json.loads(json_content).get("ja4", "")
        print(f"Expected JA3: {expected_ja3}")
        print(f"Expected JA4: {expected_ja4}")
        if resp_json.get("ja3") == expected_ja3:
            print("JA3: MATCH ✓")
        else:
            print("JA3: MISMATCH ✗")
        if resp_json.get("ja4") == expected_ja4:
            print("JA4: MATCH ✓")
        else:
            print("JA4: MISMATCH ✗")
except json.JSONDecodeError:
    pass

dll.curl_easy_cleanup(curl)
print("\nDone.")

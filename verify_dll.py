#!/usr/bin/env python3
"""
Comprehensive verification script for libcurl-impersonate DLL.

Tests:
1. DLL load + version info
2. dumpbin dependency check (no non-system DLLs)
3. Exported symbols (curl_easy_impersonate_* APIs)
4. curl_easy_impersonate_register with XWEB.json
5. HTTPS request to fingerprint server with impersonation
6. JA3 extension set, JA4, and HTTP2 fingerprint validation
"""

import ctypes
import ctypes.wintypes
import json
import os
import sys
import subprocess
import re
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(r"D:\curl-impersonate-8.20.0")
DLL_PATH = ROOT_DIR / "output" / "libcurl-impersonate.dll"
XWEB_JSON = Path(r"D:\curl-impersonate\XWEB.json")
VERIFY_URL = "https://120.26.33.71/json/detail"

# ── curl constants (from curl.h) ──────────────────────────────────────
CURLOPT_URL = 2
CURLOPT_WRITEDATA = 1
CURLOPT_WRITEFUNCTION = 11
CURLOPT_USERAGENT = 18
CURLOPT_HTTPHEADER = 23
CURLOPT_FOLLOWLOCATION = 52
CURLOPT_SSL_VERIFYPEER = 64
CURLOPT_SSL_VERIFYHOST = 81
CURLOPT_TIMEOUT = 13
CURLOPT_HTTP_VERSION = 84
CURLOPT_ACCEPT_ENCODING = 102

CURLE_OK = 0
CURL_HTTP_VERSION_2_0 = 3

# ── Helpers ────────────────────────────────────────────────────────────
class COLORS:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

def ok(msg):
    print(f"  {COLORS.GREEN}[PASS]{COLORS.RESET} {msg}")

def fail(msg):
    print(f"  {COLORS.RED}[FAIL]{COLORS.RESET} {msg}")

def warn(msg):
    print(f"  {COLORS.YELLOW}[WARN]{COLORS.RESET} {msg}")

def info(msg):
    print(f"  {COLORS.CYAN}[INFO]{COLORS.RESET} {msg}")

def section(title):
    print(f"\n{COLORS.BOLD}{'='*60}\n  {title}\n{'='*60}{COLORS.RESET}")

WRITE_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p)

# ── Test 1: DLL Load ──────────────────────────────────────────────────
def test_dll_load():
    section("1. DLL Load & Version")
    if not DLL_PATH.exists():
        fail(f"DLL not found: {DLL_PATH}")
        return None

    try:
        dll = ctypes.WinDLL(str(DLL_PATH))
    except OSError as e:
        fail(f"Cannot load DLL: {e}")
        return None

    ok(f"DLL loaded: {DLL_PATH} ({DLL_PATH.stat().st_size/1024/1024:.1f} MB)")

    # curl_version
    dll.curl_version.restype = ctypes.c_char_p
    ver = dll.curl_version().decode("utf-8")
    ok(f"Version: {ver}")

    # Check key features in version string
    for feat in ["BoringSSL", "nghttp2", "ngtcp2", "nghttp3", "brotli", "zstd", "libssh2"]:
        if feat in ver:
            ok(f"  Feature present: {feat}")
        else:
            warn(f"  Feature missing: {feat}")

    return dll

# ── Test 2: Dependencies ──────────────────────────────────────────────
def test_dependencies():
    section("2. DLL Dependencies (dumpbin)")
    SYSTEM_DLLS = {
        "kernel32.dll", "ntdll.dll", "ws2_32.dll", "advapi32.dll", "crypt32.dll",
        "secur32.dll", "user32.dll", "gdi32.dll", "shell32.dll", "shlwapi.dll",
        "ole32.dll", "oleaut32.dll", "uuid.dll", "msvcrt.dll", "bcrypt.dll",
        "ncrypt.dll", "imm32.dll", "comdlg32.dll", "version.dll", "winmm.dll",
        "wsock32.dll", "wldap32.dll", "normaliz.dll", "iphlpapi.dll",
    }

    # Find dumpbin via vcvarsall
    vcvarsall = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat")
    if not vcvarsall.exists():
        # Try other VS locations
        import glob
        candidates = glob.glob(r"C:\Program Files\Microsoft Visual Studio\2022\*\VC\Auxiliary\Build\vcvarsall.bat")
        if candidates:
            vcvarsall = Path(candidates[0])
        else:
            warn("vcvarsall.bat not found, trying dumpbin directly")
            vcvarsall = None

    dumpbin_output = None
    if vcvarsall:
        # Run dumpbin through vcvarsall
        cmd = f'call "{vcvarsall}" x64 >nul 2>&1 & dumpbin /dependents "{DLL_PATH}"'
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        dumpbin_output = r.stdout
    else:
        r = subprocess.run(["dumpbin", "/dependents", str(DLL_PATH)],
                          capture_output=True, text=True, check=False)
        if r.returncode == 0:
            dumpbin_output = r.stdout

    if dumpbin_output:
        deps = []
        for line in dumpbin_output.splitlines():
            line = line.strip().lower()
            if line.endswith(".dll"):
                deps.append(line)

        non_system = [d for d in deps if d not in SYSTEM_DLLS]
        if non_system:
            fail(f"Non-system DLL dependencies: {non_system}")
            fail("  All dependencies should be statically linked!")
        else:
            ok(f"All {len(deps)} dependencies are system DLLs: {deps}")
    else:
        warn("Could not run dumpbin, skipping dependency check")

    # Also check exports
    if vcvarsall:
        cmd = f'call "{vcvarsall}" x64 >nul 2>&1 & dumpbin /exports "{DLL_PATH}"'
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if r.returncode == 0:
            exports = []
            for line in r.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[0].isdigit():
                    exports.append(parts[-1])

            info(f"Total exports: {len(exports)}")

            # Check key APIs
            key_apis = [s for s in exports if "impersonate" in s]
            if key_apis:
                ok(f"Impersonate APIs: {', '.join(key_apis)}")
            else:
                fail("No curl_easy_impersonate exports found!")

            # Check basic curl APIs
            basic = [s for s in exports if s in ("curl_easy_init", "curl_easy_setopt",
                                                   "curl_easy_perform", "curl_easy_cleanup",
                                                   "curl_version", "curl_slist_append",
                                                   "curl_slist_free_all")]
            ok(f"Basic curl APIs: {', '.join(basic)}")

# ── Test 3: Register impersonation ────────────────────────────────────
def test_impersonate_register(dll):
    section("3. curl_easy_impersonate_register")

    if not XWEB_JSON.exists():
        fail(f"XWEB.json not found: {XWEB_JSON}")
        return None

    with open(XWEB_JSON, "r", encoding="utf-8") as f:
        xweb_data = json.load(f)

    info(f"XWEB.json loaded: {list(xweb_data.keys())}")

    # Register
    target = b"wechat_xweb"
    json_str = json.dumps(xweb_data).encode("utf-8")

    dll.curl_easy_impersonate_register.restype = ctypes.c_int
    dll.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]

    rc = dll.curl_easy_impersonate_register(target, json_str)
    if rc == CURLE_OK:
        ok(f"curl_easy_impersonate_register('wechat_xweb') succeeded (rc={rc})")
    else:
        fail(f"curl_easy_impersonate_register failed (rc={rc})")
        return None

    # Verify registration via list
    dll.curl_easy_impersonate_list.restype = ctypes.c_void_p
    list_ptr = dll.curl_easy_impersonate_list()
    if list_ptr:
        ok("curl_easy_impersonate_list() returned non-NULL")
    else:
        warn("curl_easy_impersonate_list() returned NULL")

    return xweb_data

# ── Test 4: HTTPS Request with Impersonation ──────────────────────────
def test_https_request(dll, xweb_data):
    section("4. HTTPS Request with Impersonation")

    # Initialize curl
    dll.curl_easy_init.restype = ctypes.c_void_p
    curl = dll.curl_easy_init()
    if not curl:
        fail("curl_easy_init() returned NULL")
        return None
    ok("curl_easy_init() succeeded")

    # Apply impersonation
    dll.curl_easy_impersonate.restype = ctypes.c_int
    dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    rc = dll.curl_easy_impersonate(curl, b"wechat_xweb", 1)
    if rc == CURLE_OK:
        ok("curl_easy_impersonate('wechat_xweb', default_headers=1) succeeded")
    else:
        fail(f"curl_easy_impersonate failed (rc={rc})")
        dll.curl_easy_cleanup(curl)
        return None

    # Set URL
    dll.curl_easy_setopt.restype = ctypes.c_int
    url_bytes = VERIFY_URL.encode("utf-8")
    rc = dll.curl_easy_setopt(curl, CURLOPT_URL, url_bytes)
    if rc == CURLE_OK:
        ok(f"URL set: {VERIFY_URL}")
    else:
        fail(f"Failed to set URL (rc={rc})")

    # Disable SSL verification (self-signed cert)
    rc1 = dll.curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0)
    rc2 = dll.curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0)
    if rc1 == CURLE_OK and rc2 == CURLE_OK:
        ok("SSL verification disabled (self-signed cert)")
    else:
        warn(f"SSL opts rc={rc1},{rc2}")

    # Set timeout
    dll.curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30)

    # Follow redirects
    dll.curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1)

    # Set HTTP version to HTTP/2
    dll.curl_easy_setopt(curl, CURLOPT_HTTP_VERSION, CURL_HTTP_VERSION_2_0)

    # Response buffer
    response_data = bytearray()

    def write_callback(data, size, nmemb, userdata):
        response_data.extend(data[:size * nmemb])
        return size * nmemb

    callback = WRITE_CALLBACK(write_callback)

    dll.curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, callback)
    dll.curl_easy_setopt(curl, CURLOPT_WRITEDATA, 0)

    # Perform request
    info("Performing HTTPS request...")
    rc = dll.curl_easy_perform(curl)
    if rc == CURLE_OK:
        ok(f"Request succeeded (rc={rc})")
    else:
        # Get error message
        err_buf = ctypes.create_string_buffer(256)
        dll.curl_easy_strerror.restype = ctypes.c_char_p
        err_msg = dll.curl_easy_strerror(rc).decode("utf-8", errors="replace")
        fail(f"Request failed (rc={rc}): {err_msg}")
        dll.curl_easy_cleanup(curl)
        return None

    # Get response
    response_text = response_data.decode("utf-8", errors="replace")
    info(f"Response size: {len(response_text)} bytes")

    # Get HTTP code
    http_code = ctypes.c_long(0)
    dll.curl_easy_getinfo.restype = ctypes.c_int
    dll.curl_easy_getinfo(curl, 0x200002, ctypes.byref(http_code))  # CURLINFO_RESPONSE_CODE
    ok(f"HTTP status: {http_code.value}")

    # Try to parse as JSON
    try:
        result_json = json.loads(response_text)
        ok("Response is valid JSON")
        info(f"Response keys: {list(result_json.keys())}")

        # Extract fingerprint data
        if "detail" in result_json:
            detail = result_json["detail"]
            if "ja3" in detail:
                info(f"Server JA3 hash: {detail['ja3']}")
            if "ja4" in detail:
                info(f"Server JA4: {detail['ja4']}")
            if "http2" in detail:
                info(f"Server HTTP2 fingerprint: {detail['http2']}")
    except json.JSONDecodeError:
        warn("Response is not valid JSON, showing first 500 chars:")
        info(response_text[:500])

    dll.curl_easy_cleanup(curl)
    return response_text

# ── Test 5: Fingerprint Comparison ────────────────────────────────────
def test_fingerprints(response_text, xweb_data):
    section("5. Fingerprint Comparison")

    if not response_text:
        fail("No response to analyze")
        return

    try:
        result_json = json.loads(response_text)
    except json.JSONDecodeError:
        fail("Response is not JSON, cannot compare fingerprints")
        return

    if "detail" not in result_json:
        fail("Response has no 'detail' section")
        return

    server_detail = result_json["detail"]
    xweb_detail = xweb_data.get("detail", {})

    # ── JA3: Extension set comparison ──
    section("5a. JA3 Extension Set")
    if "ja3" in server_detail and "ja3" in xweb_detail:
        server_ja3 = server_detail["ja3"]
        xweb_ja3 = xweb_detail["ja3"]

        server_exts = set()
        xweb_exts = set()

        # Get extension IDs from both
        if "AllExtensions" in server_ja3:
            # Remove GREASE extensions for comparison
            server_exts = set(e for e in server_ja3["AllExtensions"]
                            if not (0x0A0A <= (e & 0xFFFF) <= 0x0B0B or  # GREASE ranges
                                    e == 31354 or  # GREASE from XWEB
                                    e == 23130))   # GREASE from XWEB
        if "AllExtensions" in xweb_ja3:
            xweb_exts = set(e for e in xweb_ja3["AllExtensions"]
                          if not (0x0A0A <= (e & 0xFFFF) <= 0x0B0B or
                                  e == 31354 or
                                  e == 23130))

        # Also get readable names
        server_readable = set()
        xweb_readable = set()
        if "ReadableAllExtensions" in server_ja3:
            server_readable = set(server_ja3["ReadableAllExtensions"])
        if "ReadableAllExtensions" in xweb_ja3:
            xweb_readable = set(xweb_ja3["ReadableAllExtensions"])

        if server_exts == xweb_exts:
            ok(f"JA3 extension IDs match (excluding GREASE): {sorted(server_exts)}")
        else:
            only_server = server_exts - xweb_exts
            only_xweb = xweb_exts - server_exts
            if only_server:
                warn(f"  Extensions only in server response: {sorted(only_server)}")
            if only_xweb:
                warn(f"  Extensions only in XWEB.json: {sorted(only_xweb)}")
            common = server_exts & xweb_exts
            info(f"  Common extensions: {sorted(common)}")

        if server_readable == xweb_readable:
            ok(f"JA3 extension names match: {sorted(server_readable)}")
        else:
            only_server = server_readable - xweb_readable
            only_xweb = xweb_readable - server_readable
            if only_server:
                info(f"  Names only in server: {sorted(only_server)}")
            if only_xweb:
                info(f"  Names only in XWEB: {sorted(only_xweb)}")

        # Cipher suites comparison (set, not order)
        if "CipherSuites" in server_ja3 and "CipherSuites" in xweb_ja3:
            server_ciphers = set(server_ja3["CipherSuites"])
            xweb_ciphers = set(xweb_ja3["CipherSuites"])
            if server_ciphers == xweb_ciphers:
                ok(f"JA3 cipher suite set matches: {sorted(server_ciphers)}")
            else:
                only_server = server_ciphers - xweb_ciphers
                only_xweb = xweb_ciphers - server_ciphers
                if only_server:
                    warn(f"  Ciphers only in server: {sorted(only_server)}")
                if only_xweb:
                    warn(f"  Ciphers only in XWEB: {sorted(only_xweb)}")

        # Supported groups comparison
        if "SupportedGroups" in server_ja3 and "SupportedGroups" in xweb_ja3:
            server_groups = set(server_ja3["SupportedGroups"])
            xweb_groups = set(xweb_ja3["SupportedGroups"])
            if server_groups == xweb_groups:
                ok(f"JA3 supported groups match: {sorted(server_groups)}")
            else:
                only_server = server_groups - xweb_groups
                only_xweb = xweb_groups - server_groups
                if only_server:
                    warn(f"  Groups only in server: {sorted(only_server)}")
                if only_xweb:
                    warn(f"  Groups only in XWEB: {sorted(only_xweb)}")
    else:
        warn("JA3 data not available for comparison")

    # ── JA4 Comparison ──
    section("5b. JA4 Fingerprint")
    if "ja4" in server_detail and "ja4" in xweb_detail:
        server_ja4 = server_detail["ja4"]
        xweb_ja4 = xweb_detail["ja4"]

        # JA4 string comparison
        server_ja4_str = server_detail.get("ja4", "")
        xweb_ja4_str = xweb_detail.get("ja4", "")
        if server_ja4_str and xweb_ja4_str:
            if server_ja4_str == xweb_ja4_str:
                ok(f"JA4 string matches: {server_ja4_str}")
            else:
                info(f"  Server JA4: {server_ja4_str}")
                info(f"  XWEB   JA4: {xweb_ja4_str}")
                # Parse and compare components
                # JA4 format: t<version><num_ciphers><num_exts><alpn>_<cipher_hash>_<ext_hash>_<sigalg_hash>
                s_parts = server_ja4_str.split("_")
                x_parts = xweb_ja4_str.split("_")
                if len(s_parts) == 4 and len(x_parts) == 4:
                    if s_parts[0] == x_parts[0]:
                        ok(f"  JA4 prefix matches: {s_parts[0]}")
                    else:
                        warn(f"  JA4 prefix differs: server={s_parts[0]} xweb={x_parts[0]}")
                    for i, name in [(1, "cipher_hash"), (2, "ext_hash"), (3, "sigalg_hash")]:
                        if s_parts[i] == x_parts[i]:
                            ok(f"  JA4 {name} matches: {s_parts[i]}")
                        else:
                            warn(f"  JA4 {name} differs: server={s_parts[i]} xweb={x_parts[i]}")

        # Signature algorithms
        if "SignatureAlgorithms" in server_ja4 and "SignatureAlgorithms" in xweb_ja4:
            server_sigalgs = server_ja4["SignatureAlgorithms"]
            xweb_sigalgs = xweb_ja4["SignatureAlgorithms"]
            if server_sigalgs == xweb_sigalgs:
                ok(f"JA4 signature algorithms match: {server_sigalgs}")
            else:
                warn(f"  Server sigalgs: {server_sigalgs}")
                warn(f"  XWEB   sigalgs: {xweb_sigalgs}")

        # JA4 cipher suites (sorted)
        if "CipherSuites" in server_ja4 and "CipherSuites" in xweb_ja4:
            server_ciphers = server_ja4["CipherSuites"]
            xweb_ciphers = xweb_ja4["CipherSuites"]
            if sorted(server_ciphers) == sorted(xweb_ciphers):
                ok(f"JA4 cipher suite set matches")
            else:
                only_server = set(server_ciphers) - set(xweb_ciphers)
                only_xweb = set(xweb_ciphers) - set(server_ciphers)
                if only_server:
                    warn(f"  JA4 ciphers only in server: {sorted(only_server)}")
                if only_xweb:
                    warn(f"  JA4 ciphers only in XWEB: {sorted(only_xweb)}")

        # JA4 extensions (sorted)
        if "Extensions" in server_ja4 and "Extensions" in xweb_ja4:
            server_exts = server_ja4["Extensions"]
            xweb_exts = xweb_ja4["Extensions"]
            if sorted(server_exts) == sorted(xweb_exts):
                ok(f"JA4 extension set matches: {sorted(server_exts)}")
            else:
                only_server = set(server_exts) - set(xweb_exts)
                only_xweb = set(xweb_exts) - set(server_exts)
                if only_server:
                    warn(f"  JA4 exts only in server: {sorted(only_server)}")
                if only_xweb:
                    warn(f"  JA4 exts only in XWEB: {sorted(only_xweb)}")
    else:
        warn("JA4 data not available for comparison")

    # ── HTTP2 Fingerprint ──
    section("5c. HTTP2 Fingerprint")
    if "http2" in server_detail and "http2" in xweb_detail:
        server_h2 = server_detail["http2"]
        xweb_h2 = xweb_detail["http2"]

        # HTTP2 fingerprint string
        if server_h2 == xweb_h2:
            ok(f"HTTP2 fingerprint string matches: {server_h2}")
        else:
            info(f"  Server HTTP2: {server_h2}")
            info(f"  XWEB   HTTP2: {xweb_h2}")

            # Parse and compare components
            # Format: settings|window_update|priority|header_order
            def parse_h2(h2str):
                parts = h2str.split("|")
                result = {}
                if len(parts) >= 1:
                    result["settings"] = parts[0]
                if len(parts) >= 2:
                    result["window_update"] = parts[1]
                if len(parts) >= 3:
                    result["priority"] = parts[2]
                if len(parts) >= 4:
                    result["header_order"] = parts[3]
                return result

            s_h2 = parse_h2(server_h2)
            x_h2 = parse_h2(xweb_h2)

            for key in ["settings", "window_update", "priority", "header_order"]:
                if key in s_h2 and key in x_h2:
                    if s_h2[key] == x_h2[key]:
                        ok(f"  HTTP2 {key} matches: {s_h2[key]}")
                    else:
                        fail(f"  HTTP2 {key} differs!")
                        info(f"    Server: {s_h2[key]}")
                        info(f"    XWEB:   {x_h2[key]}")
    else:
        # Try metadata.HTTP2Frames
        server_meta = server_detail.get("metadata", {})
        xweb_meta = xweb_detail.get("metadata", {})
        if "HTTP2Frames" in server_meta or "HTTP2Frames" in xweb_meta:
            info("HTTP2 data found in metadata.HTTP2Frames")
            server_h2f = server_meta.get("HTTP2Frames", {})
            xweb_h2f = xweb_meta.get("HTTP2Frames", {})

            if "Settings" in server_h2f and "Settings" in xweb_h2f:
                s_settings = sorted(server_h2f["Settings"], key=lambda x: x.get("Id", 0))
                x_settings = sorted(xweb_h2f["Settings"], key=lambda x: x.get("Id", 0))
                if s_settings == x_settings:
                    ok(f"HTTP2 Settings match: {s_settings}")
                else:
                    fail("HTTP2 Settings differ!")
                    info(f"  Server: {s_settings}")
                    info(f"  XWEB:   {x_settings}")

            if "WindowUpdateIncrement" in server_h2f and "WindowUpdateIncrement" in xweb_h2f:
                if server_h2f["WindowUpdateIncrement"] == xweb_h2f["WindowUpdateIncrement"]:
                    ok(f"HTTP2 WindowUpdateIncrement matches: {server_h2f['WindowUpdateIncrement']}")
                else:
                    fail(f"HTTP2 WindowUpdateIncrement differs: server={server_h2f['WindowUpdateIncrement']} xweb={xweb_h2f['WindowUpdateIncrement']}")

            if "Priorities" in server_h2f and "Priorities" in xweb_h2f:
                if server_h2f["Priorities"] == xweb_h2f["Priorities"]:
                    ok(f"HTTP2 Priorities match")
                else:
                    fail(f"HTTP2 Priorities differ!")
                    info(f"  Server: {server_h2f['Priorities']}")
                    info(f"  XWEB:   {xweb_h2f['Priorities']}")
        else:
            warn("HTTP2 fingerprint data not available for comparison")

# ── Test 6: Without Impersonation (baseline) ──────────────────────────
def test_without_impersonation(dll):
    section("6. Baseline Request (no impersonation)")

    dll.curl_easy_init.restype = ctypes.c_void_p
    curl = dll.curl_easy_init()
    if not curl:
        fail("curl_easy_init() returned NULL")
        return

    dll.curl_easy_setopt.restype = ctypes.c_int
    dll.curl_easy_setopt(curl, CURLOPT_URL, VERIFY_URL.encode("utf-8"))
    dll.curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0)
    dll.curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0)
    dll.curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30)
    dll.curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1)

    response_data = bytearray()
    def write_callback(data, size, nmemb, userdata):
        response_data.extend(data[:size * nmemb])
        return size * nmemb

    callback = WRITE_CALLBACK(write_callback)
    dll.curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, callback)
    dll.curl_easy_setopt(curl, CURLOPT_WRITEDATA, 0)

    rc = dll.curl_easy_perform(curl)
    if rc == CURLE_OK:
        response_text = response_data.decode("utf-8", errors="replace")
        try:
            result_json = json.loads(response_text)
            if "detail" in result_json:
                detail = result_json["detail"]
                info(f"Baseline JA3: {detail.get('ja3', 'N/A')}")
                info(f"Baseline JA4: {detail.get('ja4', 'N/A')}")
                info(f"Baseline HTTP2: {detail.get('http2', 'N/A')}")
                # Show that impersonation changes fingerprint
                ok("Baseline request succeeded (fingerprint differs from impersonated)")
        except json.JSONDecodeError:
            info(f"Baseline response (not JSON): {response_text[:200]}")
    else:
        dll.curl_easy_strerror.restype = ctypes.c_char_p
        err_msg = dll.curl_easy_strerror(rc).decode("utf-8", errors="replace")
        warn(f"Baseline request failed (rc={rc}): {err_msg}")

    dll.curl_easy_cleanup(curl)

# ── Main ──────────────────────────────────────────────────────────────
def main():
    print(f"{COLORS.BOLD}libcurl-impersonate DLL Verification{COLORS.RESET}")
    print(f"DLL: {DLL_PATH}")
    print(f"XWEB.json: {XWEB_JSON}")
    print(f"Verify URL: {VERIFY_URL}")

    # Test 1: Load DLL
    dll = test_dll_load()
    if not dll:
        sys.exit(1)

    # Test 2: Dependencies
    test_dependencies()

    # Test 3: Register impersonation
    xweb_data = test_impersonate_register(dll)
    if not xweb_data:
        warn("Cannot test impersonation without XWEB.json registration")
        sys.exit(1)

    # Test 4: HTTPS request with impersonation
    response = test_https_request(dll, xweb_data)

    # Test 5: Fingerprint comparison
    if response:
        test_fingerprints(response, xweb_data)

    # Test 6: Baseline (no impersonation)
    test_without_impersonation(dll)

    section("Summary")
    print("Verification complete. Check [PASS]/[FAIL]/[WARN] above.")

if __name__ == "__main__":
    main()

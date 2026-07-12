#!/usr/bin/env python3
"""Test the curl_impy module."""
import sys, os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curl_impy import Session, register_fingerprint, list_fingerprints

print("=== curl_impy Test ===\n")

# List auto-registered fingerprints
fps = list_fingerprints()
print(f"Registered fingerprints: {fps}")

# Test 1: Chrome144 GET request
print("\n--- Test 1: Chrome144 GET ---")
with Session(impersonate="chrome144", verify=False, timeout=15) as s:
    r = s.get("https://httpbin.org/get")
    print(f"Status: {r.status_code}")
    print(f"URL: {r.url}")
    print(f"Elapsed: {r.elapsed:.3f}s")
    print(f"Headers: {dict(list(r.headers.items())[:5])}")
    data = r.json()
    print(f"User-Agent: {data.get('headers',{}).get('User-Agent','?')}")
    if "Chrome/144" in data.get("headers",{}).get("User-Agent",""):
        print("[PASS] User-Agent is Chrome/144")
    else:
        print("[FAIL] User-Agent mismatch")

# Test 2: Fingerprint echo
print("\n--- Test 2: Fingerprint Echo ---")
with Session(impersonate="chrome144", verify=False, timeout=15) as s:
    r = s.get("https://120.26.33.71/json/detail")
    if r.status_code == 200 and "t13i1515h2_8daaf6152771_d8a2da3f94cd" in r.text:
        print("[PASS] JA4 fingerprint matches")
    else:
        print(f"[FAIL] JA4 mismatch (status={r.status_code})")
    if "1:65536;2:0;4:6291456;6:262144" in r.text:
        print("[PASS] HTTP2 fingerprint matches")
    else:
        print("[FAIL] HTTP2 mismatch")

# Test 3: POST with JSON
print("\n--- Test 3: POST JSON ---")
with Session(impersonate="chrome144", verify=False, timeout=15) as s:
    r = s.post("https://httpbin.org/post", json={"key": "value", "num": 42})
    if r.status_code == 200:
        data = r.json()
        if data.get("json",{}).get("key") == "value":
            print("[PASS] POST JSON works")
        else:
            print(f"[FAIL] POST JSON response: {r.text[:200]}")
    else:
        print(f"[FAIL] POST status={r.status_code}")

# Test 4: Proxy isolation
print("\n--- Test 4: Proxy isolation ---")
os.environ["http_proxy"] = "http://127.0.0.1:1"
os.environ["https_proxy"] = "http://127.0.0.1:1"
with Session(impersonate="chrome144", verify=False, timeout=10) as s:
    r = s.get("https://www.baidu.com")
    if r.status_code == 200:
        print("[PASS] Proxy env vars ignored")
    else:
        print(f"[FAIL] Proxy leaked (status={r.status_code})")
del os.environ["http_proxy"]
del os.environ["https_proxy"]

# Test 5: Explicit proxy
print("\n--- Test 5: Explicit proxy ---")
with Session(impersonate="chrome144", verify=False, timeout=5, proxies={"https": "http://127.0.0.1:1"}) as s:
    try:
        r = s.get("https://www.baidu.com")
        print(f"[FAIL] Should have failed with bad proxy (status={r.status_code})")
    except RuntimeError as e:
        print(f"[PASS] Explicit proxy works (failed as expected)")

# Test 6: Custom headers
print("\n--- Test 6: Custom headers ---")
with Session(impersonate="chrome144", verify=False, timeout=15) as s:
    r = s.get("https://httpbin.org/get", headers={"X-Custom-Header": "test123"})
    data = r.json()
    if data.get("headers",{}).get("X-Custom-Header") == "test123":
        print("[PASS] Custom header sent")
    else:
        print(f"[FAIL] Custom header missing: {data.get('headers',{})}")

print("\n=== Done ===")

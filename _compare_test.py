"""
Deep comparison test: curl_cffi vs curl_impy
Runs identical operations with both libraries and compares results.
"""
import sys, os, json, time, traceback, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure __pycache__ doesn't interfere
import importlib

results = []

def test(name, func_cffi, func_impy):
    """Run a test with both libraries and compare results."""
    r = {"test": name, "cffi": None, "impy": None, "match": None, "error": None}
    try:
        r["cffi"] = func_cffi()
    except Exception as e:
        r["cffi"] = f"ERROR: {e}"
    try:
        r["impy"] = func_impy()
    except Exception as e:
        r["impy"] = f"ERROR: {e}"
    # Compare
    if isinstance(r["cffi"], str) and r["cffi"].startswith("ERROR"):
        r["match"] = "cffi_error"
    elif isinstance(r["impy"], str) and r["impy"].startswith("ERROR"):
        r["match"] = "impy_error"
    elif r["cffi"] == r["impy"]:
        r["match"] = "MATCH"
    else:
        r["match"] = "DIFF"
    results.append(r)
    status = "✓" if r["match"] == "MATCH" else "✗" if r["match"] == "DIFF" else "⚠"
    print(f"  {status} {name}: {r['match']}", flush=True)
    if r["match"] == "DIFF":
        print(f"      cffi: {r['cffi']}", flush=True)
        print(f"      impy: {r['impy']}", flush=True)
    return r


# ============================================================================
# Imports
# ============================================================================
from curl_cffi import requests as cffi_req
from curl_cffi import Curl as CffiCurl, CurlOpt as CffiOpt, CurlInfo as CffiInfo

from curl_impy import requests as impy_req
from curl_impy import Curl as ImpyCurl, CurlOpt as ImpyOpt, CurlInfo as ImpyInfo

BASE = "https://httpbin.org"

print("=" * 70)
print("Deep Comparison Test: curl_cffi vs curl_impy")
print("=" * 70)

# ============================================================================
# 1. Basic GET
# ============================================================================
print("\n--- 1. Basic HTTP Methods ---", flush=True)

def cffi_get():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return r.status_code

def impy_get():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return r.status_code
test("GET status", cffi_get, impy_get)

def cffi_get_body():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        data = r.json()
        return data["headers"].get("User-Agent", "")[:20]
def impy_get_body():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        data = r.json()
        return data["headers"].get("User-Agent", "")[:20]
test("GET json UA", cffi_get_body, impy_get_body)

def cffi_post():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.post(f"{BASE}/post", data={"key": "value"}, timeout=15)
        return r.json()["form"]["key"]
def impy_post():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.post(f"{BASE}/post", data={"key": "value"}, timeout=15)
        return r.json()["form"]["key"]
test("POST form", cffi_post, impy_post)

def cffi_post_json():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.post(f"{BASE}/post", json={"key": "value"}, timeout=15)
        return r.json()["json"]["key"]
def impy_post_json():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.post(f"{BASE}/post", json={"key": "value"}, timeout=15)
        return r.json()["json"]["key"]
test("POST json", cffi_post_json, impy_post_json)

def cffi_put():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.put(f"{BASE}/put", data="body", timeout=15)
        return r.status_code
def impy_put():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.put(f"{BASE}/put", data="body", timeout=15)
        return r.status_code
test("PUT", cffi_put, impy_put)

def cffi_delete():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.delete(f"{BASE}/delete", timeout=15)
        return r.status_code
def impy_delete():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.delete(f"{BASE}/delete", timeout=15)
        return r.status_code
test("DELETE", cffi_delete, impy_delete)

def cffi_head():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.head(f"{BASE}/get", timeout=15)
        return r.status_code
def impy_head():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.head(f"{BASE}/get", timeout=15)
        return r.status_code
test("HEAD", cffi_head, impy_head)

# ============================================================================
# 2. Headers
# ============================================================================
print("\n--- 2. Headers ---", flush=True)

def cffi_headers():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/headers", headers={"X-Custom": "test123"}, timeout=15)
        return r.json()["headers"].get("X-Custom")
def impy_headers():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/headers", headers={"X-Custom": "test123"}, timeout=15)
        return r.json()["headers"].get("X-Custom")
test("Custom header", cffi_headers, impy_headers)

def cffi_multi_headers():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/headers", headers={"X- Multi": "a, b, c"}, timeout=15)
        return r.json()["headers"].get("X-Multi")
def impy_multi_headers():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/headers", headers={"X- Multi": "a, b, c"}, timeout=15)
        return r.json()["headers"].get("X-Multi")
test("Multi-value header", cffi_multi_headers, impy_multi_headers)

# ============================================================================
# 3. Cookies
# ============================================================================
print("\n--- 3. Cookies ---", flush=True)

def cffi_cookies():
    with cffi_req.Session(impersonate="chrome") as s:
        s.cookies.set("test_cookie", "abc123")
        r = s.get(f"{BASE}/cookies", timeout=15)
        return r.json()["cookies"].get("test_cookie")
def impy_cookies():
    with impy_req.Session(impersonate="chrome") as s:
        s.cookies.set("test_cookie", "abc123")
        r = s.get(f"{BASE}/cookies", timeout=15)
        return r.json()["cookies"].get("test_cookie")
test("Send cookie", cffi_cookies, impy_cookies)

def cffi_set_cookie():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/cookies/set?foo=bar", timeout=15, allow_redirects=False)
        return dict(r.cookies).get("foo")
def impy_set_cookie():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/cookies/set?foo=bar", timeout=15, allow_redirects=False)
        return dict(r.cookies).get("foo")
test("Set-Cookie response", cffi_set_cookie, impy_set_cookie)

# ============================================================================
# 4. Auth
# ============================================================================
print("\n--- 4. Authentication ---", flush=True)

def cffi_auth():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/basic-auth/user/pass", auth=("user", "pass"), timeout=15)
        return r.status_code
def impy_auth():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/basic-auth/user/pass", auth=("user", "pass"), timeout=15)
        return r.status_code
test("Basic auth", cffi_auth, impy_auth)

def cffi_auth_body():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/basic-auth/user/pass", auth=("user", "pass"), timeout=15)
        return r.json()["authenticated"]
def impy_auth_body():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/basic-auth/user/pass", auth=("user", "pass"), timeout=15)
        return r.json()["authenticated"]
test("Basic auth body", cffi_auth_body, impy_auth_body)

# ============================================================================
# 5. Redirects
# ============================================================================
print("\n--- 5. Redirects ---", flush=True)

def cffi_redirect_follow():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/redirect/2", timeout=15)
        return r.status_code
def impy_redirect_follow():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/redirect/2", timeout=15)
        return r.status_code
test("Follow redirect", cffi_redirect_follow, impy_redirect_follow)

def cffi_redirect_nofollow():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/redirect/2", timeout=15, allow_redirects=False)
        return r.status_code
def impy_redirect_nofollow():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/redirect/2", timeout=15, allow_redirects=False)
        return r.status_code
test("No follow redirect", cffi_redirect_nofollow, impy_redirect_nofollow)

# ============================================================================
# 6. TLS/SSL
# ============================================================================
print("\n--- 6. TLS/SSL ---", flush=True)

def cffi_verify_true():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get("https://www.example.com", verify=True, timeout=15)
        return r.status_code
def impy_verify_true():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get("https://www.example.com", verify=True, timeout=15)
        return r.status_code
test("verify=True", cffi_verify_true, impy_verify_true)

def cffi_verify_false():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get("https://www.example.com", verify=False, timeout=15)
        return r.status_code
def impy_verify_false():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get("https://www.example.com", verify=False, timeout=15)
        return r.status_code
test("verify=False", cffi_verify_false, impy_verify_false)

# ============================================================================
# 7. Impersonation
# ============================================================================
print("\n--- 7. Impersonation ---", flush=True)

for browser in ["chrome", "safari15_3", "edge99"]:
    def make_cffi(br=browser):
        def f():
            with cffi_req.Session(impersonate=br) as s:
                r = s.get(f"{BASE}/user-agent", timeout=15)
                return r.json()["user-agent"][:15]
        return f
    def make_impy(br=browser):
        def f():
            with impy_req.Session(impersonate=br) as s:
                r = s.get(f"{BASE}/user-agent", timeout=15)
                return r.json()["user-agent"][:15]
        return f
    test(f"impersonate={browser}", make_cffi(), make_impy())

# ============================================================================
# 8. Response Properties
# ============================================================================
print("\n--- 8. Response Properties ---", flush=True)

def cffi_resp_url():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return str(r.url)
def impy_resp_url():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return str(r.url)
test("Response URL", cffi_resp_url, impy_resp_url)

def cffi_resp_encoding():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return r.encoding
def impy_resp_encoding():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return r.encoding
test("Response encoding", cffi_resp_encoding, impy_resp_encoding)

def cffi_resp_content_type():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return r.headers.get("content-type")
def impy_resp_content_type():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", timeout=15)
        return r.headers.get("content-type")
test("Content-Type header", cffi_resp_content_type, impy_resp_content_type)

# ============================================================================
# 9. Params
# ============================================================================
print("\n--- 9. Query Params ---", flush=True)

def cffi_params():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", params={"a": "1", "b": "hello world"}, timeout=15)
        data = r.json()
        return data["args"].get("b")
def impy_params():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/get", params={"a": "1", "b": "hello world"}, timeout=15)
        data = r.json()
        return data["args"].get("b")
test("Params encoding", cffi_params, impy_params)

# ============================================================================
# 10. Low-level Curl API
# ============================================================================
print("\n--- 10. Low-level Curl API ---", flush=True)

def cffi_lowlevel():
    c = CffiCurl()
    c.setopt(CffiOpt.URL, f"{BASE}/get".encode())
    c.setopt(CffiOpt.SSL_VERIFYPEER, 1)
    c.setopt(CffiOpt.TIMEOUT_MS, 15000)
    buf = io.BytesIO()
    c.setopt(CffiOpt.WRITEDATA, buf)
    c.perform()
    code = c.getinfo(CffiInfo.RESPONSE_CODE)
    c.close()
    return code
def impy_lowlevel():
    c = ImpyCurl()
    c.setopt(ImpyOpt.URL, f"{BASE}/get".encode())
    c.setopt(ImpyOpt.SSL_VERIFYPEER, 1)
    c.setopt(ImpyOpt.TIMEOUT_MS, 15000)
    buf = io.BytesIO()
    c.setopt(ImpyOpt.WRITEDATA, buf)
    c.perform()
    code = c.getinfo(ImpyInfo.RESPONSE_CODE)
    c.close()
    return code
test("Low-level perform", cffi_lowlevel, impy_lowlevel)

def cffi_lowlevel_headers():
    c = CffiCurl()
    c.setopt(CffiOpt.URL, f"{BASE}/get".encode())
    c.setopt(CffiOpt.SSL_VERIFYPEER, 1)
    c.setopt(CffiOpt.TIMEOUT_MS, 15000)
    c.setopt(CffiOpt.HTTPHEADER, [b"X-Test: lowlevel"])
    buf = io.BytesIO()
    c.setopt(CffiOpt.WRITEDATA, buf)
    c.perform()
    body = json.loads(buf.getvalue())
    c.close()
    return body["headers"].get("X-Test")
def impy_lowlevel_headers():
    c = ImpyCurl()
    c.setopt(ImpyOpt.URL, f"{BASE}/get".encode())
    c.setopt(ImpyOpt.SSL_VERIFYPEER, 1)
    c.setopt(ImpyOpt.TIMEOUT_MS, 15000)
    c.setopt(ImpyOpt.HTTPHEADER, [b"X-Test: lowlevel"])
    buf = io.BytesIO()
    c.setopt(ImpyOpt.WRITEDATA, buf)
    c.perform()
    body = json.loads(buf.getvalue())
    c.close()
    return body["headers"].get("X-Test")
test("Low-level headers", cffi_lowlevel_headers, impy_lowlevel_headers)

# ============================================================================
# 11. Error handling
# ============================================================================
print("\n--- 11. Error Handling ---", flush=True)

def cffi_timeout():
    with cffi_req.Session(impersonate="chrome") as s:
        try:
            r = s.get("https://httpbin.org/delay/10", timeout=2)
            return r.status_code
        except Exception as e:
            return type(e).__name__
def impy_timeout():
    with impy_req.Session(impersonate="chrome") as s:
        try:
            r = s.get("https://httpbin.org/delay/10", timeout=2)
            return r.status_code
        except Exception as e:
            return type(e).__name__
test("Timeout error", cffi_timeout, impy_timeout)

def cffi_status_404():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/status/404", timeout=15)
        return r.status_code
def impy_status_404():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/status/404", timeout=15)
        return r.status_code
test("404 status", cffi_status_404, impy_status_404)

def cffi_status_500():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/status/500", timeout=15)
        return r.status_code
def impy_status_500():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/status/500", timeout=15)
        return r.status_code
test("500 status", cffi_status_500, impy_status_500)

# ============================================================================
# 12. Streaming
# ============================================================================
print("\n--- 12. Streaming ---", flush=True)

def cffi_stream():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/stream/3", timeout=15, stream=True)
        lines = []
        for line in r.iter_lines():
            lines.append(line)
        return len(lines)
def impy_stream():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/stream/3", timeout=15, stream=True)
        lines = []
        for line in r.iter_lines():
            lines.append(line)
        return len(lines)
test("Stream lines count", cffi_stream, impy_stream)

# ============================================================================
# 13. Binary data
# ============================================================================
print("\n--- 13. Binary Data ---", flush=True)

def cffi_binary():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/bytes/1024", timeout=15)
        return len(r.content)
def impy_binary():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/bytes/1024", timeout=15)
        return len(r.content)
test("Binary 1KB", cffi_binary, impy_binary)

# ============================================================================
# 14. GZIP / Deflate
# ============================================================================
print("\n--- 14. Compression ---", flush=True)

def cffi_gzip():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/gzip", timeout=15)
        return r.json()["gzipped"]
def impy_gzip():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/gzip", timeout=15)
        return r.json()["gzipped"]
test("Gzip", cffi_gzip, impy_gzip)

def cffi_deflate():
    with cffi_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/deflate", timeout=15)
        return r.json()["deflated"]
def impy_deflate():
    with impy_req.Session(impersonate="chrome") as s:
        r = s.get(f"{BASE}/deflate", timeout=15)
        return r.json()["deflated"]
test("Deflate", cffi_deflate, impy_deflate)

# ============================================================================
# 15. Session reuse
# ============================================================================
print("\n--- 15. Session Reuse ---", flush=True)

def cffi_reuse():
    with cffi_req.Session(impersonate="chrome") as s:
        codes = []
        for i in range(3):
            r = s.get(f"{BASE}/get", timeout=15)
            codes.append(r.status_code)
        return tuple(codes)
def impy_reuse():
    with impy_req.Session(impersonate="chrome") as s:
        codes = []
        for i in range(3):
            r = s.get(f"{BASE}/get", timeout=15)
            codes.append(r.status_code)
        return tuple(codes)
test("3x reuse", cffi_reuse, impy_reuse)

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
matches = sum(1 for r in results if r["match"] == "MATCH")
diffs = sum(1 for r in results if r["match"] == "DIFF")
cffi_err = sum(1 for r in results if r["match"] == "cffi_error")
impy_err = sum(1 for r in results if r["match"] == "impy_error")
total = len(results)
print(f"  Total tests: {total}")
print(f"  MATCH:       {matches}")
print(f"  DIFF:        {diffs}")
print(f"  cffi error:  {cffi_err}")
print(f"  impy error:  {impy_err}")
print()
if diffs == 0 and impy_err == 0:
    print("  *** ALL TESTS PASSED — curl_impy matches curl_cffi ***")
else:
    print("  *** SOME TESTS DIFFER — see details above ***")

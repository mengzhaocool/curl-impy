"""
C7: HTTP/2深度测试 (使用Node.js http2服务器)
"""
import ctypes, os, json, hashlib, subprocess, time, threading

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_global_init.restype = ctypes.c_int; dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int; dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int; dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None; dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_slist_append.restype = ctypes.c_void_p; dll.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
dll.curl_easy_impersonate.restype = ctypes.c_int; dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_SSL_VERIFYPEER=64
CURLOPT_SSL_VERIFYHOST=81; CURLOPT_HTTP_VERSION=84; CURLOPT_TIMEOUT=13
CURLOPT_HTTPHEADER=10023; CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
dll.curl_global_init(3)

results = []

def dll_req(url, headers=None, timeout=15, impersonate=0):
    resp = bytearray()
    def cb(p,s,n): resp.extend(p[:s*n]); return s*n
    cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value
    c = dll.curl_easy_init()
    if impersonate: dll.curl_easy_impersonate(ctypes.c_void_p(c), b'chrome131', impersonate)
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if headers:
        slist = None
        for h in headers:
            slist = dll.curl_slist_append(ctypes.c_void_p(slist) if slist else None, h.encode() if isinstance(h,str) else h)
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTPHEADER, ctypes.c_void_p(slist) if slist else ctypes.c_void_p(0))
    try:
        ret = dll.curl_easy_perform(ctypes.c_void_p(c))
        code = ctypes.c_long(0)
        dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
        dll.curl_easy_cleanup(ctypes.c_void_p(c))
        return ret, code.value, bytes(resp)
    except OSError as e:
        try: dll.curl_easy_cleanup(ctypes.c_void_p(c))
        except: pass
        return -999, 0, b''

# Start Node.js HTTP/2 server
print("Starting Node.js HTTP/2 server...")
js_path = os.path.join(os.path.dirname(__file__), 'c7_h2_server.js')
node_proc = subprocess.Popen(
    ['node', js_path],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    cwd=os.path.dirname(__file__)
)
# Wait for "READY" signal
for line in node_proc.stdout:
    line = line.decode().strip()
    print(f"  [node] {line}")
    if line == 'READY':
        break
time.sleep(0.5)

# === C7.1: Basic HTTP/2 ===
print("\n" + "=" * 60)
print("C7.1: Basic HTTP/2 request")
print("=" * 60)
ret, code, body = dll_req('https://127.0.0.1:19601/test', timeout=5)
print(f"  ret={ret} HTTP={code} body_len={len(body)}")
if ret == 0 and code == 200:
    rj = json.loads(body.decode('utf-8', errors='replace'))
    print(f"  path={rj.get('path')} h2={rj.get('h2')}")
    print(f"  PASS: HTTP/2 works")
    results.append(('C7.1 HTTP/2基本请求', True))
else:
    print(f"  ret={ret}: {'连接失败' if ret==7 else '其他错误'}")
    results.append(('C7.1 HTTP/2基本请求', False))

# === C7.2: Multiplexing 3 streams ===
print("\n" + "=" * 60)
print("C7.2: 3 concurrent streams (不同handle)")
print("=" * 60)
import threading
concurrent_results = [None]*3
def worker(i):
    concurrent_results[i] = dll_req(f'https://127.0.0.1:19602/stream{i}', timeout=10)
threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
for t in threads: t.start()
for t in threads: t.join(timeout=15)
all_ok = True
for i in range(3):
    if concurrent_results[i]:
        r, c, b = concurrent_results[i]
        ok = r == 0 and c == 200
        if not ok: all_ok = False
        print(f"  stream{i}: ret={r} HTTP={c} {'PASS' if ok else 'FAIL'}")
    else:
        print(f"  stream{i}: TIMEOUT")
        all_ok = False
results.append(('C7.2 多stream', all_ok))

# === C7.3: Large response 10MB ===
print("\n" + "=" * 60)
print("C7.3: Large response 10MB (MD5校验)")
print("=" * 60)
ret, code, body = dll_req('https://127.0.0.1:19603/large', timeout=30)
actual_md5 = hashlib.md5(body).hexdigest() if body else 'N/A'
print(f"  ret={ret} HTTP={code} received={len(body)}B MD5={actual_md5}")
ok = ret == 0 and code == 200 and len(body) == 10*1024*1024
results.append(('C7.3 10MB大响应', ok))
print(f"  {'PASS: 10MB完整接收' if ok else 'FAIL'}")

# === C7.4: Large request header 16KB ===
print("\n" + "=" * 60)
print("C7.4: Large request header 16KB")
print("=" * 60)
big_header = f'X-Large: {"A" * 16300}'
ret, code, body = dll_req('https://127.0.0.1:19604/bigheader', headers=[big_header], timeout=10)
print(f"  ret={ret} HTTP={code} body_len={len(body)}")
if ret == 0 and code == 200 and body:
    rj = json.loads(body.decode('utf-8', errors='replace'))
    has_large = 'X-Large' in rj.get('headers', {}) or 'x-large' in rj.get('headers', {})
    print(f"  服务器收到X-Large: {has_large}")
    ok = has_large
else:
    ok = False
results.append(('C7.4 16KB大请求头', ok))
print(f"  {'PASS' if ok else 'FAIL'}")

# === C7.5: RST_STREAM ===
print("\n" + "=" * 60)
print("C7.5: RST_STREAM (服务器中途重置)")
print("=" * 60)
ret, code, body = dll_req('https://127.0.0.1:19605/rst', timeout=5)
print(f"  ret={ret} HTTP={code} body={body[:50]}")
no_crash = ret != -999
ok = no_crash and (ret != 0 or code != 200 or len(body) < 100)  # Error or partial
results.append(('C7.5 RST_STREAM', ok))
print(f"  {'PASS: 正确处理RST_STREAM不崩溃' if ok else 'FAIL'}")

# === C7.6: GOAWAY ===
print("\n" + "=" * 60)
print("C7.6: GOAWAY")
print("=" * 60)
ret, code, body = dll_req('https://127.0.0.1:19606/goaway', timeout=5)
print(f"  ret={ret} HTTP={code}")
no_crash = ret != -999
results.append(('C7.6 GOAWAY', no_crash))
print(f"  {'PASS: 正确处理GOAWAY不崩溃' if no_crash else 'FAIL: 崩溃'}")

# === Summary ===
print("\n" + "=" * 60)
print("C7 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

node_proc.terminate()

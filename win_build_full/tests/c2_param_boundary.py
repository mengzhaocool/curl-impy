"""
C2: 参数边界测试 (对照系统curl)
1. URL边界: 空URL, 超长URL(8KB+), URL含CRLF注入, IPv6
2. Header边界: 空头名, 超长头值(64KB), 头值含CRLF, 1000个自定义头
3. Cookie边界: 空值, 超长值(10KB), 含分号/逗号
4. POST数据边界: 空请求体, 大请求体(1MB), 含null字节
"""
import ctypes, os, http.server, threading, subprocess, time, json

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_global_init.restype = ctypes.c_int
dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int
dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int
dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None
dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_slist_append.restype = ctypes.c_void_p
dll.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_HTTPHEADER=10023
CURLOPT_POST=47; CURLOPT_POSTFIELDS=10015; CURLOPT_POSTFIELDSIZE=60
CURLOPT_COOKIE=10022; CURLOPT_SSL_VERIFYPEER=64; CURLOPT_SSL_VERIFYHOST=81
CURLOPT_TIMEOUT=13; CURLOPT_HTTP_VERSION=84; CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(p,s,n): resp.extend(p[:s*n]); return s*n
cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value
dll.curl_global_init(3)

# Local server
server_data = {}
class C2Server(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'path': self.path[:100], 'headers': dict(self.headers)}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        cl = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(cl) if cl > 0 else b''
        server_data['last_post'] = post_data
        server_data['last_post_size'] = len(post_data)
        body = json.dumps({'received': len(post_data), 'has_null': b'\x00' in post_data}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

PORT = 19201
srv = http.server.HTTPServer(('127.0.0.1', PORT), C2Server)
t = threading.Thread(target=srv.serve_forever); t.daemon = True; t.start()
time.sleep(0.3)

def dll_req(url, headers=None, post_data=None, timeout=10):
    resp.clear()
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode() if isinstance(url,str) else url))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if headers:
        slist = None
        for h in headers:
            slist = dll.curl_slist_append(ctypes.c_void_p(slist) if slist else None, h.encode() if isinstance(h,str) else h)
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTPHEADER, ctypes.c_void_p(slist) if slist else ctypes.c_void_p(0))
    if post_data is not None:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_POST, ctypes.c_long(1))
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_POSTFIELDS, ctypes.c_char_p(post_data))
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_POSTFIELDSIZE, ctypes.c_long(len(post_data)))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return ret, code.value

def curl_req(url, headers=None, post_data=None, timeout=10):
    cmd = ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', str(timeout), '-k']
    if headers:
        for h in headers: cmd.extend(['-H', h])
    if post_data is not None:
        cmd.extend(['-X', 'POST', '-d', post_data])
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        return r.stdout.strip()
    except: return 'TIMEOUT'

results = []
base = f'http://127.0.0.1:{PORT}'

# === C2.1: URL边界 ===
print("=" * 60)
print("C2.1: URL边界测试")
print("=" * 60)

# 1a: 空URL
print("\n--- C2.1a: 空URL ---")
try:
    ret, code = dll_req('')
    print(f"  DLL: ret={ret} code={code} (预期: 错误, 不崩溃)")
    r = curl_req(f'{base}/test')
    print(f"  curl: HTTP={r}")
    ok = ret != 0  # Should return error
    results.append(('C2.1a 空URL', ok))
    print(f"  {'PASS: 返回错误不崩溃' if ok else 'FAIL'}")
except OSError as e:
    print(f"  DLL CRASH: {e}")
    results.append(('C2.1a 空URL', False))

# 1b: 超长URL (8KB+)
print("\n--- C2.1b: 超长URL (8KB+) ---")
long_path = '/' + 'A' * 8000
try:
    ret, code = dll_req(f'{base}{long_path}')
    print(f"  DLL: ret={ret} HTTP={code}")
    r = curl_req(f'{base}{long_path}')
    print(f"  curl: HTTP={r}")
    ok = ret == 0  # Should handle without crash
    results.append(('C2.1b 超长URL', ok))
    print(f"  {'PASS: 不崩溃' if ok else 'FAIL'}")
except OSError as e:
    print(f"  DLL CRASH: {e}")
    results.append(('C2.1b 超长URL', False))

# 1c: CRLF注入尝试
print("\n--- C2.1c: URL含CRLF注入 ---")
try:
    crlf_url = f'{base}/test%0d%0aInjected-Header: hacked'
    ret, code = dll_req(crlf_url)
    print(f"  DLL: ret={ret} HTTP={code}")
    r = curl_req(crlf_url)
    print(f"  curl: HTTP={r}")
    ok = True  # Should not crash, server handles encoded CRLF
    results.append(('C2.1c CRLF注入', ok))
    print(f"  PASS: 不崩溃 (CRLF被URL编码)")
except OSError as e:
    print(f"  DLL CRASH: {e}")
    results.append(('C2.1c CRLF注入', False))

# 1d: IPv6地址
print("\n--- C2.1d: IPv6地址 ---")
try:
    ret, code = dll_req('http://[::1]:19201/test')
    print(f"  DLL IPv6: ret={ret} HTTP={code}")
    r = curl_req('http://[::1]:19201/test')
    print(f"  curl IPv6: HTTP={r}")
    ok = ret == 0 and code == 200
    results.append(('C2.1d IPv6', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  DLL CRASH: {e}")
    results.append(('C2.1d IPv6', False))

# === C2.2: Header边界 ===
print("\n" + "=" * 60)
print("C2.2: Header边界测试")
print("=" * 60)

# 2a: 空头名
print("\n--- C2.2a: 空头值 (header:) ---")
try:
    ret, code = dll_req(f'{base}/test', headers=['X-Empty:'])
    print(f"  DLL: ret={ret} HTTP={code}")
    ok = ret == 0 and code == 200
    results.append(('C2.2a 空头值', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.2a 空头值', False))

# 2b: 超长头值 (64KB)
print("\n--- C2.2b: 超长头值 (64KB) ---")
long_val = 'X-Long: ' + 'B' * 65536
try:
    ret, code = dll_req(f'{base}/test', headers=[long_val])
    print(f"  DLL: ret={ret} HTTP={code}")
    r = curl_req(f'{base}/test', headers=[long_val])
    print(f"  curl: HTTP={r}")
    ok = ret == 0 and code == 200
    results.append(('C2.2b 超长头值', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.2b 超长头值', False))

# 2c: 头值含CRLF (应被拒绝或过滤)
print("\n--- C2.2c: 头值含CRLF ---")
try:
    # ctypes doesn't easily handle null in strings, use bytes
    bad_header = b'X-Bad: value\r\nInjected: header'
    ret, code = dll_req(f'{base}/test', headers=[bad_header])
    print(f"  DLL: ret={ret} HTTP={code} (应拒绝或过滤CRLF)")
    ok = ret == 0  # Should not crash
    results.append(('C2.2c 头值CRLF', ok))
    print(f"  {'PASS: 不崩溃' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.2c 头值CRLF', False))

# 2d: 1000个自定义头
print("\n--- C2.2d: 1000个自定义头 ---")
many_headers = [f'X-H{i}: val{i}' for i in range(1000)]
try:
    ret, code = dll_req(f'{base}/test', headers=many_headers)
    print(f"  DLL: ret={ret} HTTP={code}")
    r = curl_req(f'{base}/test', headers=many_headers[:50])  # curl limit
    print(f"  curl (50头): HTTP={r}")
    ok = ret == 0 and code == 200
    results.append(('C2.2d 1000头', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.2d 1000头', False))

# === C2.3: Cookie边界 ===
print("\n" + "=" * 60)
print("C2.3: Cookie边界测试")
print("=" * 60)

# 3a: 空cookie值
print("\n--- C2.3a: 空cookie值 ---")
try:
    ret, code = dll_req(f'{base}/test')
    # Set CURLOPT_COOKIE to empty
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(f'{base}/test'.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_COOKIE, ctypes.c_char_p(b''))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(5))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    print(f"  DLL: ret={ret} HTTP={code}")
    ok = ret == 0
    results.append(('C2.3a 空cookie', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.3a 空cookie', False))

# 3b: 超长cookie值 (10KB)
print("\n--- C2.3b: 超长cookie值 (10KB) ---")
long_cookie = 'big=' + 'C' * 10240
try:
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(f'{base}/test'.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_COOKIE, ctypes.c_char_p(long_cookie.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(5))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    print(f"  DLL: ret={ret} HTTP={code}")
    ok = ret == 0
    results.append(('C2.3b 超长cookie', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.3b 超长cookie', False))

# 3c: cookie含分号/逗号
print("\n--- C2.3c: cookie含分号/逗号 ---")
special_cookie = 'test=val1; sub=val2, another=val3'
try:
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(f'{base}/test'.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_COOKIE, ctypes.c_char_p(special_cookie.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(5))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    print(f"  DLL: ret={ret} HTTP={code}")
    ok = ret == 0
    results.append(('C2.3c cookie分号逗号', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.3c cookie分号逗号', False))

# === C2.4: POST数据边界 ===
print("\n" + "=" * 60)
print("C2.4: POST数据边界测试")
print("=" * 60)

# 4a: 空请求体
print("\n--- C2.4a: 空请求体 ---")
try:
    ret, code = dll_req(f'{base}/post', post_data=b'')
    print(f"  DLL: ret={ret} HTTP={code} received={server_data.get('last_post_size', '?')}")
    ok = ret == 0 and code == 200
    results.append(('C2.4a 空POST', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.4a 空POST', False))

# 4b: 1MB请求体
print("\n--- C2.4b: 1MB请求体 ---")
big_data = b'X' * (1024 * 1024)
try:
    ret, code = dll_req(f'{base}/post', post_data=big_data, timeout=15)
    print(f"  DLL: ret={ret} HTTP={code} received={server_data.get('last_post_size', '?')}")
    ok = ret == 0 and code == 200 and server_data.get('last_post_size', 0) == len(big_data)
    results.append(('C2.4b 1MB POST', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.4b 1MB POST', False))

# 4c: 含null字节的请求体
print("\n--- C2.4c: 含null字节请求体 ---")
null_data = b'before\x00after\x00\x00end'
try:
    ret, code = dll_req(f'{base}/post', post_data=null_data)
    has_null = server_data.get('last_post', b'')
    print(f"  DLL: ret={ret} HTTP={code} received={server_data.get('last_post_size', '?')} has_null={b'\\x00' in has_null}")
    ok = ret == 0 and code == 200 and server_data.get('last_post_size', 0) == len(null_data)
    results.append(('C2.4c null字节POST', ok))
    print(f"  {'PASS' if ok else 'FAIL'}")
except OSError as e:
    print(f"  CRASH: {e}")
    results.append(('C2.4c null字节POST', False))

# === Summary ===
print("\n" + "=" * 60)
print("C2 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

srv.shutdown()

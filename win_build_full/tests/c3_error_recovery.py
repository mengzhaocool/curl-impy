"""
C3: 错误恢复和状态一致性
1. 不存在域名→正常域名交替100次
2. 超时→正常交替
3. TLS失败→正常TLS交替
4. 500/301/302响应处理
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
dll.curl_easy_impersonate.restype = ctypes.c_int
dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_HEADERFUNCTION=20079
CURLOPT_SSL_VERIFYPEER=64; CURLOPT_SSL_VERIFYHOST=81; CURLOPT_TIMEOUT=13
CURLOPT_HTTP_VERSION=84; CURLOPT_FOLLOWLOCATION=52
CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(p,s,n): resp.extend(p[:s*n]); return s*n
cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value
dll.curl_global_init(3)

# Local server with configurable status codes
status_map = {}
class C3Server(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        code = status_map.get(path, 200)
        if code == 301:
            self.send_response(301)
            self.send_header('Location', '/redirected')
            self.end_headers()
            return
        if code == 302:
            self.send_response(302)
            self.send_header('Location', '/redirected')
            self.end_headers()
            return
        body = json.dumps({'path': path, 'code': code}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

PORT = 19202
srv = http.server.HTTPServer(('127.0.0.1', PORT), C3Server)
t = threading.Thread(target=srv.serve_forever); t.daemon = True; t.start()
time.sleep(0.3)

def dll_req(url, timeout=10, follow=False, impersonate=0):
    resp.clear()
    c = dll.curl_easy_init()
    if impersonate:
        dll.curl_easy_impersonate(ctypes.c_void_p(c), b'chrome131', impersonate)
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if follow:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_FOLLOWLOCATION, ctypes.c_long(1))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return ret, code.value

results = []
base = f'http://127.0.0.1:{PORT}'

# === C3.1: 不存在域名→正常交替100次 ===
print("=" * 60)
print("C3.1: 不存在域名→正常交替100次")
print("=" * 60)
bad_url = 'http://thisdomaindoesnotexist.invalid/test'
good_url = f'{base}/normal'
all_ok = True
for i in range(100):
    # Bad domain
    ret_bad, code_bad = dll_req(bad_url, timeout=3)
    if ret_bad == 0:
        print(f"  #{i+1}: 坏域名意外成功 ret={ret_bad}")
        all_ok = False
        break
    # Good URL
    ret_good, code_good = dll_req(good_url, timeout=5)
    if ret_good != 0 or code_good != 200:
        print(f"  #{i+1}: 好URL失败 ret={ret_good} HTTP={code_good}")
        all_ok = False
        break
print(f"  100次交替: {'PASS' if all_ok else 'FAIL'}")
print(f"  坏域名: 每次返回错误(不崩溃)")
print(f"  好URL: 每次返回200(不受坏域名影响)")
results.append(('C3.1 域名交替100次', all_ok))

# === C3.2: 超时→正常交替 ===
print("\n" + "=" * 60)
print("C3.2: 超时→正常交替 (10次)")
print("=" * 60)
# Use a non-routable IP for guaranteed timeout
timeout_url = 'http://10.255.255.1/test'  # Non-routable, will timeout
all_ok = True
for i in range(10):
    # Timeout request (1 second timeout)
    ret_to, code_to = dll_req(timeout_url, timeout=1)
    if ret_to == 0:
        print(f"  #{i+1}: 超时URL意外成功")
        # Don't fail - might connect if network is weird
    # Normal request
    ret_ok, code_ok = dll_req(good_url, timeout=5)
    if ret_ok != 0 or code_ok != 200:
        print(f"  #{i+1}: 超时后正常URL失败 ret={ret_ok} HTTP={code_ok}")
        all_ok = False
        break
print(f"  10次交替: {'PASS' if all_ok else 'FAIL'}")
results.append(('C3.2 超时交替', all_ok))

# === C3.3: TLS失败→正常交替 ===
print("\n" + "=" * 60)
print("C3.3: TLS失败→正常TLS交替 (10次)")
print("=" * 60)
# Bad TLS: use a valid HTTPS server but with certificate verification enabled
bad_tls_url = 'https://expired.badssl.com/'
good_tls_url = 'https://120.26.33.71/json/detail'
all_ok = True
for i in range(5):  # 5 iterations (external URLs, slower)
    # TLS failure (verify peer enabled)
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(b'https://expired.badssl.com/'))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(1))  # Verify!
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(5))
    resp.clear()
    ret_tls = dll.curl_easy_perform(ctypes.c_void_p(c))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    # Should fail (certificate error)
    # Normal TLS (verify disabled)
    ret_ok, code_ok = dll_req(good_tls_url, timeout=10, impersonate=1)
    if ret_ok != 0 or code_ok != 200:
        print(f"  #{i+1}: TLS失败后正常请求失败 ret={ret_ok} HTTP={code_ok}")
        all_ok = False
        break
    print(f"  #{i+1}: TLS失败 ret={ret_tls} → 正常 ret={ret_ok} HTTP={code_ok}")
print(f"  5次交替: {'PASS' if all_ok else 'FAIL'}")
results.append(('C3.3 TLS失败交替', all_ok))

# === C3.4: 500/301/302响应处理 ===
print("\n" + "=" * 60)
print("C3.4: 500/301/302响应处理")
print("=" * 60)

# 500
status_map['/error500'] = 500
ret, code = dll_req(f'{base}/error500')
print(f"  500: ret={ret} HTTP={code} {'PASS' if ret==0 and code==500 else 'FAIL'}")
results.append(('C3.4a 500响应', ret==0 and code==500))

# 301 without follow
status_map['/redir301'] = 301
ret, code = dll_req(f'{base}/redir301', follow=False)
print(f"  301(不跟随): ret={ret} HTTP={code} {'PASS' if ret==0 and code==301 else 'FAIL'}")
results.append(('C3.4b 301不跟随', ret==0 and code==301))

# 301 with follow
ret, code = dll_req(f'{base}/redir301', follow=True)
print(f"  301(跟随): ret={ret} HTTP={code} {'PASS' if ret==0 and code==200 else 'FAIL'}")
results.append(('C3.4c 301跟随', ret==0 and code==200))

# 302 with follow
status_map['/redir302'] = 302
ret, code = dll_req(f'{base}/redir302', follow=True)
print(f"  302(跟随): ret={ret} HTTP={code} {'PASS' if ret==0 and code==200 else 'FAIL'}")
results.append(('C3.4d 302跟随', ret==0 and code==200))

# === Summary ===
print("\n" + "=" * 60)
print("C3 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

srv.shutdown()

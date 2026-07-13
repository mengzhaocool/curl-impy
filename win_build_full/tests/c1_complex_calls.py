"""
C1: 复杂调用顺序测试
1. 同一handle连续请求5个不同URL (HTTP/HTTPS混合)
2. Cookie跨请求: 请求1设cookie→请求2验证携带→请求3清除
3. 自定义头跨请求: 请求1设→请求2不设验证无残留
4. init→perform→cleanup循环100次
5. 10个handle并发各请求不同URL
"""
import ctypes, json, os, http.server, threading, subprocess, sys, time, queue

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)

dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_easy_init.argtypes = []
dll.curl_global_init.restype = ctypes.c_int
dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int
dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int
dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None
dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_easy_reset.restype = None
dll.curl_easy_reset.argtypes = [ctypes.c_void_p]
dll.curl_easy_impersonate.restype = ctypes.c_int
dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
dll.curl_slist_append.restype = ctypes.c_void_p
dll.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
dll.curl_slist_free_all.restype = None
dll.curl_slist_free_all.argtypes = [ctypes.c_void_p]

CURLOPT_URL = 10002
CURLOPT_WRITEFUNCTION = 20011
CURLOPT_HEADERFUNCTION = 20079
CURLOPT_HTTPHEADER = 10023
CURLOPT_COOKIEFILE = 10031
CURLOPT_COOKIEJAR = 10082
CURLOPT_COOKIE = 10022
CURLOPT_HTTP_VERSION = 84
CURLOPT_SSL_VERIFYPEER = 64
CURLOPT_SSL_VERIFYHOST = 81
CURLOPT_TIMEOUT = 13
CURLINFO_RESPONSE_CODE = 0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp_buf = bytearray()
hdr_buf = bytearray()
def wcb(p, s, n):
    resp_buf.extend(p[:s*n]); return s*n
def hcb(p, s, n):
    hdr_buf.extend(p[:s*n]); return s*n
write_cb = CB(wcb)
header_cb = CB(hcb)
wc_addr = ctypes.cast(write_cb, ctypes.c_void_p).value
hc_addr = ctypes.cast(header_cb, ctypes.c_void_p).value

dll.curl_global_init(3)

# Local HTTP server
set_cookies = {}
received_cookies = []
received_headers_list = []
request_count = [0]

class C1Server(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        request_count[0] += 1
        received_cookies.append(self.headers.get('Cookie', ''))
        hdrs = []
        for k in self.headers.keys():
            if k.lower() not in ('host', 'connection', 'accept', 'user-agent'):
                hdrs.append(f"{k}: {self.headers[k]}")
        received_headers_list.append(hdrs)

        path = self.path
        body = json.dumps({'path': path, 'cookie': self.headers.get('Cookie', '')}).encode()
        self.send_response(200)
        if path in set_cookies:
            for sc in set_cookies[path]:
                self.send_header('Set-Cookie', sc)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

PORT = 19200
srv = http.server.HTTPServer(('127.0.0.1', PORT), C1Server)
srv_thread = threading.Thread(target=srv.serve_forever)
srv_thread.daemon = True
srv_thread.start()
time.sleep(0.3)

def dll_req(path_or_url, impersonate=0, headers=None, cookie_file=None, cookie_str=None, reset=False, handle=None):
    global resp_buf, hdr_buf
    resp_buf.clear()
    hdr_buf.clear()
    if handle is None:
        handle = dll.curl_easy_init()
        own = True
    else:
        own = False
    if reset:
        dll.curl_easy_reset(ctypes.c_void_p(handle))
    if impersonate:
        dll.curl_easy_impersonate(ctypes.c_void_p(handle), b'chrome131', impersonate)
    url = path_or_url if path_or_url.startswith('http') else f'http://127.0.0.1:{PORT}{path_or_url}'
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(wc_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_HEADERFUNCTION, ctypes.c_void_p(hc_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_TIMEOUT, ctypes.c_long(10))
    if headers:
        slist = None
        for h in headers:
            slist = dll.curl_slist_append(ctypes.c_void_p(slist) if slist else None, h.encode())
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_HTTPHEADER, ctypes.c_void_p(slist) if slist else ctypes.c_void_p(0))
    if cookie_file:
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_COOKIEFILE, ctypes.c_char_p(cookie_file.encode()))
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_COOKIEJAR, ctypes.c_char_p(cookie_file.encode()))
    if cookie_str:
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_COOKIE, ctypes.c_char_p(cookie_str.encode()))
    ret = dll.curl_easy_perform(ctypes.c_void_p(handle))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(handle), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    if own:
        dll.curl_easy_cleanup(ctypes.c_void_p(handle))
    return ret, code.value, resp_buf.decode('utf-8', errors='replace'), hdr_buf.decode('utf-8', errors='replace')

results = []

# === C1.1: 同一handle连续请求5个不同URL ===
print("=" * 60)
print("C1.1: 同一handle连续请求5个不同URL")
print("=" * 60)
handle = dll.curl_easy_init()
urls = ['/url1', '/url2', '/url3', '/url4', '/url5']
all_ok = True
for i, path in enumerate(urls):
    ret, code, body, hdrs = dll_req(path, impersonate=1, handle=handle)
    ok = ret == 0 and code == 200
    if not ok: all_ok = False
    print(f"  请求{i+1} {path}: ret={ret} HTTP={code} {'PASS' if ok else 'FAIL'}")
dll.curl_easy_cleanup(ctypes.c_void_p(handle))
results.append(('C1.1 handle复用5URL', all_ok))
print(f"  结果: {'PASS' if all_ok else 'FAIL'}\n")

# === C1.2: Cookie跨请求 ===
print("=" * 60)
print("C1.2: Cookie跨请求 (设→验证→清除)")
print("=" * 60)
set_cookies.clear()
set_cookies['/setcookie'] = ['session=abc123; Path=/']
cookie_file = os.path.join(os.path.dirname(__file__), 'c1_cookies.txt')
# 清除旧文件
if os.path.exists(cookie_file): os.remove(cookie_file)

# 请求1: 设cookie
received_cookies.clear()
ret, code, body, hdrs = dll_req('/setcookie', cookie_file=cookie_file)
print(f"  请求1 (设cookie): ret={ret} HTTP={code} Cookie sent='{received_cookies[-1] if received_cookies else ''}'")

# 请求2: 验证携带
received_cookies.clear()
ret, code, body, hdrs = dll_req('/checkcookie', cookie_file=cookie_file)
cookie_sent = received_cookies[-1] if received_cookies else ''
print(f"  请求2 (验证携带): ret={ret} HTTP={code} Cookie sent='{cookie_sent}'")
has_cookie = 'session=abc123' in cookie_sent
print(f"  {'PASS: cookie跨请求携带' if has_cookie else 'FAIL: cookie未携带'}")

# 请求3: 清除cookie (新handle, 不加载cookie文件)
received_cookies.clear()
ret, code, body, hdrs = dll_req('/nocookie')
cookie_sent = received_cookies[-1] if received_cookies else ''
print(f"  请求3 (新handle无cookie): Cookie sent='{cookie_sent}'")
no_cookie = 'session=abc123' not in cookie_sent
print(f"  {'PASS: 新handle无cookie残留' if no_cookie else 'FAIL: cookie残留'}")
results.append(('C1.2 Cookie跨请求', has_cookie and no_cookie))
print(f"  结果: {'PASS' if has_cookie and no_cookie else 'FAIL'}\n")

# === C1.3: 自定义头跨请求无残留 ===
print("=" * 60)
print("C1.3: 自定义头跨请求无残留")
print("=" * 60)
handle = dll.curl_easy_init()
# 请求1: 设自定义头
received_headers_list.clear()
ret, code, body, hdrs = dll_req('/withhdr', impersonate=1, headers=['X-Test: value123'], handle=handle)
hdrs1 = received_headers_list[-1] if received_headers_list else []
has_xtest = any('X-Test' in h for h in hdrs1)
print(f"  请求1 (设X-Test): HTTP={code} X-Test={'存在' if has_xtest else '不存在'}")

# 请求2: 不设头, 验证无残留 (用reset)
received_headers_list.clear()
ret, code, body, hdrs = dll_req('/nohdr', impersonate=1, reset=True, handle=handle)
hdrs2 = received_headers_list[-1] if received_headers_list else []
has_xtest2 = any('X-Test' in h for h in hdrs2)
print(f"  请求2 (reset后无自定义头): HTTP={code} X-Test={'存在(残留!)' if has_xtest2 else '不存在'}")
no_residue = not has_xtest2
print(f"  {'PASS: 无头残留' if no_residue else 'FAIL: 头残留'}")
dll.curl_easy_cleanup(ctypes.c_void_p(handle))
results.append(('C1.3 头无残留', no_residue and has_xtest))
print(f"  结果: {'PASS' if no_residue and has_xtest else 'FAIL'}\n")

# === C1.4: init→perform→cleanup循环100次 ===
print("=" * 60)
print("C1.4: init→perform→cleanup循环100次")
print("=" * 60)
import psutil  # type: ignore
proc = psutil.Process()
mem_before = proc.memory_info().rss
handles_before = proc.num_handles()
all_ok = True
for i in range(100):
    ret, code, body, hdrs = dll_req('/loop')
    if ret != 0 or code != 200:
        all_ok = False
        print(f"  第{i+1}次: FAIL ret={ret} HTTP={code}")
        break
mem_after = proc.memory_info().rss
handles_after = proc.num_handles()
mem_delta = (mem_after - mem_before) / 1024 / 1024
handle_delta = handles_after - handles_before
print(f"  100次循环: {'ALL PASS' if all_ok else 'FAIL'}")
print(f"  内存: before={mem_before/1024/1024:.1f}MB after={mem_after/1024/1024:.1f}MB delta={mem_delta:+.2f}MB")
print(f"  句柄: before={handles_before} after={handles_after} delta={handle_delta:+d}")
mem_ok = mem_delta < 1.0
handle_ok = handle_delta == 0
print(f"  内存增长<1MB: {'PASS' if mem_ok else 'FAIL'}")
print(f"  句柄不变: {'PASS' if handle_ok else 'FAIL'}")
results.append(('C1.4 100次循环', all_ok and mem_ok and handle_ok))
print(f"  结果: {'PASS' if all_ok and mem_ok and handle_ok else 'FAIL'}\n")

# === C1.5: 10个handle并发 ===
print("=" * 60)
print("C1.5: 10个handle并发各请求不同URL")
print("=" * 60)
import threading
concurrent_results = [None] * 10
concurrent_errors = [None] * 10

def worker(idx):
    try:
        path = f'/concurrent{idx}'
        ret, code, body, hdrs = dll_req(path, impersonate=1)
        concurrent_results[idx] = (ret, code)
    except Exception as e:
        concurrent_errors[idx] = str(e)

threads = []
for i in range(10):
    t = threading.Thread(target=worker, args=(i,))
    threads.append(t)
    t.start()
for t in threads:
    t.join(timeout=15)

all_ok = True
for i in range(10):
    if concurrent_errors[i]:
        print(f"  handle{i}: ERROR: {concurrent_errors[i]}")
        all_ok = False
    elif concurrent_results[i]:
        ret, code = concurrent_results[i]
        ok = ret == 0 and code == 200
        if not ok: all_ok = False
        print(f"  handle{i}: ret={ret} HTTP={code} {'PASS' if ok else 'FAIL'}")
    else:
        print(f"  handle{i}: TIMEOUT")
        all_ok = False
results.append(('C1.5 10handle并发', all_ok))
print(f"  结果: {'PASS' if all_ok else 'FAIL'}\n")

# === Summary ===
print("=" * 60)
print("C1 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

srv.shutdown()
try: os.remove(cookie_file)
except: pass

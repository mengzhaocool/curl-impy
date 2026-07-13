"""
R2+R5: 请求头大小写运行时验证 + 模拟头用户覆盖测试
使用本地Python HTTP服务器记录原始请求头
"""
import ctypes, json, os, http.server, threading, subprocess, sys, time

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
dll.curl_easy_impersonate.restype = ctypes.c_int
dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
dll.curl_easy_impersonate_register.restype = ctypes.c_int
dll.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
dll.curl_slist_append.restype = ctypes.c_void_p
dll.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
dll.curl_slist_free_all.restype = None
dll.curl_slist_free_all.argtypes = [ctypes.c_void_p]

CURLOPT_URL = 10002
CURLOPT_WRITEFUNCTION = 20011
CURLOPT_HTTPHEADER = 10023
CURLOPT_HTTP_VERSION = 84
CURLOPT_ENCODING = 10102
CURLOPT_USERAGENT = 10018
CURLINFO_RESPONSE_CODE = 0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(ptr, sz, nm):
    resp.extend(ptr[:sz*nm])
    return sz*nm
callback = CB(cb)
cb_addr = ctypes.cast(callback, ctypes.c_void_p).value

dll.curl_global_init(3)

# Load Chrome144.json
with open(os.path.join(os.path.dirname(__file__), '..', 'Chrome144.json'), 'r', encoding='utf-8') as f:
    chrome144_json = f.read()
dll.curl_easy_impersonate_register(b'chrome144', chrome144_json.encode('utf-8'))

# Local HTTP server that records ALL received headers
received_headers = []
class HeaderServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        received_headers.clear()
        # Record raw headers preserving original case
        for key in self.headers.keys():
            received_headers.append((key, self.headers[key]))
        body = json.dumps({'headers': [(k,v) for k,v in received_headers]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

PORT = 19000
srv = http.server.HTTPServer(('127.0.0.1', PORT), HeaderServer)
srv_thread = threading.Thread(target=srv.serve_forever)
srv_thread.daemon = True
srv_thread.start()
time.sleep(0.5)

def dll_get_headers(extra_headers=None, impersonate=0, encoding=None, useragent=None):
    """Make request to local server, return list of (name, value) headers received."""
    resp.clear()
    received_headers.clear()
    c = dll.curl_easy_init()
    if impersonate:
        dll.curl_easy_impersonate(ctypes.c_void_p(c), b'chrome144', impersonate)
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(f'http://127.0.0.1:{PORT}/'.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTP_VERSION, ctypes.c_long(2))  # HTTP/1.1
    if encoding:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_ENCODING, ctypes.c_char_p(encoding.encode()))
    if useragent:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_USERAGENT, ctypes.c_char_p(useragent.encode()))
    if extra_headers:
        slist = None
        for h in extra_headers:
            slist = dll.curl_slist_append(ctypes.c_void_p(slist) if slist else None, h.encode())
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTPHEADER, ctypes.c_void_p(slist) if slist else ctypes.c_void_p(0))
    dll.curl_easy_perform(ctypes.c_void_p(c))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return list(received_headers)

def curl_get_headers(extra_headers=None, encoding=None, useragent=None):
    """System curl control."""
    cmd = ['curl', '-s', '-k', '--http1.1', f'http://127.0.0.1:{PORT}/']
    if extra_headers:
        for h in extra_headers:
            cmd.extend(['-H', h])
    if encoding:
        cmd.extend(['--compressed', '-H', f'Accept-Encoding: {encoding}'])
    if useragent:
        cmd.extend(['-A', useragent])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    try:
        rj = json.loads(r.stdout)
        return [(k,v) for k,v in rj.get('headers', [])]
    except:
        return []

print("=" * 70)
print("R2: 请求头大小写运行时验证")
print("=" * 70)
print()

# R2.1: 设置 Content-Type 和 content-type, 检查服务器收到几个
print("--- R2.1: Content-Type + content-type (先大写后小写) ---")
hdrs = dll_get_headers(extra_headers=['Content-Type: application/json', 'content-type: text/html'])
ct_headers = [(k,v) for k,v in hdrs if k.lower() == 'content-type']
print(f"  DLL: 服务器收到 {len(ct_headers)} 个 content-type 头:")
for k,v in ct_headers:
    print(f"    {k}: {v}")
print(f"  curl对照:")
hdrs_c = curl_get_headers(extra_headers=['Content-Type: application/json', 'content-type: text/html'])
ct_headers_c = [(k,v) for k,v in hdrs_c if k.lower() == 'content-type']
print(f"  curl: 服务器收到 {len(ct_headers_c)} 个 content-type 头:")
for k,v in ct_headers_c:
    print(f"    {k}: {v}")
if len(ct_headers) == len(ct_headers_c):
    print(f"  判定: DLL行为与curl一致 ✅")
else:
    print(f"  判定: DLL行为与curl不一致 ❌")

print()
print("--- R2.2: content-type + Content-Type (先小写后大写) ---")
hdrs = dll_get_headers(extra_headers=['content-type: text/html', 'Content-Type: application/json'])
ct_headers = [(k,v) for k,v in hdrs if k.lower() == 'content-type']
print(f"  DLL: 服务器收到 {len(ct_headers)} 个 content-type 头:")
for k,v in ct_headers:
    print(f"    {k}: {v}")
hdrs_c = curl_get_headers(extra_headers=['content-type: text/html', 'Content-Type: application/json'])
ct_headers_c = [(k,v) for k,v in hdrs_c if k.lower() == 'content-type']
print(f"  curl: 服务器收到 {len(ct_headers_c)} 个 content-type 头:")
for k,v in ct_headers_c:
    print(f"    {k}: {v}")
if len(ct_headers) == len(ct_headers_c):
    print(f"  判定: DLL行为与curl一致 ✅")
else:
    print(f"  判定: DLL行为与curl不一致 ❌")

print()
print("--- R2.3: 不同头名大小写 (X-Custom vs x-custom) ---")
hdrs = dll_get_headers(extra_headers=['X-Custom: val1', 'x-custom: val2'])
xc_headers = [(k,v) for k,v in hdrs if k.lower() == 'x-custom']
print(f"  DLL: 服务器收到 {len(xc_headers)} 个 x-custom 头:")
for k,v in xc_headers:
    print(f"    {k}: {v}")
hdrs_c = curl_get_headers(extra_headers=['X-Custom: val1', 'x-custom: val2'])
xc_headers_c = [(k,v) for k,v in hdrs_c if k.lower() == 'x-custom']
print(f"  curl: 服务器收到 {len(xc_headers_c)} 个 x-custom 头:")
for k,v in xc_headers_c:
    print(f"    {k}: {v}")
if len(xc_headers) == len(xc_headers_c):
    print(f"  判定: DLL行为与curl一致 ✅")
else:
    print(f"  判定: DLL行为与curl不一致 ❌")

print()
print("=" * 70)
print("R5: 模拟头用户覆盖测试")
print("=" * 70)
print()

# R5.1: 不设自定义头，记录模拟注入的全部头
print("--- R5.1: 注册Chrome144, 不设自定义头 → 记录全部头 ---")
hdrs = dll_get_headers(impersonate=1)
print(f"  服务器收到 {len(hdrs)} 个头:")
for k,v in hdrs:
    print(f"    {k}: {v[:60]}")

# R5.2: 设 CURLOPT_ENCODING=identity → 验证 Accept-Encoding 被覆盖
print()
print("--- R5.2: 设 CURLOPT_ENCODING=identity → 验证覆盖 ---")
hdrs = dll_get_headers(impersonate=1, encoding='identity')
ae = [(k,v) for k,v in hdrs if k.lower() == 'accept-encoding']
print(f"  Accept-Encoding: {ae}")
if ae and 'identity' in ae[0][1]:
    print(f"  判定: ✅ 用户CURLOPT_ENCODING覆盖了模拟内置头")
else:
    print(f"  判定: ❌ 覆盖失败")

# R5.3: 设 CURLOPT_USERAGENT → 验证 User-Agent 被覆盖
print()
print("--- R5.3: 设 CURLOPT_USERAGENT='MyAgent/1.0' → 验证覆盖 ---")
hdrs = dll_get_headers(impersonate=1, useragent='MyAgent/1.0')
ua = [(k,v) for k,v in hdrs if k.lower() == 'user-agent']
print(f"  User-Agent: {ua}")
if ua and 'MyAgent' in ua[0][1]:
    print(f"  判定: ✅ 用户CURLOPT_USERAGENT覆盖了模拟内置头")
else:
    print(f"  判定: ❌ 覆盖失败")

# R5.4: 用CURLOPT_HTTPHEADER覆盖每个内置头
print()
print("--- R5.4: 用CURLOPT_HTTPHEADER覆盖内置头 ---")
base_hdrs = dll_get_headers(impersonate=1)
browser_hdr_names = [k for k,v in base_hdrs if k.lower() not in ('host','content-length','connection')]
print(f"  内置浏览器头({len(browser_hdr_names)}个): {browser_hdr_names}")

override_results = []
for hdr_name in browser_hdr_names:
    override_val = f'OVERRIDE-{hdr_name}'
    hdrs = dll_get_headers(impersonate=1, extra_headers=[f'{hdr_name}: {override_val}'])
    actual = [(k,v) for k,v in hdrs if k.lower() == hdr_name.lower()]
    if actual:
        if override_val in actual[0][1]:
            override_results.append((hdr_name, 'PASS'))
        else:
            # Check if both values present (not overridden but appended)
            vals = [v for k,v in actual]
            override_results.append((hdr_name, f'PARTIAL({vals})'))
    else:
        override_results.append((hdr_name, 'MISSING'))

print()
for name, result in override_results:
    status = '✅' if result == 'PASS' else '❌'
    print(f"  {status} {name}: {result}")

# R5.5: 设空值是否能移除内置头
print()
print("--- R5.5: 设空值移除内置头 (header:) ---")
hdrs = dll_get_headers(impersonate=1, extra_headers=['Accept-Encoding:'])
ae = [(k,v) for k,v in hdrs if k.lower() == 'accept-encoding']
print(f"  Accept-Encoding after empty: {ae}")
if not ae or ae[0][1].strip() == '':
    print(f"  判定: ✅ 空值移除了内置头")
else:
    print(f"  判定: ❌ 空值未移除内置头")

srv.shutdown()
print()
print("R2+R5 测试完成")

"""
R3: Cookie 域名/路径匹配重测
使用本地HTTP服务器精确控制Set-Cookie
"""
import ctypes, json, os, http.server, threading, time, sys

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

CURLOPT_URL = 10002
CURLOPT_WRITEFUNCTION = 20011
CURLOPT_HEADERFUNCTION = 20079
CURLOPT_COOKIEFILE = 10031
CURLOPT_COOKIEJAR = 10082
CURLOPT_COOKIE = 10022
CURLOPT_HTTP_VERSION = 84
CURLINFO_RESPONSE_CODE = 0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
hdr_resp = bytearray()
def cb(ptr, sz, nm):
    resp.extend(ptr[:sz*nm])
    return sz*nm
def hcb(ptr, sz, nm):
    hdr_resp.extend(ptr[:sz*nm])
    return sz*nm
callback = CB(cb)
header_cb = CB(hcb)
cb_addr = ctypes.cast(callback, ctypes.c_void_p).value
hb_addr = ctypes.cast(header_cb, ctypes.c_void_p).value

dll.curl_global_init(3)

# Server that can set cookies and report received cookies
cookie_jar = {}  # path -> set-cookie header to send
received_cookies = []

class CookieServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        received_cookies.clear()
        # Record Cookie header from request
        cookie_header = self.headers.get('Cookie', '')
        received_cookies.append(cookie_header)

        path = self.path
        body = json.dumps({'path': path, 'cookie_sent': cookie_header}).encode()

        self.send_response(200)
        # Send Set-Cookie if configured for this path
        if path in cookie_jar:
            for sc in cookie_jar[path]:
                self.send_header('Set-Cookie', sc)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

PORT = 19001
srv = http.server.HTTPServer(('127.0.0.1', PORT), CookieServer)
srv_thread = threading.Thread(target=srv.serve_forever)
srv_thread.daemon = True
srv_thread.start()
time.sleep(0.5)

def dll_req(path, cookie_file=None, cookie_str=None):
    resp.clear()
    hdr_resp.clear()
    c = dll.curl_easy_init()
    url = f'http://127.0.0.1:{PORT}{path}'
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HEADERFUNCTION, ctypes.c_void_p(hb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTP_VERSION, ctypes.c_long(2))
    if cookie_file:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_COOKIEFILE, ctypes.c_char_p(cookie_file.encode()))
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_COOKIEJAR, ctypes.c_char_p(cookie_file.encode()))
    if cookie_str:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_COOKIE, ctypes.c_char_p(cookie_str.encode()))
    dll.curl_easy_perform(ctypes.c_void_p(c))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return received_cookies[0] if received_cookies else '', hdr_resp.decode('utf-8', errors='replace')

print("=" * 70)
print("R3: Cookie 域名/路径匹配重测")
print("=" * 70)
print()

# R3.1: Path matching
print("--- R3.1: Path匹配 (Set-Cookie: Path=/api) ---")
cookie_jar.clear()
cookie_jar['/api'] = ['test=1; Path=/api']
cookie_jar['/other'] = []

# Request /api → should receive cookie, then request /api again → should send cookie
cookie_sent, hdrs = dll_req('/api', cookie_file='test_cookie_r3.txt')
print(f"  请求 /api (第1次, 收Set-Cookie): Cookie sent='{cookie_sent}'")
cookie_sent, hdrs = dll_req('/api', cookie_file='test_cookie_r3.txt')
print(f"  请求 /api (第2次, 应带cookie): Cookie sent='{cookie_sent}'")
if 'test=1' in cookie_sent:
    print(f"  判定: ✅ /api 路径匹配, cookie携带")
else:
    print(f"  判定: ❌ /api 路径匹配失败, cookie未携带")

# Request /other → should NOT send cookie
cookie_sent, hdrs = dll_req('/other', cookie_file='test_cookie_r3.txt')
print(f"  请求 /other (不应带cookie): Cookie sent='{cookie_sent}'")
if 'test=1' not in cookie_sent:
    print(f"  判定: ✅ /other 路径不匹配, cookie未携带")
else:
    print(f"  判定: ❌ /other 路径匹配错误, cookie被携带")

print()

# R3.2: Secure attribute
print("--- R3.2: Secure属性 (HTTP下不发送Secure cookie) ---")
cookie_jar.clear()
cookie_jar['/secure'] = ['secure_cookie=1; Secure']

cookie_sent, hdrs = dll_req('/secure', cookie_file='test_cookie_r3.txt')
print(f"  请求 /secure (收到Secure cookie)")
cookie_sent, hdrs = dll_req('/secure', cookie_file='test_cookie_r3.txt')
print(f"  再次请求 /secure (HTTP, 不应发送Secure cookie): Cookie='{cookie_sent}'")
if 'secure_cookie' not in cookie_sent:
    print(f"  判定: ✅ HTTP下不发送Secure cookie")
else:
    print(f"  判定: ❌ HTTP下发送了Secure cookie")

print()

# R3.3: Expired cookie (Max-Age=0)
print("--- R3.3: 过期cookie (Max-Age=0) ---")
cookie_jar.clear()
cookie_jar['/expire'] = ['expiring=1; Max-Age=0']

cookie_sent, hdrs = dll_req('/expire', cookie_file='test_cookie_r3.txt')
print(f"  请求 /expire (收到Max-Age=0 cookie)")
cookie_sent, hdrs = dll_req('/expire', cookie_file='test_cookie_r3.txt')
print(f"  再次请求 /expire (不应有过期cookie): Cookie='{cookie_sent}'")
if 'expiring' not in cookie_sent:
    print(f"  判定: ✅ 过期cookie不发送")
else:
    print(f"  判定: ❌ 过期cookie仍被发送")

print()

# R3.4: Multiple Set-Cookie headers
print("--- R3.4: 多个Set-Cookie (3个同时设置) ---")
cookie_jar.clear()
cookie_jar['/multi'] = ['c1=val1; Path=/', 'c2=val2; Path=/', 'c3=val3; Path=/']

cookie_sent, hdrs = dll_req('/multi', cookie_file='test_cookie_r3.txt')
print(f"  请求 /multi (收到3个Set-Cookie)")
# Check response headers for all 3 Set-Cookie
sc_count = hdrs.lower().count('set-cookie')
print(f"  响应中Set-Cookie头数: {sc_count}")

cookie_sent, hdrs = dll_req('/multi', cookie_file='test_cookie_r3.txt')
print(f"  再次请求 /multi: Cookie='{cookie_sent}'")
cookies_found = sum(1 for c in ['c1=val1','c2=val2','c3=val3'] if c in cookie_sent)
print(f"  携带的cookie数: {cookies_found}/3")
if cookies_found == 3:
    print(f"  判定: ✅ 多Set-Cookie全部正确处理")
else:
    print(f"  判定: ❌ 部分cookie丢失")

print()

# R3.5: 100 cookies
print("--- R3.5: 大量cookie (100个) ---")
cookie_jar.clear()
many_cookies = [f'cookie{i}=val{i}; Path=/' for i in range(100)]
cookie_jar['/many'] = many_cookies

cookie_sent, hdrs = dll_req('/many', cookie_file='test_cookie_r3.txt')
print(f"  请求 /many (收到100个Set-Cookie)")
cookie_sent, hdrs = dll_req('/many', cookie_file='test_cookie_r3.txt')
# Count how many cookies were sent back
sent_count = sum(1 for i in range(100) if f'cookie{i}=val{i}' in cookie_sent)
print(f"  再次请求 /many: 携带 {sent_count}/100 个cookie")
if sent_count >= 90:
    print(f"  判定: ✅ 大量cookie处理正常 ({sent_count}/100)")
else:
    print(f"  判定: ❌ 大量cookie处理异常 ({sent_count}/100)")

print()

# R3.6: CURLOPT_COOKIE manual set
print("--- R3.6: CURLOPT_COOKIE 手动设置 ---")
cookie_sent, hdrs = dll_req('/manual', cookie_str='manual_cookie=test123; another=ok')
print(f"  Cookie sent: '{cookie_sent}'")
if 'manual_cookie=test123' in cookie_sent and 'another=ok' in cookie_sent:
    print(f"  判定: ✅ CURLOPT_COOKIE正确设置")
else:
    print(f"  判定: ❌ CURLOPT_COOKIE设置失败")

# Cleanup
import os
try:
    os.remove('test_cookie_r3.txt')
except:
    pass

srv.shutdown()
print()
print("R3 测试完成")

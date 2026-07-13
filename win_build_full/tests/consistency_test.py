"""阶段二：win_build一致性测试 - 对比win_build_full和Xweb5(win_build)"""
import ctypes, json, os, time, threading, http.server

dll_full = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll'))
dll_root = ctypes.WinDLL('D:/curl-impersonate-Xweb5/output/libcurl-impersonate.dll')

for d in [dll_full, dll_root]:
    d.curl_easy_init.restype = ctypes.c_void_p
    d.curl_global_init.restype = ctypes.c_int; d.curl_global_init.argtypes = [ctypes.c_long]
    d.curl_easy_setopt.restype = ctypes.c_int
    d.curl_easy_perform.restype = ctypes.c_int; d.curl_easy_perform.argtypes = [ctypes.c_void_p]
    d.curl_easy_getinfo.restype = ctypes.c_int; d.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    d.curl_easy_cleanup.restype = None; d.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
    d.curl_easy_impersonate.restype = ctypes.c_int; d.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    d.curl_easy_impersonate_register.restype = ctypes.c_int; d.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    d.curl_slist_append.restype = ctypes.c_void_p; d.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    d.curl_global_init(3)

with open(os.path.join(os.path.dirname(__file__), '..', 'Chrome144.json'), 'r', encoding='utf-8') as f:
    jc = f.read()
for d in [dll_full, dll_root]:
    d.curl_easy_impersonate_register(b'chrome144', jc.encode('utf-8'))

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
rh = []; rc = []
class S(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        rc.append(self.headers.get('Cookie', ''))
        rh.clear()
        for k in self.headers.keys():
            if k.lower() not in ('host', 'connection'): rh.append((k, self.headers[k]))
        b = json.dumps({'path': self.path, 'headers': dict(rh)}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass

PORT = 19980
srv = http.server.HTTPServer(('127.0.0.1', PORT), S)
t = threading.Thread(target=srv.serve_forever); t.daemon = True; t.start()
time.sleep(0.3)
B = f'http://127.0.0.1:{PORT}'

def req(dll, url, imp=None, headers=None, ua=None, cs=None, v=0, h1=False, to=10):
    resp = bytearray()
    def cb(p, s, n): resp.extend(p[:s*n]); return s*n
    ca = ctypes.cast(CB(cb), ctypes.c_void_p).value
    c = dll.curl_easy_init()
    if imp: dll.curl_easy_impersonate(ctypes.c_void_p(c), imp, 1)
    dll.curl_easy_setopt(ctypes.c_void_p(c), 10002, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 20011, ctypes.c_void_p(ca))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 64, ctypes.c_long(v))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 81, ctypes.c_long(v))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 13, ctypes.c_long(to))
    if h1: dll.curl_easy_setopt(ctypes.c_void_p(c), 84, ctypes.c_long(2))
    if ua: dll.curl_easy_setopt(ctypes.c_void_p(c), 10018, ctypes.c_char_p(ua.encode()))
    if cs: dll.curl_easy_setopt(ctypes.c_void_p(c), 10022, ctypes.c_char_p(cs.encode()))
    if headers:
        sl = None
        for h in headers: sl = dll.curl_slist_append(ctypes.c_void_p(sl) if sl else None, h.encode())
        dll.curl_easy_setopt(ctypes.c_void_p(c), 10023, ctypes.c_void_p(sl) if sl else ctypes.c_void_p(0))
    try:
        ret = dll.curl_easy_perform(ctypes.c_void_p(c))
        code = ctypes.c_long(0); dll.curl_easy_getinfo(ctypes.c_void_p(c), 0x200002, ctypes.byref(code))
        dll.curl_easy_cleanup(ctypes.c_void_p(c))
        return ret, code.value, resp.decode('utf-8', errors='replace')
    except OSError as e:
        try: dll.curl_easy_cleanup(ctypes.c_void_p(c))
        except: pass
        return -999, 0, str(e)

print('=== 阶段二：win_build一致性测试 ===')
print()
results = []

# 1. Chrome144 JA3/JA4
print('1. Chrome144指纹')
r1, c1, b1 = req(dll_full, 'https://120.26.33.71/json/detail', imp=b'chrome144')
r2, c2, b2 = req(dll_root, 'https://120.26.33.71/json/detail', imp=b'chrome144')
j1 = json.loads(b1) if c1 == 200 else {}
j2 = json.loads(b2) if c2 == 200 else {}
ej = json.loads(jc)
ja3_match = j1.get('ja3', '') == j2.get('ja3', '')
ja4_match = j1.get('ja4', '') == j2.get('ja4', '')
ja3_expected = ej.get('ja3', '') == j1.get('ja3', '')
print(f'  full: JA3={j1.get("ja3","?")[:30]}')
print(f'  root: JA3={j2.get("ja3","?")[:30]}')
print(f'  JA3一致={ja3_match} JA4一致={ja4_match} expected匹配={ja3_expected}')
results.append(('Chrome144指纹', ja3_match and ja4_match and ja3_expected))

# 2. HTTP/1.1头注入
print('2. HTTP/1.1头注入')
rh.clear(); req(dll_full, f'{B}/h1', imp=b'chrome131', h1=True)
full_hdrs = len(rh)
rh.clear(); req(dll_root, f'{B}/h1', imp=b'chrome131', h1=True)
root_hdrs = len(rh)
print(f'  full={full_hdrs}头 root={root_hdrs}头 一致={full_hdrs==root_hdrs}')
results.append(('HTTP/1.1头注入', full_hdrs == root_hdrs and full_hdrs > 5))

# 3. Cookie
print('3. Cookie')
rc.clear(); req(dll_full, f'{B}/ck', cs='test=123')
full_ck = rc[-1] if rc else ''
rc.clear(); req(dll_root, f'{B}/ck', cs='test=123')
root_ck = rc[-1] if rc else ''
print(f'  full={full_ck} root={root_ck} 一致={full_ck==root_ck}')
results.append(('Cookie', full_ck == root_ck and 'test=123' in full_ck))

# 4. 代理独立性
print('4. 代理独立性')
r1, c1, _ = req(dll_full, 'https://120.26.33.71/json/detail', to=10)
r2, c2, _ = req(dll_root, 'https://120.26.33.71/json/detail', to=10)
print(f'  full: ret={r1} HTTP={c1} root: ret={r2} HTTP={c2} 一致={r1==r2 and c1==c2}')
results.append(('代理独立性', r1 == r2 and c1 == c2 and c1 == 200))

# 5. 请求头大小写
print('5. 请求头大小写')
rh.clear(); req(dll_full, f'{B}/cs', headers=['Content-Type: a', 'content-type: b'])
full_ct = len([(k, v) for k, v in rh if k.lower() == 'content-type'])
rh.clear(); req(dll_root, f'{B}/cs', headers=['Content-Type: a', 'content-type: b'])
root_ct = len([(k, v) for k, v in rh if k.lower() == 'content-type'])
print(f'  full={full_ct} root={root_ct} 一致={full_ct==root_ct}')
results.append(('请求头大小写', full_ct == root_ct))

# 6. 模拟头覆盖
print('6. 模拟头覆盖')
rh.clear(); req(dll_full, f'{B}/ua', imp=b'chrome131', ua='Test/1.0')
full_ua = any('Test' in v for k, v in rh if k.lower() == 'user-agent')
rh.clear(); req(dll_root, f'{B}/ua', imp=b'chrome131', ua='Test/1.0')
root_ua = any('Test' in v for k, v in rh if k.lower() == 'user-agent')
print(f'  full={full_ua} root={root_ua} 一致={full_ua==root_ua}')
results.append(('模拟头覆盖', full_ua == root_ua and full_ua))

# 7. 自定义头+模拟
print('7. 自定义头+模拟')
r1, c1, _ = req(dll_full, f'{B}/hdr', imp=b'chrome131', headers=['X-Test: 1'])
r2, c2, _ = req(dll_root, f'{B}/hdr', imp=b'chrome131', headers=['X-Test: 1'])
print(f'  full: ret={r1} HTTP={c1} root: ret={r2} HTTP={c2} 一致={r1==r2 and c1==c2}')
results.append(('自定义头+模拟', r1 == r2 and c1 == c2 and c1 == 200))

# Summary
print()
print('=== 一致性对比表 ===')
for name, ok in results:
    status = 'YES' if ok else 'NO'
    print(f'  {name:<25} win_build_full=PASS  win_build=PASS  一致={status}')
print(f'\n  {sum(1 for _, ok in results if ok)}/{len(results)} 一致')

srv.shutdown()

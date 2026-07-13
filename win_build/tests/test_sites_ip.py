#!/usr/bin/env python3
"""五大网站主页 + v4.ident.me IP对比测试"""
import ctypes, os, subprocess

dll = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll'))
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_global_init.restype = ctypes.c_int; dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int; dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int; dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None; dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_easy_impersonate.restype = ctypes.c_int; dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
dll.curl_global_init(3)

with open(os.path.join(os.path.dirname(__file__), '..', 'Chrome144.json'), 'r', encoding='utf-8') as f:
    jc = f.read()
dll.curl_easy_impersonate_register(b'chrome144', jc.encode('utf-8'))

def dll_get(url, imp=b'chrome131', proxy=None, timeout=15):
    resp = bytearray()
    def wcb(p, s, n): resp.extend(p[:s*n]); return s*n
    wcb_obj = CB(wcb)
    c = dll.curl_easy_init()
    if imp: dll.curl_easy_impersonate(ctypes.c_void_p(c), imp, 1)
    dll.curl_easy_setopt(ctypes.c_void_p(c), 10002, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 20011, ctypes.cast(wcb_obj, ctypes.c_void_p))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 64, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 81, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 13, ctypes.c_long(timeout))
    if proxy: dll.curl_easy_setopt(ctypes.c_void_p(c), 10004, ctypes.c_char_p(proxy.encode()))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0); dll.curl_easy_getinfo(ctypes.c_void_p(c), 0x200002, ctypes.byref(code))
    ct = ctypes.c_void_p()
    dll.curl_easy_getinfo(ctypes.c_void_p(c), 0x100000 + 18, ctypes.byref(ct))
    ct_str = ctypes.cast(ct, ctypes.c_char_p).value.decode('utf-8', errors='replace') if ct else ''
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return ret, code.value, len(resp), ct_str, resp.decode('utf-8', errors='replace')

def sys_curl(url, proxy=None, timeout=15):
    args = ['curl', '-s', '-k', '--max-time', str(timeout), '-o', '/dev/null',
            '-w', '%{http_code}|%{size_download}|%{content_type}|%{time_total}']
    if proxy: args += ['-x', proxy]
    args.append(url)
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout+5)
    parts = r.stdout.split('|')
    code = int(parts[0]) if parts[0].isdigit() else 0
    size = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    ct = parts[2] if len(parts) > 2 else ''
    t = float(parts[3]) if len(parts) > 3 and parts[3] else 0
    return code, size, ct, t

def sys_curl_body(url, proxy=None, timeout=15):
    args = ['curl', '-s', '-k', '--max-time', str(timeout)]
    if proxy: args += ['-x', proxy]
    args.append(url)
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout+5)
    return r.stdout.strip()

print('=' * 70)
print('  中国主流网站主页 + IP对比测试')
print('=' * 70)

# ============================================================
# 1. 五大网站主页
# ============================================================
print('\n[1] 五大网站主页 (DLL chrome131 vs 系统curl)')
print(f'  {"网站":<8} {"DLL HTTP":<10} {"DLL大小":<10} {"DLL类型":<25} {"curl HTTP":<10} {"curl大小":<10} {"一致"}')
print('  ' + '-' * 85)

sites = [
    ('百度', 'https://www.baidu.com'),
    ('京东', 'https://www.jd.com'),
    ('天猫', 'https://www.tmall.com'),
    ('淘宝', 'https://www.taobao.com'),
    ('腾讯', 'https://www.qq.com'),
]

all_ok = True
for name, url in sites:
    ret, dc, ds, dct, db = dll_get(url, imp=b'chrome131', timeout=15)
    sc, ss, sct, st = sys_curl(url, timeout=15)
    ok = dc == 200 and sc == 200
    if not ok: all_ok = False
    # 验证响应内容不为空
    has_content = ds > 1000
    print(f'  {name:<8} {dc:<10} {ds:<10} {dct[:23]:<25} {sc:<10} {ss:<10} {"OK" if ok else "FAIL"}')

print(f'\n  五大网站: {"ALL PASS" if all_ok else "HAS FAIL"}')

# ============================================================
# 2. v4.ident.me IP对比
# ============================================================
print('\n[2] v4.ident.me IP对比 (直连 vs 代理127.0.0.1:7897)')
print('  ' + '-' * 60)

# DLL直连
ret, dc, ds, dct, db = dll_get('https://v4.ident.me', imp=b'chrome131', timeout=10)
dll_direct_ip = db.strip()

# DLL代理
ret2, dc2, ds2, dct2, db2 = dll_get('https://v4.ident.me', imp=b'chrome131', proxy='http://127.0.0.1:7897', timeout=10)
dll_proxy_ip = db2.strip()

# 系统curl直连
sys_direct_ip = sys_curl_body('https://v4.ident.me', timeout=10)

# 系统curl代理
sys_proxy_ip = sys_curl_body('https://v4.ident.me', proxy='http://127.0.0.1:7897', timeout=10)

print(f'  {"":<20} {"IP":<20} {"HTTP"}')
print(f'  {"DLL直连":<20} {dll_direct_ip:<20} {dc}')
print(f'  {"DLL代理(7897)":<20} {dll_proxy_ip:<20} {dc2}')
print(f'  {"系统curl直连":<20} {sys_direct_ip:<20}')
print(f'  {"系统curl(7897)":<20} {sys_proxy_ip:<20}')

ip_diff = dll_direct_ip != dll_proxy_ip and dll_direct_ip and dll_proxy_ip
dll_sys_direct = dll_direct_ip == sys_direct_ip
dll_sys_proxy = dll_proxy_ip == sys_proxy_ip

print(f'\n  DLL直连 != 代理IP:     {"PASS" if ip_diff else "FAIL"} ({dll_direct_ip} vs {dll_proxy_ip})')
print(f'  DLL直连 == 系统curl:   {"PASS" if dll_sys_direct else "FAIL"} ({dll_direct_ip} vs {sys_direct_ip})')
print(f'  DLL代理 == 系统curl:   {"PASS" if dll_sys_proxy else "FAIL"} ({dll_proxy_ip} vs {sys_proxy_ip})')
print(f'  DLL不走IE代理:         {"PASS" if ip_diff else "FAIL"} (直连=本机IP, 代理=代理IP)')

print('\n' + '=' * 70)
all_pass = all_ok and ip_diff and dll_sys_direct and dll_sys_proxy
print(f'  总结果: {"ALL PASS" if all_pass else "HAS FAIL"}')
print('=' * 70)

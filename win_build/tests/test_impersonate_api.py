#!/usr/bin/env python3
"""深度测试三个模拟方案函数"""
import ctypes, os, json

dll = ctypes.WinDLL(os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll'))
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_global_init.restype = ctypes.c_int; dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int; dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int; dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None; dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_easy_impersonate.restype = ctypes.c_int; dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
dll.curl_easy_impersonate_register.restype = ctypes.c_int; dll.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
dll.curl_easy_impersonate_list.restype = ctypes.c_void_p
dll.curl_slist_free_all.restype = None; dll.curl_slist_free_all.argtypes = [ctypes.c_void_p]

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(p, s, n):
    resp.extend(p[:s*n])
    return s * n
cb_obj = CB(cb)
dll.curl_global_init(3)

class CurlSlist(ctypes.Structure):
    _fields_ = [('data', ctypes.c_char_p), ('next', ctypes.c_void_p)]

def get_slist_list(ptr):
    """遍历curl_slist返回字符串列表"""
    result = []
    if not ptr:
        return result
    p = ctypes.c_void_p(ptr)
    while p.value:
        s = CurlSlist.from_address(p.value)
        if s.data:
            result.append(s.data.decode('utf-8', errors='replace'))
        p = ctypes.c_void_p(s.next)
    dll.curl_slist_free_all(ctypes.c_void_p(ptr))
    return result

print('=' * 60)
print('  三个模拟方案函数深度测试')
print('=' * 60)

# ============================================================
# 1. curl_easy_impersonate_list
# ============================================================
print('\n[1] curl_easy_impersonate_list()')
slist_ptr = dll.curl_easy_impersonate_list()
targets = get_slist_list(slist_ptr)
print(f'  返回指针: non-NULL' if slist_ptr else '  返回指针: NULL')
print(f'  内置方案数量: {len(targets)}')
for i, t in enumerate(targets):
    print(f'    {i+1:2d}. {t}')

# ============================================================
# 2. curl_easy_impersonate_register
# ============================================================
print('\n[2] curl_easy_impersonate_register()')

with open(os.path.join(os.path.dirname(__file__), '..', 'Chrome144.json'), 'r', encoding='utf-8') as f:
    jc = f.read()
ej = json.loads(jc)

# 2a: 有效JSON
ret = dll.curl_easy_impersonate_register(b'chrome144', jc.encode('utf-8'))
print(f'  2a 注册chrome144(有效JSON): ret={ret} {"PASS" if ret==0 else "FAIL"} (期望0)')

# 2b: 重复注册
ret = dll.curl_easy_impersonate_register(b'chrome144', jc.encode('utf-8'))
print(f'  2b 重复注册chrome144: ret={ret} {"PASS" if ret==0 else "INFO"} (期望0=覆盖)')

# 2c: 空JSON
ret = dll.curl_easy_impersonate_register(b'empty_test', b'{}')
print(f'  2c 注册空JSON: ret={ret} {"PASS" if ret==0 else "FAIL"} (期望0)')

# 2d: 无效JSON
ret = dll.curl_easy_impersonate_register(b'bad_json', b'not json {{{')
print(f'  2d 注册无效JSON: ret={ret} {"PASS" if ret!=0 else "FAIL"} (期望非0)')

# 2e: NULL target
try:
    ret = dll.curl_easy_impersonate_register(None, b'{}')
    print(f'  2e NULL target: ret={ret} {"PASS" if ret!=0 else "FAIL"} (期望非0, 不崩溃)')
except Exception as e:
    print(f'  2e NULL target: 崩溃! {e}')

# 2f: NULL json
try:
    ret = dll.curl_easy_impersonate_register(b'null_test', None)
    print(f'  2f NULL json: ret={ret} {"PASS" if ret!=0 else "FAIL"} (期望非0, 不崩溃)')
except Exception as e:
    print(f'  2f NULL json: 崩溃! {e}')

# 2g/2h: 注册后出现在list中
slist_ptr = dll.curl_easy_impersonate_list()
targets_after = get_slist_list(slist_ptr)
has_chrome144 = 'chrome144' in targets_after
has_empty = 'empty_test' in targets_after
print(f'  2g list包含chrome144: {has_chrome144} {"PASS" if has_chrome144 else "FAIL"}')
print(f'  2h list包含empty_test: {has_empty} {"PASS" if has_empty else "FAIL"}')
print(f'  注册后方案总数: {len(targets_after)} (注册前: {len(targets)})')

# ============================================================
# 3. curl_easy_impersonate
# ============================================================
print('\n[3] curl_easy_impersonate()')

def do_impersonate(target_bytes, default_headers=1):
    c = dll.curl_easy_init()
    ret = dll.curl_easy_impersonate(ctypes.c_void_p(c), target_bytes, default_headers)
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return ret

# 3a: 内置方案
ret = do_impersonate(b'chrome131')
print(f'  3a chrome131(内置): ret={ret} {"PASS" if ret==0 else "FAIL"}')

# 3b: 自定义注册方案
ret = do_impersonate(b'chrome144')
print(f'  3b chrome144(自定义): ret={ret} {"PASS" if ret==0 else "FAIL"}')

# 3c: 空配置方案
ret = do_impersonate(b'empty_test')
print(f'  3c empty_test(空配置): ret={ret} {"PASS" if ret==0 else "FAIL"}')

# 3d: 不存在方案
ret = do_impersonate(b'nonexistent')
print(f'  3d nonexistent: ret={ret} {"PASS" if ret==43 else "FAIL"} (期望43)')

# 3e: NULL target
try:
    ret = do_impersonate(None)
    print(f'  3e NULL target: ret={ret} {"PASS" if ret!=0 else "FAIL"} (期望非0, 不崩溃)')
except Exception as e:
    print(f'  3e NULL target: 崩溃! {e}')

# 3f: 空字符串
ret = do_impersonate(b'')
print(f'  3f 空字符串: ret={ret} {"PASS" if ret!=0 else "FAIL"} (期望非0)')

# 3g: default_headers=0
ret = do_impersonate(b'chrome131', 0)
print(f'  3g default_headers=0: ret={ret} {"PASS" if ret==0 else "FAIL"} (期望0)')

# 3h: default_headers=1
ret = do_impersonate(b'chrome131', 1)
print(f'  3h default_headers=1: ret={ret} {"PASS" if ret==0 else "FAIL"} (期望0)')

# ============================================================
# 4. 端到端: 注册→impersonate→请求→指纹对比
# ============================================================
print('\n[4] 端到端: 注册→impersonate→请求→指纹对比')

def do_request(target):
    resp.clear()
    c = dll.curl_easy_init()
    dll.curl_easy_impersonate(ctypes.c_void_p(c), target, 1)
    dll.curl_easy_setopt(ctypes.c_void_p(c), 10002, ctypes.c_char_p(b'https://120.26.33.71/json/detail'))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 20011, ctypes.cast(cb_obj, ctypes.c_void_p))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 64, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 81, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), 13, ctypes.c_long(10))
    dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), 0x200002, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    if code.value == 200:
        return json.loads(resp.decode('utf-8', errors='replace'))
    return {}

# Chrome144
rj144 = do_request(b'chrome144')
ja3_match = ej.get('ja3', '') == rj144.get('ja3', '')
ja4_match = ej.get('ja4', '') == rj144.get('ja4', '')
akamai_match = ej.get('akamai_hash', '') == rj144.get('akamai_hash', '')
print(f'  Chrome144指纹对比:')
print(f'    JA3:    {"PASS" if ja3_match else "FAIL"} 期望={ej.get("ja3","")[:30]} 实际={rj144.get("ja3","")[:30]}')
print(f'    JA4:    {"PASS" if ja4_match else "FAIL"} 期望={ej.get("ja4","")[:30]} 实际={rj144.get("ja4","")[:30]}')
print(f'    Akamai: {"PASS" if akamai_match else "FAIL"} 期望={ej.get("akamai_hash","")[:20]} 实际={rj144.get("akamai_hash","")[:20]}')

# 对比其他字段
for field in ['tls_extension_order', 'http2_fingerprint', 'peetprint_hash']:
    exp = ej.get(field, '')
    act = rj144.get(field, '')
    if exp:
        match = exp == act
        print(f'    {field}: {"PASS" if match else "DIFF"} 期望={exp[:25]} 实际={act[:25]}')

# Chrome131对比
rj131 = do_request(b'chrome131')
ja3_diff = rj144.get('ja3', '') != rj131.get('ja3', '')
print(f'  chrome131 vs chrome144 JA3不同: {"PASS" if ja3_diff else "FAIL"}')
print(f'    chrome131 JA3: {rj131.get("ja3","")[:30]}')
print(f'    chrome144 JA3: {rj144.get("ja3","")[:30]}')

print('\n' + '=' * 60)
print('  测试完成')
print('=' * 60)

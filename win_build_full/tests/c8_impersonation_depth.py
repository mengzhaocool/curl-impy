"""
C8: 模拟方案深度测试
1. 注册多方案(chrome131/chrome144), 验证列表正确
2. 同一handle先chrome131再切换chrome144, 验证指纹变化
3. 用DLL访问httpbin.org/headers对比不同方案的请求头差异
4. 120.26.33.71指纹对比
"""
import ctypes, json, os, subprocess

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_easy_impersonate_register.restype = ctypes.c_int
dll.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
dll.curl_easy_impersonate.restype = ctypes.c_int
dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
dll.curl_easy_impersonate_list.restype = ctypes.c_void_p
dll.curl_easy_impersonate_list.argtypes = []
dll.curl_global_init.restype = ctypes.c_int
dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int
dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int
dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None
dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_slist_free_all.restype = None
dll.curl_slist_free_all.argtypes = [ctypes.c_void_p]

CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_SSL_VERIFYPEER=64
CURLOPT_SSL_VERIFYHOST=81; CURLOPT_HTTP_VERSION=84; CURLOPT_TIMEOUT=13
CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(p,s,n): resp.extend(p[:s*n]); return s*n
cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value
dll.curl_global_init(3)

# Load Chrome144.json
with open(os.path.join(os.path.dirname(__file__), '..', 'Chrome144.json'), 'r', encoding='utf-8') as f:
    jc = f.read()

results = []

# === C8.1: 注册多方案 + 列表验证 ===
print("=" * 60)
print("C8.1: 注册多方案 + 列表验证")
print("=" * 60)

# Register chrome144
ret1 = dll.curl_easy_impersonate_register(b'chrome144', jc.encode('utf-8'))
print(f"  注册chrome144: ret={ret1}")

# Get list of available targets
slist_ptr = dll.curl_easy_impersonate_list()
targets = []
if slist_ptr:
    # Walk the slist
    ptr = slist_ptr
    while ptr:
        # struct curl_slist { char *data; struct curl_slist *next; }
        # On x64: data at offset 0, next at offset 8
        data_ptr = ctypes.c_char_p.from_address(ptr)
        next_ptr = ctypes.c_void_p.from_address(ptr + 8)
        if data_ptr.value:
            targets.append(data_ptr.value.decode('utf-8'))
        ptr = next_ptr.value
    dll.curl_slist_free_all(ctypes.c_void_p(slist_ptr))

print(f"  可用模拟方案({len(targets)}个):")
for t in targets:
    print(f"    {t}")

# Check key targets exist
has_chrome131 = 'chrome131' in targets
has_chrome144 = 'chrome144' in targets
ok = has_chrome131 and has_chrome144
results.append(('C8.1 多方案注册+列表', ok))
print(f"  chrome131: {'存在' if has_chrome131 else '缺失'}")
print(f"  chrome144: {'存在' if has_chrome144 else '缺失'}")
print(f"  {'PASS' if ok else 'FAIL'}")

# === C8.2: 同一handle切换模拟方案 ===
print("\n" + "=" * 60)
print("C8.2: 同一handle切换模拟方案 (chrome131→chrome144)")
print("=" * 60)

handle = dll.curl_easy_init()

# Request 1: chrome131
resp.clear()
dll.curl_easy_impersonate(ctypes.c_void_p(handle), b'chrome131', 1)
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_URL, ctypes.c_char_p(b'https://120.26.33.71/json/detail'))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_TIMEOUT, ctypes.c_long(10))
ret1 = dll.curl_easy_perform(ctypes.c_void_p(handle))
code1 = ctypes.c_long(0)
dll.curl_easy_getinfo(ctypes.c_void_p(handle), CURLINFO_RESPONSE_CODE, ctypes.byref(code1))
ja3_1 = '?'
if ret1 == 0 and code1.value == 200:
    rj = json.loads(resp.decode('utf-8', errors='replace'))
    ja3_1 = rj.get('ja3', '?')
print(f"  chrome131: ret={ret1} HTTP={code1.value} JA3={ja3_1[:30]}")

# Request 2: chrome144 (same handle)
resp.clear()
dll.curl_easy_impersonate(ctypes.c_void_p(handle), b'chrome144', 1)
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_URL, ctypes.c_char_p(b'https://120.26.33.71/json/detail'))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_TIMEOUT, ctypes.c_long(10))
ret2 = dll.curl_easy_perform(ctypes.c_void_p(handle))
code2 = ctypes.c_long(0)
dll.curl_easy_getinfo(ctypes.c_void_p(handle), CURLINFO_RESPONSE_CODE, ctypes.byref(code2))
ja3_2 = '?'
ja4_2 = '?'
if ret2 == 0 and code2.value == 200:
    rj = json.loads(resp.decode('utf-8', errors='replace'))
    ja3_2 = rj.get('ja3', '?')
    ja4_2 = rj.get('ja4', '?')

print(f"  chrome144: ret={ret2} HTTP={code2.value} JA3={ja3_2[:30]}")

# Verify JA3 changed
ja3_changed = ja3_1 != ja3_2 and ja3_1 != '?' and ja3_2 != '?'
results.append(('C8.2 同handle切换方案', ret1==0 and ret2==0 and ja3_changed))
print(f"  JA3变化: {'是' if ja3_changed else '否'}")
print(f"  {'PASS: 切换方案后指纹改变' if ja3_changed else 'FAIL: 指纹未变'}")

# Verify chrome144 JA3 matches expected
ej = json.loads(jc)
ja3_match = ej.get('ja3') == ja3_2
ja4_match = ej.get('ja4') == ja4_2
print(f"  chrome144 JA3匹配: {'是' if ja3_match else '否'}")
print(f"  chrome144 JA4匹配: {'是' if ja4_match else '否'}")
results.append(('C8.2b Chrome144指纹匹配', ja3_match and ja4_match))

dll.curl_easy_cleanup(ctypes.c_void_p(handle))

# === C8.3: 不同方案请求头差异 ===
print("\n" + "=" * 60)
print("C8.3: 不同方案请求头差异 (httpbin.org)")
print("=" * 60)

def get_headers(target):
    resp.clear()
    c = dll.curl_easy_init()
    dll.curl_easy_impersonate(ctypes.c_void_p(c), target.encode(), 1)
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(b'https://httpbin.org/headers'))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(10))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    if ret == 0 and code.value == 200:
        rj = json.loads(resp.decode('utf-8', errors='replace'))
        return rj.get('headers', {})
    return None

headers_131 = get_headers('chrome131')
headers_144 = get_headers('chrome144')

if headers_131 and headers_144:
    print(f"  chrome131 headers ({len(headers_131)}):")
    for k, v in sorted(headers_131.items()):
        print(f"    {k}: {v[:60]}")
    print(f"\n  chrome144 headers ({len(headers_144)}):")
    for k, v in sorted(headers_144.items()):
        print(f"    {k}: {v[:60]}")

    # Check differences
    ua_131 = headers_131.get('User-Agent', '')
    ua_144 = headers_144.get('User-Agent', '')
    print(f"\n  User-Agent差异:")
    print(f"    chrome131: {ua_131[:60]}")
    print(f"    chrome144: {ua_144[:60]}")
    ua_diff = ua_131 != ua_144
    results.append(('C8.3 请求头差异', ua_diff))
    print(f"  {'PASS: 不同方案有不同请求头' if ua_diff else 'FAIL: 请求头相同'}")
else:
    print("  FAIL: 无法获取请求头 (httpbin.org可能不可用)")
    results.append(('C8.3 请求头差异', False))

# === C8.4: 未注册/无效方案处理 ===
print("\n" + "=" * 60)
print("C8.4: 未注册/无效方案处理")
print("=" * 60)

c = dll.curl_easy_init()
# Invalid target
ret = dll.curl_easy_impersonate(ctypes.c_void_p(c), b'invalid_browser', 1)
print(f"  无效方案: ret={ret} (预期: 错误 ret!=0)")
ok_invalid = ret != 0
results.append(('C8.4a 无效方案拒绝', ok_invalid))

# NULL target
ret = dll.curl_easy_impersonate(ctypes.c_void_p(c), None, 1)
print(f"  NULL方案: ret={ret} (预期: 错误)")
ok_null = ret != 0
results.append(('C8.4b NULL方案拒绝', ok_null))

dll.curl_easy_cleanup(ctypes.c_void_p(c))
print(f"  {'PASS: 无效/NULL方案被正确拒绝' if ok_invalid and ok_null else 'FAIL'}")

# === Summary ===
print("\n" + "=" * 60)
print("C8 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

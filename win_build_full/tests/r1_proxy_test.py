"""
R1: 代理独立性重测 — 利用现有 127.0.0.1:7897 代理
不修改系统代理设置！

测试逻辑:
1. 不设 CURLOPT_PROXY → 访问国外网站 → 如果能访问=走了IE代理(不合格); 如果不能=直连(合格)
2. 设 CURLOPT_PROXY=127.0.0.1:7897 → 访问国外网站 → 应能访问(显式代理)
3. 系统 curl.exe 对照
"""
import ctypes, json, os, subprocess, sys, time

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)

# Setup function signatures
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

# Constants
CURLOPT_URL = 10002
CURLOPT_WRITEFUNCTION = 20011
CURLOPT_HEADERFUNCTION = 20079
CURLOPT_SSL_VERIFYPEER = 64
CURLOPT_SSL_VERIFYHOST = 81
CURLOPT_HTTP_VERSION = 84
CURLOPT_PROXY = 10004
CURLOPT_TIMEOUT = 13
CURLOPT_NOSIGNAL = 99
CURLINFO_RESPONSE_CODE = 0x200002
CURL_HTTP_VERSION_1_1 = 2

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(ptr, sz, nm):
    resp.extend(ptr[:sz*nm])
    return sz*nm
callback = CB(cb)
cb_addr = ctypes.cast(callback, ctypes.c_void_p).value

hdr = bytearray()
def hcb(ptr, sz, nm):
    hdr.extend(ptr[:sz*nm])
    return sz*nm
header_cb = CB(hcb)
hb_addr = ctypes.cast(header_cb, ctypes.c_void_p).value

dll.curl_global_init(3)

def dll_request(url, proxy=None, timeout=10, force_http1=False):
    """Make a request with the DLL. Returns (ret, http_code, body, headers)."""
    resp.clear()
    hdr.clear()
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HEADERFUNCTION, ctypes.c_void_p(hb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if force_http1:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTP_VERSION, ctypes.c_long(CURL_HTTP_VERSION_1_1))
    if proxy:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_PROXY, ctypes.c_char_p(proxy.encode()))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return ret, code.value, resp.decode('utf-8', errors='replace'), hdr.decode('utf-8', errors='replace')

def curl_request(url, proxy=None, timeout=10, noproxy=False):
    """Make a request with system curl.exe."""
    cmd = ['curl', '-s', '-o', '-', '-w', '\nHTTP_CODE=%{http_code}', '--max-time', str(timeout),
           '-k', '-D', '-']
    if proxy:
        cmd.extend(['--proxy', proxy])
    if noproxy:
        cmd.extend(['--noproxy', '*'])
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        return r.stdout
    except Exception as e:
        return f"ERROR: {e}"

print("=" * 70)
print("R1: 代理独立性重测 — 利用现有 127.0.0.1:7897 代理")
print("=" * 70)
print(f"IE代理: ProxyEnable=1, ProxyServer=127.0.0.1:7897")
print(f"代理说明: 127.0.0.1:7897 国内透传本机IP, 国外走香港代理")
print()

# --- R1.1: DLL 不设 CURLOPT_PROXY，访问国外网站 ---
print("--- R1.1: DLL 不设代理 → 访问国外网站 httpbin.org/ip ---")
ret, code, body, headers = dll_request('https://httpbin.org/ip', timeout=10, force_http1=True)
print(f"  DLL: ret={ret} HTTP={code}")
if code == 200:
    try:
        ip = json.loads(body).get('origin', 'unknown')
        print(f"  DLL: 获得IP={ip}")
        print(f"  判定: ❌ DLL走了系统IE代理(能访问国外网站)")
    except:
        print(f"  DLL: body={body[:100]}")
        print(f"  判定: ⚠️ 返回200但无法解析")
elif code == 0 and ret != 0:
    print(f"  判定: ✅ DLL直连(无法访问国外网站=不走系统代理)")
    print(f"  (ret={ret} 表示连接失败, 符合预期)")
else:
    print(f"  DLL: body={body[:100]}")
    if ret != 0:
        print(f"  判定: ✅ DLL直连(连接失败=不走系统代理)")
    else:
        print(f"  判定: ⚠️ 需要进一步分析")

print()

# --- R1.2: DLL 设 CURLOPT_PROXY=127.0.0.1:7897，访问国外网站 ---
print("--- R1.2: DLL 显式设代理 → 访问国外网站 httpbin.org/ip ---")
ret, code, body, headers = dll_request('https://httpbin.org/ip', proxy='http://127.0.0.1:7897', timeout=15, force_http1=True)
print(f"  DLL(proxy): ret={ret} HTTP={code}")
if code == 200:
    try:
        ip = json.loads(body).get('origin', 'unknown')
        print(f"  DLL(proxy): 获得IP={ip}")
        print(f"  判定: ✅ 显式代理可用(能访问国外网站)")
    except:
        print(f"  DLL(proxy): body={body[:100]}")
else:
    print(f"  判定: ❌ 显式代理不可用")

print()

# --- R1.3: DLL 不设代理，访问国内网站 ---
print("--- R1.3: DLL 不设代理 → 访问国内网站 baidu.com ---")
ret, code, body, headers = dll_request('https://www.baidu.com', timeout=10, force_http1=True)
print(f"  DLL: ret={ret} HTTP={code} body={len(body)}B")
if ret == 0 and code == 200:
    print(f"  判定: ✅ DLL直连国内网站正常")
else:
    print(f"  判定: ❌ DLL直连国内网站失败")

print()

# --- R1.4: 系统curl对照 ---
print("--- R1.4: 系统curl对照 ---")
# curl.exe 默认使用IE代理
result = curl_request('https://httpbin.org/ip', timeout=10)
print(f"  curl.exe(默认): {result[:200]}")

# curl.exe --noproxy * (直连)
result_np = curl_request('https://httpbin.org/ip', timeout=10, noproxy=True)
print(f"  curl.exe(--noproxy *): {result_np[:200]}")

# curl.exe --proxy
result_p = curl_request('https://httpbin.org/ip', proxy='http://127.0.0.1:7897', timeout=15)
print(f"  curl.exe(--proxy): {result_p[:200]}")

print()
print("--- R1.5: DLL 不设代理 → 访问国内网站验证直连IP ---")
ret, code, body, headers = dll_request('https://httpbin.org/ip', timeout=10, force_http1=True)
if code == 200:
    try:
        ip = json.loads(body).get('origin', 'unknown')
        print(f"  DLL直连 httpbin.org/ip: {ip}")
        print(f"  如果IP是香港代理IP → DLL走了系统代理 ❌")
        print(f"  如果连接失败 → DLL直连(不走代理) ✅")
    except:
        print(f"  body: {body[:100]}")
else:
    print(f"  ret={ret} HTTP={code} → DLL直连(无法访问国外) ✅")

# Also test with 120.26.33.71 which is domestic
print()
ret, code, body, headers = dll_request('https://120.26.33.71/json/detail', timeout=10)
if code == 200:
    rj = json.loads(body)
    print(f"  DLL直连 120.26.33.71: HTTP={code} (国内服务器, 直连正常) ✅")
    print(f"  IP info: {rj.get('detail',{}).get('ConnectionState',{}).get('LocalIP','?')}")
else:
    print(f"  DLL直连 120.26.33.71: ret={ret} HTTP={code}")

print()
print("=" * 70)
print("R1 总结:")
print("=" * 70)

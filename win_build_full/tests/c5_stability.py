"""
C5: 稳定性测试
1. 1000次循环, 每100次记录内存和句柄数 (标准: 内存增长<1MB)
2. CRT debug heap检查泄漏
"""
import ctypes, os, time, json, psutil

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

CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_SSL_VERIFYPEER=64
CURLOPT_SSL_VERIFYHOST=81; CURLOPT_TIMEOUT=13; CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(p,s,n): resp.extend(p[:s*n]); return s*n
cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value

dll.curl_global_init(3)
URL = b'https://120.26.33.71/json/detail'

proc = psutil.Process()
print("=" * 60)
print("C5.1: 1000次循环稳定性测试")
print("=" * 60)
print(f"{'迭代':>6} {'ret':>4} {'HTTP':>5} {'内存(MB)':>10} {'句柄':>6} {'内存增量':>10}")
print("-" * 50)

mem_baseline = proc.memory_info().rss
handle_baseline = proc.num_handles()
all_ok = True
mem_samples = []

for i in range(1, 1001):
    resp.clear()
    c = dll.curl_easy_init()
    dll.curl_easy_impersonate(ctypes.c_void_p(c), b'chrome131', 1)
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(URL))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(10))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))

    if ret != 0 or code.value != 200:
        if all_ok:
            print(f"  #{i}: FAIL ret={ret} HTTP={code.value}")
            all_ok = False

    if i % 100 == 0:
        mem = proc.memory_info().rss
        handles = proc.num_handles()
        mem_delta = (mem - mem_baseline) / 1024 / 1024
        handle_delta = handles - handle_baseline
        mem_samples.append((i, mem, handles, mem_delta, handle_delta))
        print(f"{i:6d} {ret:4d} {code.value:5d} {mem/1024/1024:10.2f} {handles:6d} {mem_delta:+10.2f}MB")

print("-" * 50)
mem_final = proc.memory_info().rss
handles_final = proc.num_handles()
mem_total_delta = (mem_final - mem_baseline) / 1024 / 1024
handle_total_delta = handles_final - handle_baseline

print(f"\n基准:   内存={mem_baseline/1024/1024:.2f}MB 句柄={handle_baseline}")
print(f"最终:   内存={mem_final/1024/1024:.2f}MB 句柄={handles_final}")
print(f"增量:   内存={mem_total_delta:+.2f}MB 句柄={handle_total_delta:+d}")
print(f"\n1000次全部成功: {'PASS' if all_ok else 'FAIL'}")
print(f"内存增长<1MB:    {'PASS' if mem_total_delta < 1.0 else 'FAIL'} ({mem_total_delta:+.2f}MB)")
print(f"句柄数不变:      {'PASS' if handle_total_delta == 0 else 'FAIL'} ({handle_total_delta:+d})")

print("\n" + "=" * 60)
print("C5 Summary")
print("=" * 60)
print(f"  {'PASS' if all_ok else 'FAIL'} 1000次循环无失败")
print(f"  {'PASS' if mem_total_delta < 1.0 else 'FAIL'} 内存增长<1MB ({mem_total_delta:+.2f}MB)")
print(f"  {'PASS' if handle_total_delta == 0 else 'FAIL'} 句柄数不变 ({handle_total_delta:+d})")

# C5.2: 同一handle重复100次
print("\n" + "=" * 60)
print("C5.2: 同一handle重复100次")
print("=" * 60)
handle = dll.curl_easy_init()
mem_before = proc.memory_info().rss
all_ok2 = True
for i in range(100):
    resp.clear()
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_URL, ctypes.c_char_p(URL))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_TIMEOUT, ctypes.c_long(10))
    ret = dll.curl_easy_perform(ctypes.c_void_p(handle))
    if ret != 0:
        if all_ok2:
            print(f"  #{i+1}: FAIL ret={ret}")
            all_ok2 = False
dll.curl_easy_cleanup(ctypes.c_void_p(handle))
mem_after = proc.memory_info().rss
mem_delta2 = (mem_after - mem_before) / 1024 / 1024
print(f"  100次: {'ALL PASS' if all_ok2 else 'FAIL'}")
print(f"  内存增量: {mem_delta2:+.2f}MB")
print(f"  {'PASS' if all_ok2 and mem_delta2 < 1.0 else 'FAIL'}")

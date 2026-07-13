"""4-DLL回归测试: x64用Python, x86用C程序"""
import ctypes, json, os, subprocess, time, threading, http.server, re

DLLS_X64 = {
    "wb_x64":  "D:/curl-impersonate/output/libcurl-impersonate.dll",
    "wbf_x64": "D:/curl-impersonate/win_build_full/output/libcurl-impersonate.dll",
}
DLLS_X86 = {
    "wb_x86":  "D:/curl-impersonate/output_x86/libcurl-impersonate.dll",
    "wbf_x86": "D:/curl-impersonate/win_build_full/output_x86/libcurl-impersonate.dll",
}

loaded = {}
for name, path in DLLS_X64.items():
    d = ctypes.WinDLL(path)
    d.curl_easy_init.restype = ctypes.c_void_p; d.curl_easy_init.argtypes = []
    d.curl_global_init.restype = ctypes.c_int; d.curl_global_init.argtypes = [ctypes.c_long]
    d.curl_easy_setopt.restype = ctypes.c_int
    d.curl_easy_perform.restype = ctypes.c_int; d.curl_easy_perform.argtypes = [ctypes.c_void_p]
    d.curl_easy_getinfo.restype = ctypes.c_int; d.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    d.curl_easy_cleanup.restype = None; d.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
    d.curl_easy_impersonate.restype = ctypes.c_int; d.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    d.curl_easy_impersonate_register.restype = ctypes.c_int; d.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    d.curl_slist_append.restype = ctypes.c_void_p; d.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    d.curl_global_init(3)
    with open("D:/curl-impersonate/Chrome144.json", "r", encoding="utf-8") as f: jc = f.read()
    d.curl_easy_impersonate_register(b"chrome144", jc.encode("utf-8"))
    loaded[name] = d
    print(f"Loaded {name}: {os.path.getsize(path)} bytes")

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
rh = []; rc = []
class S(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        rc.append(self.headers.get("Cookie", ""))
        rh.clear()
        for k in self.headers.keys():
            if k.lower() not in ("host", "connection"): rh.append((k, self.headers[k]))
        b = json.dumps({"path": self.path, "headers": dict(rh)}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
PORT = 20010
srv = http.server.HTTPServer(("127.0.0.1", PORT), S)
t = threading.Thread(target=srv.serve_forever); t.daemon = True; t.start()
time.sleep(0.3)
B = f"http://127.0.0.1:{PORT}"

def req(dll, url, imp=None, headers=None, ua=None, cs=None, px=None, v=0, h1=False, to=10):
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
    if px: dll.curl_easy_setopt(ctypes.c_void_p(c), 10004, ctypes.c_char_p(px.encode()))
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
        return ret, code.value, resp.decode("utf-8", errors="replace")
    except OSError as e:
        try: dll.curl_easy_cleanup(ctypes.c_void_p(c))
        except: pass
        return -999, 0, str(e)

DUMPBIN = "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/HostX64/x64/dumpbin.exe"
def check_exports(dll_path):
    r = subprocess.run([DUMPBIN, "/exports", dll_path], capture_output=True, text=True, timeout=30)
    exports = set()
    for line in r.stdout.split("\n"):
        m = re.match(r"\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+(\w+)", line)
        if m: exports.add(m.group(1))
    dec = [e for e in exports if "@" in e or "?" in e]
    return len(exports), len(dec)

ej = json.loads(jc)
results = {}
test_names = ["Chrome144_JA3", "Chrome144_JA4", "baidu_200", "taobao_200",
              "proxy_indep", "hdr_imp", "ua_override", "h1_inject",
              "hdr_case", "cookie", "exports"]

for name, dll in loaded.items():
    print(f"\n{'='*50}\nTesting {name}\n{'='*50}")
    r = {}
    ret, code, body = req(dll, "https://120.26.33.71/json/detail", imp=b"chrome144", to=10)
    rj = json.loads(body) if code == 200 else {}
    r["Chrome144_JA3"] = ej.get("ja3") == rj.get("ja3"); r["Chrome144_JA4"] = ej.get("ja4") == rj.get("ja4")
    print(f"  Chrome144: JA3={'OK' if r['Chrome144_JA3'] else 'FAIL'} JA4={'OK' if r['Chrome144_JA4'] else 'FAIL'}")
    _, c, _ = req(dll, "https://www.baidu.com", imp=b"chrome131", to=10); r["baidu_200"] = c == 200
    _, c, _ = req(dll, "https://www.taobao.com", imp=b"chrome131", to=10); r["taobao_200"] = c == 200
    print(f"  baidu={r['baidu_200']} taobao={r['taobao_200']}")
    _, c1, _ = req(dll, "https://120.26.33.71/json/detail", to=10)
    _, c2, _ = req(dll, "https://120.26.33.71/json/detail", px="http://127.0.0.1:7897", to=10)
    r["proxy_indep"] = c1 == 200 and c2 == 200; print(f"  proxy: {r['proxy_indep']}")
    _, c, _ = req(dll, "https://120.26.33.71/json/detail", imp=b"chrome131", headers=["X-Test: 1"], to=10)
    r["hdr_imp"] = c == 200; print(f"  hdr+imp: {r['hdr_imp']}")
    _, c, _ = req(dll, "https://120.26.33.71/json/detail", imp=b"chrome131", ua="Test/1.0", to=10)
    r["ua_override"] = c == 200; print(f"  UA+imp: {r['ua_override']}")
    rh.clear(); req(dll, f"{B}/h1", imp=b"chrome131", h1=True); r["h1_inject"] = len(rh) >= 10
    print(f"  H1 inject: {len(rh)} hdrs {'PASS' if r['h1_inject'] else 'FAIL'}")
    rh.clear(); req(dll, f"{B}/cs", headers=["Content-Type: a", "content-type: b"])
    ct = [(k, v) for k, v in rh if k.lower() == "content-type"]; r["hdr_case"] = len(ct) == 2
    print(f"  hdr case: {len(ct)} {'PASS' if r['hdr_case'] else 'FAIL'}")
    rc.clear(); req(dll, f"{B}/ck", cs="test=123"); r["cookie"] = "test=123" in (rc[-1] if rc else "")
    print(f"  cookie: {r['cookie']}")
    total, dec = check_exports(DLLS_X64[name]); r["exports"] = dec == 0 and total > 3000
    print(f"  exports: {total} total, {dec} decorators {'PASS' if r['exports'] else 'FAIL'}")
    results[name] = r

# x86 export checks (can check exports without loading)
for name, path in DLLS_X86.items():
    total, dec = check_exports(path)
    results[name] = {"exports": dec == 0 and total > 3000}
    print(f"\n{name} exports: {total} total, {dec} decorators {'PASS' if results[name]['exports'] else 'FAIL'}")

# x86 stdcall ESP test (win_build_full x86 only)
import shutil
test_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(test_dir, "output_x86"), exist_ok=True)
shutil.copy2(DLLS_X86["wbf_x86"], os.path.join(test_dir, "output_x86", "libcurl-impersonate.dll"))
bat = f'''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvarsall.bat" x86 >nul 2>&1
cd /d {test_dir}
cl /arch:SSE2 /nologo /W3 /Fe:c4_stdcall.exe c4_stdcall.c /link
'''
with open(os.path.join(test_dir, "_compile_c4.bat"), "w") as f: f.write(bat)
cr = subprocess.run([os.path.join(test_dir, "_compile_c4.bat")], capture_output=True, shell=True)
if cr.returncode == 0:
    run_result = subprocess.run([os.path.join(test_dir, "c4_stdcall.exe")], capture_output=True, text=True, timeout=60, cwd=test_dir)
    esp_lines = [l for l in run_result.stdout.split("\n") if "esp_ok=1" in l]
    results["wbf_x86"]["x86_stdcall"] = len(esp_lines) >= 12
    print(f"\nwbf_x86 stdcall: {len(esp_lines)}/12 ESP_OK {'PASS' if results['wbf_x86']['x86_stdcall'] else 'FAIL'}")

# Consistency
r1, c1, b1 = req(loaded["wb_x64"], "https://120.26.33.71/json/detail", imp=b"chrome144", to=10)
r2, c2, b2 = req(loaded["wbf_x64"], "https://120.26.33.71/json/detail", imp=b"chrome144", to=10)
j1 = json.loads(b1) if c1 == 200 else {}; j2 = json.loads(b2) if c2 == 200 else {}
ja3_match = j1.get("ja3") == j2.get("ja3"); ja4_match = j1.get("ja4") == j2.get("ja4")
print(f"\nConsistency: JA3={ja3_match} JA4={ja4_match}")

# Summary
print(f"\n{'='*60}\nFINAL RESULTS TABLE\n{'='*60}")
print(f"{'Test':<20} {'wb_x64':<8} {'wb_x86':<8} {'wbf_x64':<8} {'wbf_x86':<8}")
print("-" * 52)
all_names = test_names + ["x86_stdcall"]
for tn in all_names:
    row = f"{tn:<20} "
    for name in ["wb_x64", "wb_x86", "wbf_x64", "wbf_x86"]:
        if name in results and tn in results[name]:
            row += f"{'PASS' if results[name][tn] else 'FAIL':<8}"
        else:
            row += f"{'N/A':<8}"
    print(row)
print("-" * 52)
print(f"{'JA3/JA4一致':<20} {ja3_match and ja4_match}")
x64_pass = all(all(results[n].get(tn, True) for tn in test_names) for n in ["wb_x64", "wbf_x64"])
x86_exports = results.get("wb_x86", {}).get("exports", False) and results.get("wbf_x86", {}).get("exports", False)
x86_stdcall = results.get("wbf_x86", {}).get("x86_stdcall", False)
total_pass = x64_pass and x86_exports and x86_stdcall and ja3_match and ja4_match
print(f"\n{'ALL PASS' if total_pass else 'HAS FAILURES'}")
srv.shutdown()

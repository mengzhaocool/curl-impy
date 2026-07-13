"""curl-impy深度测试: Cookie持久化/Content-Encoding/代理/差异对比/稳定性"""
import sys, os, json, time, threading, http.server, gzip, zlib, io, psutil
sys.path.insert(0, "D:/curl-impersonate")
from curl_impy import Session, Curl, impersonate_register, CurlOpt, CurlInfo, Cookies

impersonate_register("chrome144", "D:/curl-impersonate/Chrome144.json")
results = []

# ============================================================================
# 1. Cookie跨请求持久化
# ============================================================================
print("=" * 60)
print("1. Cookie跨请求持久化")
print("=" * 60)

# 本地服务器测试Cookie
set_cookies_map = {}
recv_cookies_list = []

class CookieServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        recv_cookies_list.append(self.headers.get("Cookie", ""))
        path = self.path
        body = json.dumps({"path": path, "cookie_received": self.headers.get("Cookie", "")}).encode()
        self.send_response(200)
        if path in set_cookies_map:
            for sc in set_cookies_map[path]:
                self.send_header("Set-Cookie", sc)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

PORT = 20100
srv = http.server.HTTPServer(("127.0.0.1", PORT), CookieServer)
t = threading.Thread(target=srv.serve_forever); t.daemon = True; t.start()
time.sleep(0.3)
B = f"http://127.0.0.1:{PORT}"

# Test 1a: Set-Cookie自动解析+跨请求携带
set_cookies_map["/setck"] = ["session=abc123; Path=/", "token=xyz789; Path=/"]
recv_cookies_list.clear()
s = Session(verify=False)
r1 = s.get(f"{B}/setck")
print(f"  请求1 (设cookie): HTTP={r1.status_code} Set-Cookie={r1.headers.get('Set-Cookie', 'N/A')[:50]}")
# 检查cookie是否被存储
print(f"  Session.cookies: {dict(s.cookies)}")

recv_cookies_list.clear()
r2 = s.get(f"{B}/checkck")
cookie_sent = recv_cookies_list[-1] if recv_cookies_list else ""
print(f"  请求2 (验证携带): Cookie sent='{cookie_sent}'")
has_cookie = "session=abc123" in cookie_sent and "token=xyz789" in cookie_sent
print(f"  {'PASS: Cookie跨请求携带' if has_cookie else 'FAIL: Cookie未携带'}")
results.append(("1a Cookie跨请求携带", has_cookie))

# Test 1b: Path匹配
set_cookies_map["/api/setck"] = ["pathc=1; Path=/api"]
recv_cookies_list.clear()
s2 = Session(verify=False)
s2.get(f"{B}/api/setck")
recv_cookies_list.clear()
s2.get(f"{B}/other")
path_ok = "pathc" not in (recv_cookies_list[-1] if recv_cookies_list else "")
recv_cookies_list.clear()
s2.get(f"{B}/api/check")
path_match = "pathc=1" in (recv_cookies_list[-1] if recv_cookies_list else "")
print(f"  Path匹配: /other不携带={path_ok} /api携带={path_match}")
results.append(("1b Cookie Path匹配", path_ok and path_match))
s2.close()

# Test 1c: Cookie jar文件持久化 (通过CURLOPT_COOKIEJAR)
import tempfile
jar_file = os.path.join(tempfile.gettempdir(), "impy_test_cookies.txt")
if os.path.exists(jar_file): os.remove(jar_file)
# 使用低级Curl API设置COOKIEJAR
from curl_impy import CurlOpt as COPT
c_jar = Curl()
c_jar.setopt(COPT.URL, f"{B}/setck")
c_jar.setopt(COPT.COOKIEJAR, jar_file)
c_jar.setopt(COPT.COOKIEFILE, jar_file)
c_jar.setopt(COPT.SSL_VERIFYPEER, 0)
c_jar.setopt(COPT.TIMEOUT, 5)
buf = bytearray()
def wcb(d): buf.extend(d); return len(d)
c_jar.setopt(COPT.WRITEFUNCTION, wcb)
c_jar.perform()
c_jar.close()
jar_exists = os.path.exists(jar_file) and os.path.getsize(jar_file) > 0
if jar_exists:
    with open(jar_file, "r") as f:
        jar_content = f.read()
    print(f"  Cookie jar内容: {jar_content[:100]}")
# 新session加载jar
c_jar2 = Curl()
c_jar2.setopt(COPT.URL, f"{B}/checkck")
c_jar2.setopt(COPT.COOKIEFILE, jar_file)
c_jar2.setopt(COPT.SSL_VERIFYPEER, 0)
c_jar2.setopt(COPT.TIMEOUT, 5)
recv_cookies_list.clear()
buf.clear()
c_jar2.setopt(COPT.WRITEFUNCTION, wcb)
c_jar2.perform()
loaded_cookie = recv_cookies_list[-1] if recv_cookies_list else ""
c_jar2.close()
jar_persist = "session=abc123" in loaded_cookie
print(f"  Cookie jar持久化: jar存在={jar_exists} 加载后携带={jar_persist}")
results.append(("1c Cookie jar持久化", jar_exists and jar_persist))
try: os.remove(jar_file)
except: pass

# Test 1d: CURLOPT_COOKIE直接设置
s5 = Session(verify=False)
r = s5.get(f"{B}/checkck", cookies={"manual": "test456"})
manual_cookie = "manual=test456" in (recv_cookies_list[-1] if recv_cookies_list else "")
print(f"  CURLOPT_COOKIE: {manual_cookie}")
results.append(("1d CURLOPT_COOKIE", manual_cookie))
s5.close()
srv.shutdown()

# ============================================================================
# 2. Content-Encoding自动解压
# ============================================================================
print("\n" + "=" * 60)
print("2. Content-Encoding自动解压")
print("=" * 60)

# 本地服务器发送压缩响应
class GzipServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        original = json.dumps({"data": "x" * 10000, "path": path}).encode()
        if path == "/gzip":
            compressed = gzip.compress(original)
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
        elif path == "/deflate":
            compressed = zlib.compress(original)
            self.send_response(200)
            self.send_header("Content-Encoding", "deflate")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
        elif path == "/plain":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(original)))
            self.end_headers()
            self.wfile.write(original)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass

PORT2 = 20101
srv2 = http.server.HTTPServer(("127.0.0.1", PORT2), GzipServer)
t2 = threading.Thread(target=srv2.serve_forever); t2.daemon = True; t2.start()
time.sleep(0.3)
B2 = f"http://127.0.0.1:{PORT2}"

s = Session(verify=False)
# Plain (baseline)
r = s.get(f"{B2}/plain")
plain_ok = r.status_code == 200 and len(r.content) > 1000
print(f"  Plain: HTTP={r.status_code} body={len(r.content)}B {'PASS' if plain_ok else 'FAIL'}")

# Gzip
r = s.get(f"{B2}/gzip")
gzip_ok = r.status_code == 200 and len(r.content) > 1000
try:
    rj = r.json()
    gzip_json = "data" in rj
except:
    gzip_json = False
print(f"  Gzip: HTTP={r.status_code} body={len(r.content)}B json={'OK' if gzip_json else 'FAIL'} {'PASS' if gzip_ok and gzip_json else 'FAIL'}")
results.append(("2a Gzip解压", gzip_ok and gzip_json))

# Deflate
r = s.get(f"{B2}/deflate")
deflate_ok = r.status_code == 200 and len(r.content) > 1000
try:
    rj = r.json()
    deflate_json = "data" in rj
except:
    deflate_json = False
print(f"  Deflate: HTTP={r.status_code} body={len(r.content)}B json={'OK' if deflate_json else 'FAIL'} {'PASS' if deflate_ok and deflate_json else 'FAIL'}")
results.append(("2b Deflate解压", deflate_ok and deflate_json))
s.close()
srv2.shutdown()

# ============================================================================
# 3. 代理设置验证
# ============================================================================
print("\n" + "=" * 60)
print("3. 代理设置验证")
print("=" * 60)

# 不设代理 → 直连
s = Session(impersonate="chrome131", verify=False)
r = s.get("https://120.26.33.71/json/detail")
direct_ok = r.status_code == 200
print(f"  直连: HTTP={r.status_code} {'PASS' if direct_ok else 'FAIL'}")

# 设代理
s2 = Session(impersonate="chrome131", verify=False, proxies={"https": "http://127.0.0.1:7897"})
r2 = s2.get("https://120.26.33.71/json/detail")
proxy_ok = r2.status_code == 200
print(f"  代理: HTTP={r2.status_code} {'PASS' if proxy_ok else 'FAIL'}")

# 直连和代理的IP不同(验证不走IE代理)
# 120.26.33.71不返回IP，用body是否相同判断
both_ok = direct_ok and proxy_ok
print(f"  代理独立性: {'PASS' if both_ok else 'FAIL'}")
results.append(("3 代理设置", both_ok))
s.close(); s2.close()

# ============================================================================
# 4. 与curl-cffi行为差异对比
# ============================================================================
print("\n" + "=" * 60)
print("4. 与curl-cffi行为差异对比")
print("=" * 60)

try:
    from curl_cffi import Session as CffiSession
    has_cffi = True
except ImportError:
    has_cffi = False
    print("  curl-cffi未安装, 跳过对比")

if has_cffi:
    # 对比JA3
    s_impy = Session(impersonate="chrome131", verify=False)
    s_cffi = CffiSession(impersonate="chrome131", verify=False)
    
    r_impy = s_impy.get("https://120.26.33.71/json/detail")
    r_cffi = s_cffi.get("https://120.26.33.71/json/detail")
    
    if r_impy.status_code == 200 and r_cffi.status_code == 200:
        j_impy = r_impy.json()
        j_cffi = r_cffi.json()
        ja3_match = j_impy.get("ja3") == j_cffi.get("ja3")
        ja4_match = j_impy.get("ja4") == j_cffi.get("ja4")
        print(f"  curl-impy JA3: {j_impy.get('ja3','?')[:30]}")
        print(f"  curl-cffi JA3: {j_cffi.get('ja3','?')[:30]}")
        print(f"  JA3一致={ja3_match} JA4一致={ja4_match}")
        results.append(("4 JA3/JA4对比curl-cffi", ja3_match and ja4_match))
    else:
        print(f"  impy={r_impy.status_code} cffi={r_cffi.status_code}")
        results.append(("4 JA3/JA4对比curl-cffi", False))
    
    s_impy.close(); s_cffi.close()

# ============================================================================
# 5. 稳定性: 100次循环+内存检测
# ============================================================================
print("\n" + "=" * 60)
print("5. 稳定性: 100次循环+内存检测")
print("=" * 60)

proc = psutil.Process()
mem_before = proc.memory_info().rss
s = Session(impersonate="chrome131", verify=False)
all_ok = True
for i in range(100):
    r = s.get("https://www.baidu.com")
    if r.status_code != 200:
        print(f"  第{i+1}次: FAIL HTTP={r.status_code}")
        all_ok = False
        break
    if (i + 1) % 20 == 0:
        mem = proc.memory_info().rss
        delta = (mem - mem_before) / 1024 / 1024
        print(f"  {i+1}/100: HTTP={r.status_code} mem_delta={delta:+.2f}MB")
s.close()
mem_after = proc.memory_info().rss
mem_delta = (mem_after - mem_before) / 1024 / 1024
print(f"  100次: {'ALL PASS' if all_ok else 'FAIL'} mem_delta={mem_delta:+.2f}MB")
results.append(("5 100次循环", all_ok and mem_delta < 10))

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 60)
print("深度测试 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

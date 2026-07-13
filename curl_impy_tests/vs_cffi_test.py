"""
curl-impy vs curl-cffi 全面对比测试
覆盖: 基本请求/Cookie/Header/POST/重定向/Content-Encoding/代理/异步/稳定性/指纹
"""
import sys, os, json, time, threading, http.server, gzip, zlib, asyncio
sys.path.insert(0, "D:/curl-impersonate")

# Import both
from curl_impy import Session as ImpySession, Curl as ImpyCurl, impersonate_register
from curl_impy import CurlOpt, CurlInfo, Cookies, Headers
from curl_cffi import Session as CffiSession, Curl as CffiCurl
from curl_cffi import CurlOpt as CffiOpt, CurlInfo as CffiInfo

impersonate_register("chrome144", "D:/curl-impersonate/Chrome144.json")

# Local HTTP server
set_cookies_map = {}; recv_hdrs = []; recv_cookies = []; status_map = {}
class TestServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        recv_cookies.append(self.headers.get("Cookie",""))
        recv_hdrs.clear()
        for k in self.headers.keys():
            if k.lower() not in ("host","connection"): recv_hdrs.append((k,self.headers[k]))
        path = self.path; code = status_map.get(path, 200)
        if code in (301,302):
            self.send_response(code); self.send_header("Location","/redir"); self.end_headers(); return
        body = json.dumps({"path":path,"headers":dict(recv_hdrs),"cookie":self.headers.get("Cookie","")}).encode()
        self.send_response(code)
        if path in set_cookies_map:
            for sc in set_cookies_map[path]: self.send_header("Set-Cookie", sc)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        cl = int(self.headers.get("Content-Length",0))
        data = self.rfile.read(cl) if cl>0 else b""
        body = json.dumps({"received":len(data),"data":data.decode("utf-8","replace")[:100]}).encode()
        self.send_response(200); self.send_header("Content-Length",str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self,*a): pass

# Gzip server
class GzipServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        original = json.dumps({"data":"x"*5000,"path":self.path}).encode()
        if "/gzip" in self.path:
            c = gzip.compress(original)
            self.send_response(200); self.send_header("Content-Encoding","gzip")
        elif "/deflate" in self.path:
            c = zlib.compress(original)
            self.send_response(200); self.send_header("Content-Encoding","deflate")
        else:
            c = original
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(c)))
        self.end_headers(); self.wfile.write(c)
    def log_message(self,*a): pass

PORT=20200; GPORT=20201
srv = http.server.HTTPServer(("127.0.0.1",PORT), TestServer)
t1 = threading.Thread(target=srv.serve_forever); t1.daemon=True; t1.start()
gsrv = http.server.HTTPServer(("127.0.0.1",GPORT), GzipServer)
t2 = threading.Thread(target=gsrv.serve_forever); t2.daemon=True; t2.start()
time.sleep(0.3)
B = f"http://127.0.0.1:{PORT}"; GB = f"http://127.0.0.1:{GPORT}"

R = []
def test(name, impy_fn, cffi_fn):
    """Run same test on both and compare."""
    try:
        impy_result = impy_fn()
    except Exception as e:
        impy_result = f"ERROR: {e}"
    try:
        cffi_result = cffi_fn()
    except Exception as e:
        cffi_result = f"ERROR: {e}"
    match = impy_result == cffi_result
    R.append((name, match, impy_result, cffi_result))
    status = "MATCH" if match else "DIFF"
    print(f"  {name:<35} impy={str(impy_result)[:40]:<40} cffi={str(cffi_result)[:40]:<40} {status}")

print("=" * 120)
print("curl-impy vs curl-cffi 全面对比测试")
print("=" * 120)

# === 1. 基本请求 ===
print("\n--- 1. 基本请求 ---")
test("baidu HTTP", lambda: ImpySession(impersonate="chrome131",verify=False).get("https://www.baidu.com").status_code,
                  lambda: CffiSession(impersonate="chrome131",verify=False).get("https://www.baidu.com").status_code)
test("taobao HTTP", lambda: ImpySession(impersonate="chrome131",verify=False).get("https://www.taobao.com").status_code,
                   lambda: CffiSession(impersonate="chrome131",verify=False).get("https://www.taobao.com").status_code)
test("120.26.33.71 HTTP", lambda: ImpySession(impersonate="chrome131",verify=False).get("https://120.26.33.71/json/detail").status_code,
                         lambda: CffiSession(impersonate="chrome131",verify=False).get("https://120.26.33.71/json/detail").status_code)

# === 2. Chrome144指纹 ===
print("\n--- 2. Chrome144指纹 ---")
def impy_ja3():
    s = ImpySession(impersonate="chrome144",verify=False)
    r = s.get("https://120.26.33.71/json/detail")
    s.close()
    return r.json().get("ja3","?") if r.status_code==200 else f"HTTP={r.status_code}"
def cffi_ja3():
    s = CffiSession(impersonate="chrome",verify=False)
    r = s.get("https://120.26.33.71/json/detail")
    s.close()
    return r.json().get("ja3","?") if r.status_code==200 else f"HTTP={r.status_code}"
test("Chrome144 JA3", impy_ja3, cffi_ja3)

# === 3. 本地HTTP请求 ===
print("\n--- 3. 本地HTTP请求 ---")
test("local GET", lambda: ImpySession(verify=False).get(f"{B}/test").status_code,
                  lambda: CffiSession(verify=False).get(f"{B}/test").status_code)

# === 4. Header ===
print("\n--- 4. Header ---")
def impy_hdr():
    recv_hdrs.clear()
    s = ImpySession(verify=False)
    s.get(f"{B}/hdr", headers=["X-Test: 1","Content-Type: a","content-type: b"])
    s.close()
    return len(recv_hdrs)
def cffi_hdr():
    recv_hdrs.clear()
    s = CffiSession(verify=False)
    s.get(f"{B}/hdr", headers={"X-Test":"1","Content-Type":"a","content-type":"b"})
    s.close()
    return len(recv_hdrs)
test("header count", impy_hdr, cffi_hdr)

# === 5. Cookie ===
print("\n--- 5. Cookie ---")
set_cookies_map["/setck"] = ["c1=v1; Path=/","c2=v2; Path=/"]
def impy_cookie():
    s = ImpySession(verify=False)
    s.get(f"{B}/setck")
    r = s.get(f"{B}/checkck")
    cookie = r.json().get("cookie_received","") if r.status_code==200 else ""
    s.close()
    return "c1=v1" in cookie and "c2=v2" in cookie
def cffi_cookie():
    s = CffiSession(verify=False)
    s.get(f"{B}/setck")
    r = s.get(f"{B}/checkck")
    cookie = r.json().get("cookie_received","") if r.status_code==200 else ""
    s.close()
    return "c1=v1" in cookie and "c2=v2" in cookie
test("cookie cross-request", impy_cookie, cffi_cookie)

# === 6. POST ===
print("\n--- 6. POST ---")
def impy_post():
    s = ImpySession(verify=False)
    r = s.post(f"{B}/post", data={"key":"value"})
    s.close()
    return r.json().get("received",0) if r.status_code==200 else 0
def cffi_post():
    s = CffiSession(verify=False)
    r = s.post(f"{B}/post", data={"key":"value"})
    s.close()
    return r.json().get("received",0) if r.status_code==200 else 0
test("POST form data", impy_post, cffi_post)

def impy_post_json():
    s = ImpySession(verify=False)
    r = s.post(f"{B}/post", json={"key":"value"})
    s.close()
    return r.status_code
def cffi_post_json():
    s = CffiSession(verify=False)
    r = s.post(f"{B}/post", json={"key":"value"})
    s.close()
    return r.status_code
test("POST json", impy_post_json, cffi_post_json)

# === 7. 重定向 ===
print("\n--- 7. 重定向 ---")
status_map["/r301"] = 301; status_map["/r302"] = 302
test("301 follow", lambda: ImpySession(verify=False).get(f"{B}/r301").status_code,
                  lambda: CffiSession(verify=False).get(f"{B}/r301").status_code)
test("302 follow", lambda: ImpySession(verify=False).get(f"{B}/r302").status_code,
                  lambda: CffiSession(verify=False).get(f"{B}/r302").status_code)
test("301 no-follow", lambda: ImpySession(verify=False).get(f"{B}/r301",allow_redirects=False).status_code,
                       lambda: CffiSession(verify=False).get(f"{B}/r301",allow_redirects=False).status_code)

# === 8. Content-Encoding ===
print("\n--- 8. Content-Encoding ---")
def impy_gzip():
    s = ImpySession(verify=False)
    r = s.get(f"{GB}/gzip")
    s.close()
    return r.json().get("data","")[:10] if r.status_code==200 else "FAIL"
def cffi_gzip():
    s = CffiSession(verify=False)
    r = s.get(f"{GB}/gzip")
    s.close()
    return r.json().get("data","")[:10] if r.status_code==200 else "FAIL"
test("gzip decompress", impy_gzip, cffi_gzip)
test("deflate decompress", lambda: ImpySession(verify=False).get(f"{GB}/deflate").json().get("data","")[:10],
                           lambda: CffiSession(verify=False).get(f"{GB}/deflate").json().get("data","")[:10])

# === 9. 代理 ===
print("\n--- 9. 代理 ---")
test("proxy direct", lambda: ImpySession(impersonate="chrome131",verify=False).get("https://120.26.33.71/json/detail").status_code,
                      lambda: CffiSession(impersonate="chrome131",verify=False).get("https://120.26.33.71/json/detail").status_code)
test("proxy via 7897", lambda: ImpySession(impersonate="chrome131",verify=False,proxies={"https":"http://127.0.0.1:7897"}).get("https://120.26.33.71/json/detail").status_code,
                        lambda: CffiSession(impersonate="chrome131",verify=False,proxies={"https":"http://127.0.0.1:7897"}).get("https://120.26.33.71/json/detail").status_code)

# === 10. USERAGENT覆盖 ===
print("\n--- 10. USERAGENT覆盖 ---")
def impy_ua():
    recv_hdrs.clear()
    s = ImpySession(impersonate="chrome131",verify=False)
    s.get(f"{B}/ua", headers={"User-Agent":"MyAgent/1.0"})
    s.close()
    return any("MyAgent" in v for k,v in recv_hdrs if k.lower()=="user-agent")
def cffi_ua():
    recv_hdrs.clear()
    s = CffiSession(impersonate="chrome131",verify=False)
    s.get(f"{B}/ua", headers={"User-Agent":"MyAgent/1.0"})
    s.close()
    return any("MyAgent" in v for k,v in recv_hdrs if k.lower()=="user-agent")
test("UA override", impy_ua, cffi_ua)

# === 11. 低级Curl API ===
print("\n--- 11. 低级Curl API ---")
def impy_curl():
    c = ImpyCurl()
    c.impersonate("chrome131")
    buf = bytearray()
    def cb(d): buf.extend(d); return len(d)
    c.setopt(CurlOpt.URL, "https://www.baidu.com")
    c.setopt(CurlOpt.WRITEFUNCTION, cb)
    c.setopt(CurlOpt.SSL_VERIFYPEER, 0)
    c.setopt(CurlOpt.TIMEOUT, 10)
    c.perform()
    code = c.getinfo(CurlInfo.RESPONSE_CODE)
    c.close()
    return code
def cffi_curl():
    c = CffiCurl()
    c.impersonate("chrome131")
    buf = bytearray()
    def cb(d): buf.extend(d); return len(d)
    c.setopt(CffiOpt.URL, "https://www.baidu.com")
    c.setopt(CffiOpt.WRITEFUNCTION, cb)
    c.setopt(CffiOpt.SSL_VERIFYPEER, 0)
    c.setopt(CffiOpt.TIMEOUT, 10)
    c.perform()
    code = c.getinfo(CffiInfo.RESPONSE_CODE)
    c.close()
    return code
test("Curl low-level baidu", impy_curl, cffi_curl)

# === 12. Async测试 ===
print("\n--- 12. Async测试 ---")
async def _async_test():
    s = ImpySession(impersonate="chrome131", verify=False)
    r = await s.get("https://www.baidu.com")
    s.close()
    return r.status_code
try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    impy_async = loop.run_until_complete(_async_test())
    loop.close()
except Exception as e:
    impy_async = f"ERROR: {e}"

async def _async_test_cffi():
    s = CffiSession(impersonate="chrome131", verify=False)
    r = await s.get("https://www.baidu.com")
    s.close()
    return r.status_code
try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    cffi_async = loop.run_until_complete(_async_test_cffi())
    loop.close()
except Exception as e:
    cffi_async = f"ERROR: {e}"
test("async baidu", lambda: impy_async, lambda: cffi_async)

# === 13. 稳定性 ===
print("\n--- 13. 稳定性 (50次循环) ---")
def impy_stability():
    s = ImpySession(impersonate="chrome131", verify=False)
    ok = all(s.get("https://www.baidu.com").status_code==200 for _ in range(50))
    s.close()
    return ok
def cffi_stability():
    s = CffiSession(impersonate="chrome131", verify=False)
    ok = all(s.get("https://www.baidu.com").status_code==200 for _ in range(50))
    s.close()
    return ok
test("50x stability", impy_stability, cffi_stability)

# === Summary ===
print("\n" + "=" * 120)
print("Summary")
print("=" * 120)
matched = sum(1 for _,m,_,_ in R if m)
for name, match, impy_r, cffi_r in R:
    print(f"  {'MATCH' if match else 'DIFF':<6} {name:<35} impy={str(impy_r)[:30]:<30} cffi={str(cffi_r)[:30]}")
print(f"\n  {matched}/{len(R)} matched")
srv.shutdown(); gsrv.shutdown()

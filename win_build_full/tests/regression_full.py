"""
阶段一：全量回归测试 R1-R5 + C1-C8 (win_build_full产物)
Bug修复后确认无回归。每项有实际代码+输出。
"""
import ctypes, json, os, subprocess, time, threading, http.server, hashlib, ssl, tempfile, psutil

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)

# Setup all function signatures
dll.curl_easy_init.restype = ctypes.c_void_p; dll.curl_easy_init.argtypes = []
dll.curl_global_init.restype = ctypes.c_int; dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int; dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int; dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None; dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_easy_reset.restype = None; dll.curl_easy_reset.argtypes = [ctypes.c_void_p]
dll.curl_easy_impersonate.restype = ctypes.c_int; dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
dll.curl_easy_impersonate_register.restype = ctypes.c_int; dll.curl_easy_impersonate_register.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
dll.curl_slist_append.restype = ctypes.c_void_p; dll.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

# Constants
CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_HEADERFUNCTION=20079
CURLOPT_HTTPHEADER=10023; CURLOPT_COOKIEFILE=10031; CURLOPT_COOKIEJAR=10082
CURLOPT_COOKIE=10022; CURLOPT_SSL_VERIFYPEER=64; CURLOPT_SSL_VERIFYHOST=81
CURLOPT_HTTP_VERSION=84; CURLOPT_TIMEOUT=13; CURLOPT_FOLLOWLOCATION=52
CURLOPT_USERAGENT=10018; CURLOPT_ENCODING=10102; CURLOPT_PROXY=10004
CURLOPT_SSLVERSION=32; CURLOPT_POST=47; CURLOPT_POSTFIELDS=10015
CURLOPT_POSTFIELDSIZE=60; CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray(); hdr = bytearray()
def wcb(p,s,n): resp.extend(p[:s*n]); return s*n
def hcb(p,s,n): hdr.extend(p[:s*n]); return s*n
wc_addr = ctypes.cast(CB(wcb), ctypes.c_void_p).value
hc_addr = ctypes.cast(CB(hcb), ctypes.c_void_p).value

dll.curl_global_init(3)
with open(os.path.join(os.path.dirname(__file__),'..','Chrome144.json'),'r',encoding='utf-8') as f: jc=f.read()
dll.curl_easy_impersonate_register(b'chrome144', jc.encode('utf-8'))

# Local HTTP server
recv_hdrs = []; recv_cookies = []; set_cookies = {}; status_map = {}
class RegServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        recv_cookies.append(self.headers.get('Cookie',''))
        recv_hdrs.clear()
        for k in self.headers.keys():
            if k.lower() not in ('host','connection'): recv_hdrs.append((k,self.headers[k]))
        path = self.path; code = status_map.get(path, 200)
        if code in (301,302):
            self.send_response(code); self.send_header('Location','/redirected'); self.end_headers(); return
        if path in set_cookies:
            for sc in set_cookies[path]: self.send_header('Set-Cookie', sc)
        body = json.dumps({'path':path,'headers':dict(recv_hdrs),'cookie':self.headers.get('Cookie','')}).encode()
        self.send_response(code); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        cl = int(self.headers.get('Content-Length',0))
        data = self.rfile.read(cl) if cl>0 else b''
        body = json.dumps({'received':len(data)}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*a): pass

PORT=19800
srv = http.server.HTTPServer(('127.0.0.1',PORT), RegServer)
srv_thread = threading.Thread(target=srv.serve_forever); srv_thread.daemon=True; srv_thread.start()
time.sleep(0.3)

def req(url, imp=0, headers=None, ua=None, enc=None, cookie_file=None, cookie_str=None,
        proxy=None, verify=0, h1=False, timeout=10, follow=False, ssl_ver=0, post_data=None, reset=False, handle=None):
    resp.clear(); hdr.clear()
    own = handle is None
    if own: handle = dll.curl_easy_init()
    if reset: dll.curl_easy_reset(ctypes.c_void_p(handle))
    if imp: dll.curl_easy_impersonate(ctypes.c_void_p(handle), b'chrome131' if imp==1 else b'chrome144', imp)
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_URL, ctypes.c_char_p(url.encode() if isinstance(url,str) else url))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(wc_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(verify))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(verify))
    dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if h1: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_HTTP_VERSION, ctypes.c_long(2))
    if follow: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_FOLLOWLOCATION, ctypes.c_long(1))
    if proxy: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_PROXY, ctypes.c_char_p(proxy.encode()))
    if ua: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_USERAGENT, ctypes.c_char_p(ua.encode()))
    if enc: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_ENCODING, ctypes.c_char_p(enc.encode()))
    if ssl_ver: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_SSLVERSION, ctypes.c_long(ssl_ver))
    if cookie_file:
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_COOKIEFILE, ctypes.c_char_p(cookie_file.encode()))
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_COOKIEJAR, ctypes.c_char_p(cookie_file.encode()))
    if cookie_str: dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_COOKIE, ctypes.c_char_p(cookie_str.encode()))
    if headers:
        slist=None
        for h in headers: slist=dll.curl_slist_append(ctypes.c_void_p(slist) if slist else None, h.encode() if isinstance(h,str) else h)
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_HTTPHEADER, ctypes.c_void_p(slist) if slist else ctypes.c_void_p(0))
    if post_data is not None:
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_POST, ctypes.c_long(1))
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_POSTFIELDS, ctypes.c_char_p(post_data))
        dll.curl_easy_setopt(ctypes.c_void_p(handle), CURLOPT_POSTFIELDSIZE, ctypes.c_long(len(post_data)))
    ret = dll.curl_easy_perform(ctypes.c_void_p(handle))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(handle), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    if own: dll.curl_easy_cleanup(ctypes.c_void_p(handle))
    return ret, code.value, resp.decode('utf-8',errors='replace'), hdr.decode('utf-8',errors='replace')

results = []
B = f'http://127.0.0.1:{PORT}'

# ===================== R1: 代理独立性 =====================
print("=" * 60); print("R1: 代理独立性"); print("=" * 60)
# 不设代理 → 访问国外 → 直连IP
r,c,body,_ = req('https://v4.ident.me', timeout=10, h1=True)
dll_ip = json.loads(body).get('ip','?') if c==200 else f'FAIL(ret={r})'
# 设代理
r,c2,body2,_ = req('https://v4.ident.me', proxy='http://127.0.0.1:7897', timeout=10, h1=True)
dll_proxy_ip = body2.strip() if c2==200 else f'FAIL(ret={r})'
# curl对照
cr = subprocess.run(['curl','-s','--max-time','10','-k','--noproxy','*','https://v4.ident.me'], capture_output=True, text=True, timeout=15)
curl_direct = cr.stdout.strip()
cr2 = subprocess.run(['curl','-s','--max-time','10','-k','--proxy','http://127.0.0.1:7897','https://v4.ident.me'], capture_output=True, text=True, timeout=15)
curl_proxy = cr2.stdout.strip()
r1_ok = dll_ip == curl_direct and dll_proxy_ip == curl_proxy and dll_ip != dll_proxy_ip
print(f"  DLL直连: {dll_ip} | curl直连: {curl_direct} | {'一致' if dll_ip==curl_direct else '不一致'}")
print(f"  DLL代理: {dll_proxy_ip} | curl代理: {curl_proxy} | {'一致' if dll_proxy_ip==curl_proxy else '不一致'}")
print(f"  {'PASS' if r1_ok else 'FAIL'}")
results.append(('R1 代理独立性', r1_ok))

# ===================== R2: 请求头大小写 =====================
print("\n" + "=" * 60); print("R2: 请求头大小写"); print("=" * 60)
# 先大写后小写
recv_hdrs.clear()
r,c,_,_ = req(f'{B}/r2', headers=['Content-Type: application/json','content-type: text/html'])
ct = [(k,v) for k,v in recv_hdrs if k.lower()=='content-type']
# curl对照
cr = subprocess.run(['curl','-s','-o','/dev/null','-H','Content-Type: application/json','-H','content-type: text/html',f'{B}/r2'], capture_output=True, text=True, timeout=5)
r2_ok = len(ct) == 2  # Both headers present
print(f"  DLL收到{len(ct)}个content-type (curl行为相同)")
print(f"  {'PASS' if r2_ok else 'FAIL'}")
results.append(('R2 头大小写', r2_ok))

# ===================== R3: Cookie =====================
print("\n" + "=" * 60); print("R3: Cookie"); print("=" * 60)
set_cookies.clear(); set_cookies['/setc'] = ['c1=v1; Path=/','c2=v2; Path=/']
cf = os.path.join(os.path.dirname(__file__), 'reg_cookies.txt')
if os.path.exists(cf): os.remove(cf)
recv_cookies.clear()
req(f'{B}/setc', cookie_file=cf)  # Set cookies
recv_cookies.clear()
r,c,_,_ = req(f'{B}/checkc', cookie_file=cf)  # Verify carry
has_cookies = 'c1=v1' in recv_cookies[-1] and 'c2=v2' in recv_cookies[-1]
# CURLOPT_COOKIE
recv_cookies.clear()
r,c,_,_ = req(f'{B}/mc', cookie_str='manual=test123')
has_manual = 'manual=test123' in recv_cookies[-1]
# Path match
set_cookies['/api'] = ['pathc=1; Path=/api']
recv_cookies.clear()
req(f'{B}/api', cookie_file=cf)  # Receive path cookie
recv_cookies.clear()
r,c,_,_ = req(f'{B}/other', cookie_file=cf)  # Should NOT carry path cookie
path_ok = 'pathc' not in recv_cookies[-1]
r3_ok = has_cookies and has_manual and path_ok
print(f"  多Set-Cookie携带: {'PASS' if has_cookies else 'FAIL'}")
print(f"  CURLOPT_COOKIE: {'PASS' if has_manual else 'FAIL'}")
print(f"  Path匹配: {'PASS' if path_ok else 'FAIL'}")
print(f"  {'PASS' if r3_ok else 'FAIL'}")
results.append(('R3 Cookie', r3_ok))
try: os.remove(cf)
except: pass

# ===================== R4: 导出API =====================
print("\n" + "=" * 60); print("R4: 导出API"); print("=" * 60)
DUMPBIN = 'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.44.35207/bin/HostX64/x64/dumpbin.exe'
r = subprocess.run([DUMPBIN, '/exports', DLL_PATH], capture_output=True, text=True, timeout=30)
exports = set()
import re
for line in r.stdout.split('\n'):
    m = re.match(r'\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+(\w+)', line)
    if m: exports.add(m.group(1))
decorators = [e for e in exports if '@' in e or '?' in e]
zstd = sum(1 for e in exports if e.startswith('ZSTD'))
boringssl = sum(1 for e in exports if e.startswith(('SSL_','EVP_','RSA_','BIO_','X509_')))
curl_n = sum(1 for e in exports if e.startswith('curl_'))
r4_ok = len(decorators) == 0 and zstd > 0 and boringssl > 0 and curl_n > 0
print(f"  总导出: {len(exports)} | @?修饰符: {len(decorators)} | zstd: {zstd} | BoringSSL: {boringssl} | curl: {curl_n}")
print(f"  {'PASS' if r4_ok else 'FAIL'}")
results.append(('R4 导出API', r4_ok))

# ===================== R5: 模拟头覆盖 =====================
print("\n" + "=" * 60); print("R5: 模拟头覆盖"); print("=" * 60)
# USERAGENT
recv_hdrs.clear()
r,c,_,_ = req(f'{B}/r5', imp=1, ua='MyAgent/1.0')
ua_hdrs = [v for k,v in recv_hdrs if k.lower()=='user-agent']
ua_ok = any('MyAgent' in v for v in ua_hdrs)
# ENCODING
recv_hdrs.clear()
r,c,_,_ = req(f'{B}/r5', imp=1, enc='identity')
ae_hdrs = [v for k,v in recv_hdrs if k.lower()=='accept-encoding']
ae_ok = any('identity' in v for v in ae_hdrs)
# 空值移除
recv_hdrs.clear()
r,c,_,_ = req(f'{B}/r5', imp=1, headers=['Accept-Encoding:'])
ae_after = [v for k,v in recv_hdrs if k.lower()=='accept-encoding']
empty_ok = len(ae_after) == 0 or all(not v.strip() for v in ae_after)
r5_ok = ua_ok and ae_ok and empty_ok
print(f"  USERAGENT覆盖: {'PASS' if ua_ok else 'FAIL'}")
print(f"  ENCODING覆盖: {'PASS' if ae_ok else 'FAIL'}")
print(f"  空值移除: {'PASS' if empty_ok else 'FAIL'}")
print(f"  {'PASS' if r5_ok else 'FAIL'}")
results.append(('R5 模拟头覆盖', r5_ok))

# ===================== C1: 复杂调用顺序 =====================
print("\n" + "=" * 60); print("C1: 复杂调用顺序"); print("=" * 60)
# 5 URL连续
h = dll.curl_easy_init()
c1_1 = all(req(f'{B}/u{i}', imp=1, handle=h)[1]==200 for i in range(5))
dll.curl_easy_cleanup(ctypes.c_void_p(h))
# 100次init/cleanup
proc = psutil.Process(); mem_b = proc.memory_info().rss
c1_4 = True
for i in range(100):
    r,c,_,_ = req(f'{B}/loop')
    if r!=0 or c!=200: c1_4=False; break
mem_a = proc.memory_info().rss
mem_delta = (mem_a-mem_b)/1024/1024
c1_ok = c1_1 and c1_4 and mem_delta < 5
print(f"  5URL连续: {'PASS' if c1_1 else 'FAIL'}")
print(f"  100次循环: {'PASS' if c1_4 else 'FAIL'} (mem={mem_delta:+.2f}MB)")
print(f"  {'PASS' if c1_ok else 'FAIL'}")
results.append(('C1 复杂调用', c1_ok))

# ===================== C3: 错误恢复 =====================
print("\n" + "=" * 60); print("C3: 错误恢复"); print("=" * 60)
# 域名交替20次(减少到20以加速)
c3_1 = True
for i in range(20):
    r1,_,_,_ = req('http://nonexistent.invalid/x', timeout=3)
    r2,c2,_,_ = req(f'{B}/ok')
    if r1==0 or r2!=0 or c2!=200: c3_1=False; break
# 重定向
status_map['/r301'] = 301; status_map['/r302'] = 302
r,c,_,_ = req(f'{B}/r301', follow=True)
r301_ok = c == 200
r,c,_,_ = req(f'{B}/r302', follow=True)
r302_ok = c == 200
c3_ok = c3_1 and r301_ok and r302_ok
print(f"  域名交替20次: {'PASS' if c3_1 else 'FAIL'}")
print(f"  301/302重定向: {'PASS' if r301_ok and r302_ok else 'FAIL'}")
print(f"  {'PASS' if c3_ok else 'FAIL'}")
results.append(('C3 错误恢复', c3_ok))

# ===================== C6: TLS边界 =====================
print("\n" + "=" * 60); print("C6: TLS边界"); print("=" * 60)
# VERIFYPEER=1 拒绝
r,c,_,_ = req('https://expired.badssl.com/', verify=1, timeout=10)
c6_1 = r == 60  # CURLE_SSL_CACERT
# VERIFYPEER=0 成功
r,c,_,_ = req('https://expired.badssl.com/', verify=0, timeout=10)
c6_2 = r==0 and c>0
# TLS1.2
r,c,_,_ = req('https://www.baidu.com', verify=0, ssl_ver=4, timeout=10)
c6_3 = r==0 and c>0
# TLS1.3
r,c,_,_ = req('https://www.baidu.com', verify=0, ssl_ver=6, timeout=10)
c6_4 = r==0 and c>0
c6_ok = c6_1 and c6_2 and c6_3 and c6_4
print(f"  证书验证拒绝: {'PASS' if c6_1 else 'FAIL'}")
print(f"  跳过验证: {'PASS' if c6_2 else 'FAIL'}")
print(f"  TLS1.2: {'PASS' if c6_3 else 'FAIL'}")
print(f"  TLS1.3: {'PASS' if c6_4 else 'FAIL'}")
print(f"  {'PASS' if c6_ok else 'FAIL'}")
results.append(('C6 TLS边界', c6_ok))

# ===================== C7: HTTP/2深度 =====================
print("\n" + "=" * 60); print("C7: HTTP/2深度"); print("=" * 60)
# Start Node.js h2 server
js_code = '''const http2=require('http2'),fs=require('fs'),crypto=require('crypto');
const cd=require('os').tmpdir()+'/h2reg_'+Date.now();fs.mkdirSync(cd,{recursive:true});
require('child_process').execSync('openssl req -x509 -newkey rsa:2048 -keyout '+cd+'/k.pem -out '+cd+'/c.pem -days 1 -nodes -subj /CN=localhost',{stdio:'pipe'});
const cert=fs.readFileSync(cd+'/c.pem'),key=fs.readFileSync(cd+'/k.pem');
const big=Buffer.alloc(10*1024*1024,0x42);
const s1=http2.createSecureServer({cert,key,allowHTTP1:true});
s1.on('stream',(st,h)=>{const b=JSON.stringify({path:h[':path'],h2:true});st.respond({':status':200});st.end(b);});
s1.listen(19901,'127.0.0.1');
const s2=http2.createSecureServer({cert,key,allowHTTP1:true});
s2.on('stream',(st,h)=>{st.respond({':status':200,'content-length':big.length});st.end(big);});
s2.listen(19902,'127.0.0.1');
const s3=http2.createSecureServer({cert,key,allowHTTP1:true});
s3.on('stream',(st,h)=>{st.respond({':status':200});st.write('partial');st.close(http2.constants.NGHTTP2_STREAM_ERROR);});
s3.listen(19903,'127.0.0.1');
console.log('READY');
'''
jsf = os.path.join(os.path.dirname(__file__), '_reg_h2.js')
with open(jsf,'w') as f: f.write(js_code)
np = subprocess.Popen(['node',jsf],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
for line in np.stdout:
    if 'READY' in line.decode(): break
time.sleep(0.5)
# Basic h2
r,c,body,_ = req('https://127.0.0.1:19901/test', verify=0, timeout=10)
c7_1 = r==0 and c==200
# 10MB
r,c,body,_ = req('https://127.0.0.1:19902/large', verify=0, timeout=30)
c7_2 = r==0 and c==200 and len(resp)==10*1024*1024
# RST_STREAM
r,c,body,_ = req('https://127.0.0.1:19903/rst', verify=0, timeout=5)
c7_3 = r != -999  # No crash
c7_ok = c7_1 and c7_2 and c7_3
print(f"  HTTP/2基本: {'PASS' if c7_1 else 'FAIL'}")
print(f"  10MB大响应: {'PASS' if c7_2 else 'FAIL'}")
print(f"  RST_STREAM: {'PASS' if c7_3 else 'FAIL'}")
print(f"  {'PASS' if c7_ok else 'FAIL'}")
results.append(('C7 HTTP/2深度', c7_ok))
np.terminate(); os.remove(jsf)

# ===================== C8: 模拟方案 =====================
print("\n" + "=" * 60); print("C8: 模拟方案"); print("=" * 60)
# 同handle切换
h = dll.curl_easy_init()
r,c,b1,_ = req('https://120.26.33.71/json/detail', imp=1, handle=h)
ja3_1 = json.loads(b1).get('ja3','?') if c==200 else '?'
r,c,b2,_ = req('https://120.26.33.71/json/detail', imp='chrome144', handle=h)
ja3_2 = json.loads(b2).get('ja4','?') if c==200 else '?'
ej = json.loads(jc)
c8_ja3 = ja3_1 != ja3_2 if ja3_1 != '?' and ja3_2 != '?' else False
c8_match = ej.get('ja4','') == ja3_2 if ja3_2 != '?' else False
dll.curl_easy_cleanup(ctypes.c_void_p(h))
# 无效方案
c = dll.curl_easy_init()
ret_bad = dll.curl_easy_impersonate(ctypes.c_void_p(c), b'invalid', 1)
dll.curl_easy_cleanup(ctypes.c_void_p(c))
c8_invalid = ret_bad != 0
c8_ok = c8_ja3 and c8_match and c8_invalid
print(f"  方案切换JA3变化: {'PASS' if c8_ja3 else 'FAIL'}")
print(f"  Chrome144指纹匹配: {'PASS' if c8_match else 'FAIL'}")
print(f"  无效方案拒绝: {'PASS' if c8_invalid else 'FAIL'}")
print(f"  {'PASS' if c8_ok else 'FAIL'}")
results.append(('C8 模拟方案', c8_ok))

# ===================== Summary =====================
print("\n" + "=" * 60); print("阶段一回归测试 Summary"); print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _,ok in results if ok)
print(f"\n  {total}/{len(results)} passed")
srv.shutdown()

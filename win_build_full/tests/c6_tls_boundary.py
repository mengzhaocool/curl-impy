"""
C6: TLS边界测试
用Python ssl模块创建自签名证书HTTPS服务器
1. 自签名证书(VERIFYPEER=1应拒绝, =0应成功)
2. 域名不匹配(VERIFYHOST=1应拒绝)
3. TLS1.2-only: 服务器只启用TLS1.2
4. TLS1.3-only: 服务器只启用TLS1.3
"""
import ctypes, os, ssl, threading, http.server, json, time, tempfile

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
CURLOPT_SSL_VERIFYHOST=81; CURLOPT_SSLVERSION=32; CURLOPT_TIMEOUT=13
CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)
resp = bytearray()
def cb(p,s,n): resp.extend(p[:s*n]); return s*n
cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value
dll.curl_global_init(3)

# Generate self-signed certificate
import subprocess
cert_dir = tempfile.mkdtemp()
cert_file = os.path.join(cert_dir, 'cert.pem')
key_file = os.path.join(cert_dir, 'key.pem')
subprocess.run([
    'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-keyout', key_file,
    '-out', cert_file, '-days', '1', '-nodes', '-subj',
    '/CN=localhost'
], check=True, capture_output=True, timeout=10)

class TLSServer(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'tls': True, 'path': self.path}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a): pass

results = []

def dll_req(url, verify_peer=0, verify_host=0, ssl_version=0, timeout=5):
    resp.clear()
    c = dll.curl_easy_init()
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(verify_peer))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(verify_host))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if ssl_version:
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSLVERSION, ctypes.c_long(ssl_version))
    ret = dll.curl_easy_perform(ctypes.c_void_p(c))
    code = ctypes.c_long(0)
    dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
    dll.curl_easy_cleanup(ctypes.c_void_p(c))
    return ret, code.value

# === C6.1: Self-signed cert ===
print("=" * 60)
print("C6.1: Self-signed certificate")
print("=" * 60)

ctx_default = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx_default.load_cert_chain(cert_file, key_file)

PORT = 19401
srv = http.server.HTTPServer(('127.0.0.1', PORT), TLSServer)
srv.socket = ctx_default.wrap_socket(srv.socket, server_side=True)
t = threading.Thread(target=srv.serve_forever); t.daemon = True; t.start()
time.sleep(0.5)

url = f'https://127.0.0.1:{PORT}/test'

# Verify peer ON (should fail - self-signed)
ret, code = dll_req(url, verify_peer=1, verify_host=2)
print(f"  VERIFYPEER=1: ret={ret} HTTP={code} (预期: 失败ret!=0)")
ok1 = ret != 0
results.append(('C6.1a 自签名拒绝', ok1))
print(f"  {'PASS: 自签名证书被拒绝' if ok1 else 'FAIL: 应该拒绝'}")

# Verify peer OFF (should succeed)
ret, code = dll_req(url, verify_peer=0, verify_host=0)
print(f"  VERIFYPEER=0: ret={ret} HTTP={code} (预期: 成功HTTP=200)")
ok2 = ret == 0 and code == 200
results.append(('C6.1b 跳过验证', ok2))
print(f"  {'PASS: 跳过验证后成功' if ok2 else 'FAIL'}")

srv.shutdown()

# === C6.2: Domain mismatch ===
print("\n" + "=" * 60)
print("C6.2: Domain mismatch (cert CN=localhost, connect via 127.0.0.1)")
print("=" * 60)

srv2 = http.server.HTTPServer(('127.0.0.1', PORT+1), TLSServer)
srv2.socket = ctx_default.wrap_socket(srv2.socket, server_side=True)
t2 = threading.Thread(target=srv2.serve_forever); t2.daemon = True; t2.start()
time.sleep(0.5)

url2 = f'https://127.0.0.1:{PORT+1}/test'

# Verify host ON (should fail - CN=localhost but connecting to 127.0.0.1)
ret, code = dll_req(url2, verify_peer=1, verify_host=2)
print(f"  VERIFYHOST=2: ret={ret} HTTP={code} (预期: 失败)")
# Note: if cert has SAN for 127.0.0.1, this might pass. Let's check.
ok3 = ret != 0 or code == 0  # Either error or no response
results.append(('C6.2 域名不匹配', ok3))
print(f"  {'PASS: 域名不匹配被拒绝' if ok3 else 'INFO: 证书可能包含IP SAN'}")

# Verify host OFF (should succeed)
ret, code = dll_req(url2, verify_peer=0, verify_host=0)
print(f"  VERIFYHOST=0: ret={ret} HTTP={code}")
ok4 = ret == 0 and code == 200
results.append(('C6.2b 跳过域名检查', ok4))

srv2.shutdown()

# === C6.3: TLS 1.2 only ===
print("\n" + "=" * 60)
print("C6.3: TLS 1.2 only server")
print("=" * 60)

ctx_tls12 = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx_tls12.load_cert_chain(cert_file, key_file)
ctx_tls12.minimum_version = ssl.TLSVersion.TLSv1_2
ctx_tls12.maximum_version = ssl.TLSVersion.TLSv1_2

srv3 = http.server.HTTPServer(('127.0.0.1', PORT+2), TLSServer)
srv3.socket = ctx_tls12.wrap_socket(srv3.socket, server_side=True)
t3 = threading.Thread(target=srv3.serve_forever); t3.daemon = True; t3.start()
time.sleep(0.5)

url3 = f'https://127.0.0.1:{PORT+2}/test'
ret, code = dll_req(url3, verify_peer=0, verify_host=0)
print(f"  TLS1.2-only: ret={ret} HTTP={code}")
ok5 = ret == 0 and code == 200
results.append(('C6.3 TLS1.2-only', ok5))
print(f"  {'PASS: TLS1.2协商成功' if ok5 else 'FAIL'}")

srv3.shutdown()

# === C6.4: TLS 1.3 only ===
print("\n" + "=" * 60)
print("C6.4: TLS 1.3 only server")
print("=" * 60)

ctx_tls13 = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx_tls13.load_cert_chain(cert_file, key_file)
ctx_tls13.minimum_version = ssl.TLSVersion.TLSv1_3
ctx_tls13.maximum_version = ssl.TLSVersion.TLSv1_3

srv4 = http.server.HTTPServer(('127.0.0.1', PORT+3), TLSServer)
srv4.socket = ctx_tls13.wrap_socket(srv4.socket, server_side=True)
t4 = threading.Thread(target=srv4.serve_forever); t4.daemon = True; t4.start()
time.sleep(0.5)

url4 = f'https://127.0.0.1:{PORT+3}/test'
ret, code = dll_req(url4, verify_peer=0, verify_host=0)
print(f"  TLS1.3-only: ret={ret} HTTP={code}")
ok6 = ret == 0 and code == 200
results.append(('C6.4 TLS1.3-only', ok6))
print(f"  {'PASS: TLS1.3协商成功' if ok6 else 'FAIL (可能不支持TLS1.3-only)'}")

srv4.shutdown()

# === Summary ===
print("\n" + "=" * 60)
print("C6 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

# Cleanup
import shutil
shutil.rmtree(cert_dir, ignore_errors=True)

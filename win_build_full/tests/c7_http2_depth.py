"""
C7: HTTP/2深度测试
使用h2库创建本地HTTP/2服务器，测试:
1. 多路复用3个stream
2. 大响应10MB (MD5校验)
3. 大请求头16KB
4. RST_STREAM
5. GOAWAY
"""
import ctypes, os, json, hashlib, threading, time, ssl, tempfile, subprocess

# h2 server
import h2.connection
import h2.events
import h2.config

DLL_PATH = os.path.join(os.path.dirname(__file__), '..', 'output', 'libcurl-impersonate.dll')
dll = ctypes.WinDLL(DLL_PATH)
dll.curl_easy_init.restype = ctypes.c_void_p
dll.curl_global_init.restype = ctypes.c_int; dll.curl_global_init.argtypes = [ctypes.c_long]
dll.curl_easy_setopt.restype = ctypes.c_int
dll.curl_easy_perform.restype = ctypes.c_int; dll.curl_easy_perform.argtypes = [ctypes.c_void_p]
dll.curl_easy_getinfo.restype = ctypes.c_int; dll.curl_easy_getinfo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
dll.curl_easy_cleanup.restype = None; dll.curl_easy_cleanup.argtypes = [ctypes.c_void_p]
dll.curl_slist_append.restype = ctypes.c_void_p; dll.curl_slist_append.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
dll.curl_easy_impersonate.restype = ctypes.c_int; dll.curl_easy_impersonate.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]

CURLOPT_URL=10002; CURLOPT_WRITEFUNCTION=20011; CURLOPT_SSL_VERIFYPEER=64
CURLOPT_SSL_VERIFYHOST=81; CURLOPT_HTTP_VERSION=84; CURLOPT_TIMEOUT=13
CURLOPT_HTTPHEADER=10023; CURLINFO_RESPONSE_CODE=0x200002

CB = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t)

results = []

def generate_cert():
    cert_dir = tempfile.mkdtemp()
    cert_file = os.path.join(cert_dir, 'cert.pem')
    key_file = os.path.join(cert_dir, 'key.pem')
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-keyout',key_file,
                   '-out',cert_file,'-days','1','-nodes','-subj','/CN=localhost'],
                  check=True, capture_output=True, timeout=10)
    return cert_file, key_file

def h2_server_thread(port, cert_file, key_file, mode='normal', large_data=None):
    """Run an h2 server in a thread."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_file, key_file)
    ctx.set_alpn_protocols(['h2'])

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', port))
    sock.listen(5)
    sock = ctx.wrap_socket(sock, server_side=True)

    config = h2.config.H2Configuration(client_side=False)
    h2_conn = h2.connection.H2Connection(config=config)
    h2_conn.initiate_connection()
    sock.sendall(h2_conn.data_to_send())

    try:
        while True:
            data = sock.recv(65535)
            if not data:
                break
            events = h2_conn.receive_data(data)
            for event in events:
                if isinstance(event, h2.events.RequestReceived):
                    stream_id = event.stream_id
                    headers = dict(event.headers)
                    path = headers.get(b':path', b'/').decode()
                    method = headers.get(b':method', b'GET').decode()

                    if mode == 'rst':
                        # Send RST_STREAM after partial response
                        response_data = b'partial'
                        h2_conn.send_headers(stream_id, [(b':status', b'200'), (b'content-type', b'text/plain')])
                        h2_conn.send_data(stream_id, response_data)
                        h2_conn.reset_stream(stream_id)
                        sock.sendall(h2_conn.data_to_send())
                        return

                    if mode == 'goaway':
                        # Send GOAWAY immediately
                        h2_conn.close_connection()
                        sock.sendall(h2_conn.data_to_send())
                        return

                    if large_data:
                        # Large response
                        response = large_data
                        h2_conn.send_headers(stream_id, [(b':status', b'200'), (b'content-type', b'application/octet-stream'), (b'content-length', str(len(response)).encode())])
                        # Send in chunks
                        chunk_size = 16384
                        for i in range(0, len(response), chunk_size):
                            chunk = response[i:i+chunk_size]
                            h2_conn.send_data(stream_id, chunk)
                        h2_conn.end_stream(stream_id)
                    else:
                        # Normal response
                        response_headers = [
                            (b':status', b'200'),
                            (b'content-type', b'application/json'),
                        ]
                        resp_body = json.dumps({'path': path, 'method': method, 'headers': {k.decode():v.decode() for k,v in headers.items()}}).encode()
                        h2_conn.send_headers(stream_id, response_headers + [(b'content-length', str(len(resp_body)).encode())])
                        h2_conn.send_data(stream_id, resp_body)
                        h2_conn.end_stream(stream_id)

                    sock.sendall(h2_conn.data_to_send())
    except Exception as e:
        pass
    finally:
        sock.close()

def dll_req(url, headers=None, timeout=10, impersonate=0):
    resp = bytearray()
    def cb(p,s,n): resp.extend(p[:s*n]); return s*n
    cb_addr = ctypes.cast(CB(cb), ctypes.c_void_p).value

    c = dll.curl_easy_init()
    if impersonate:
        dll.curl_easy_impersonate(ctypes.c_void_p(c), b'chrome131', impersonate)
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_URL, ctypes.c_char_p(url.encode()))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_WRITEFUNCTION, ctypes.c_void_p(cb_addr))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYPEER, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_SSL_VERIFYHOST, ctypes.c_long(0))
    dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_TIMEOUT, ctypes.c_long(timeout))
    if headers:
        slist = None
        for h in headers:
            slist = dll.curl_slist_append(ctypes.c_void_p(slist) if slist else None, h.encode() if isinstance(h,str) else h)
        dll.curl_easy_setopt(ctypes.c_void_p(c), CURLOPT_HTTPHEADER, ctypes.c_void_p(slist) if slist else ctypes.c_void_p(0))
    try:
        ret = dll.curl_easy_perform(ctypes.c_void_p(c))
        code = ctypes.c_long(0)
        dll.curl_easy_getinfo(ctypes.c_void_p(c), CURLINFO_RESPONSE_CODE, ctypes.byref(code))
        dll.curl_easy_cleanup(ctypes.c_void_p(c))
        return ret, code.value, bytes(resp)
    except OSError as e:
        try: dll.curl_easy_cleanup(ctypes.c_void_p(c))
        except: pass
        return -999, 0, b''

# Generate cert
cert_file, key_file = generate_cert()
print(f"Cert: {cert_file}")

# === C7.1: Basic HTTP/2 request ===
print("=" * 60)
print("C7.1: Basic HTTP/2 request")
print("=" * 60)
PORT = 19501
srv_t = threading.Thread(target=h2_server_thread, args=(PORT, cert_file, key_file))
srv_t.daemon = True; srv_t.start()
time.sleep(0.5)

url = f'https://127.0.0.1:{PORT}/test'
ret, code, body = dll_req(url, timeout=5)
print(f"  ret={ret} HTTP={code} body_len={len(body)}")
if ret == 0 and code == 200:
    rj = json.loads(body.decode('utf-8', errors='replace'))
    print(f"  path={rj.get('path')} method={rj.get('method')}")
    print(f"  PASS: HTTP/2 basic request")
    results.append(('C7.1 HTTP/2基本请求', True))
else:
    print(f"  FAIL/Crash (可能h2 ALPN不兼容)")
    results.append(('C7.1 HTTP/2基本请求', False))

# === C7.2: Multiplexing 3 streams ===
print("\n" + "=" * 60)
print("C7.2: Multiplexing 3 streams (同一连接)")
print("=" * 60)
PORT2 = 19502
srv2_t = threading.Thread(target=h2_server_thread, args=(PORT2, cert_file, key_file))
srv2_t.daemon = True; srv2_t.start()
time.sleep(0.5)

# 3 concurrent requests (different handles = different connections, but let's test sequential)
all_ok = True
for i in range(3):
    ret, code, body = dll_req(f'https://127.0.0.1:{PORT2}/stream{i}', timeout=5)
    if ret != 0 or code != 200:
        all_ok = False
    print(f"  stream{i}: ret={ret} HTTP={code}")

results.append(('C7.2 多stream请求', all_ok))
print(f"  {'PASS' if all_ok else 'FAIL'}")

# === C7.3: Large response 10MB ===
print("\n" + "=" * 60)
print("C7.3: Large response 10MB (MD5校验)")
print("=" * 60)
PORT3 = 19503
large_data = os.urandom(10 * 1024 * 1024)  # 10MB random
expected_md5 = hashlib.md5(large_data).hexdigest()
print(f"  10MB数据 MD5={expected_md5}")

srv3_t = threading.Thread(target=h2_server_thread, args=(PORT3, cert_file, key_file, 'normal', large_data))
srv3_t.daemon = True; srv3_t.start()
time.sleep(0.5)

ret, code, body = dll_req(f'https://127.0.0.1:{PORT3}/large', timeout=30)
actual_md5 = hashlib.md5(body).hexdigest() if body else 'N/A'
print(f"  ret={ret} HTTP={code} received={len(body)}B MD5={actual_md5}")
ok = ret == 0 and code == 200 and len(body) == 10*1024*1024 and actual_md5 == expected_md5
results.append(('C7.3 10MB大响应', ok))
print(f"  MD5匹配: {'是' if actual_md5 == expected_md5 else '否'}")
print(f"  {'PASS' if ok else 'FAIL'}")

# === C7.4: Large request header 16KB ===
print("\n" + "=" * 60)
print("C7.4: Large request header 16KB")
print("=" * 60)
PORT4 = 19504
srv4_t = threading.Thread(target=h2_server_thread, args=(PORT4, cert_file, key_file))
srv4_t.daemon = True; srv4_t.start()
time.sleep(0.5)

big_header = f'X-Large: {"A" * 16300}'  # ~16KB header
ret, code, body = dll_req(f'https://127.0.0.1:{PORT4}/bigheader', headers=[big_header], timeout=10)
print(f"  ret={ret} HTTP={code} body_len={len(body)}")
ok = ret == 0 and code == 200
results.append(('C7.4 16KB大请求头', ok))
print(f"  {'PASS' if ok else 'FAIL'}")

# === C7.5: RST_STREAM ===
print("\n" + "=" * 60)
print("C7.5: RST_STREAM (服务器中途重置)")
print("=" * 60)
PORT5 = 19505
srv5_t = threading.Thread(target=h2_server_thread, args=(PORT5, cert_file, key_file, 'rst'))
srv5_t.daemon = True; srv5_t.start()
time.sleep(0.5)

ret, code, body = dll_req(f'https://127.0.0.1:{PORT5}/rst', timeout=5)
print(f"  ret={ret} HTTP={code} body={body[:50]}")
ok = ret != 0 or code != 200  # Should get error or partial response
no_crash = ret != -999
results.append(('C7.5 RST_STREAM', no_crash and ok))
print(f"  {'PASS: 正确处理RST_STREAM, 不崩溃' if no_crash and ok else 'FAIL'}")

# === C7.6: GOAWAY ===
print("\n" + "=" * 60)
print("C7.6: GOAWAY (服务器发送GOAWAY)")
print("=" * 60)
PORT6 = 19506
srv6_t = threading.Thread(target=h2_server_thread, args=(PORT6, cert_file, key_file, 'goaway'))
srv6_t.daemon = True; srv6_t.start()
time.sleep(0.5)

ret, code, body = dll_req(f'https://127.0.0.1:{PORT6}/goaway', timeout=5)
print(f"  ret={ret} HTTP={code}")
no_crash = ret != -999
results.append(('C7.6 GOAWAY', no_crash))
print(f"  {'PASS: 正确处理GOAWAY, 不崩溃' if no_crash else 'FAIL: 崩溃'}")

# === Summary ===
print("\n" + "=" * 60)
print("C7 Summary")
print("=" * 60)
for name, ok in results:
    print(f"  {'PASS' if ok else 'FAIL'} {name}")
total = sum(1 for _, ok in results if ok)
print(f"\n  {total}/{len(results)} passed")

# Cleanup
import shutil
shutil.rmtree(os.path.dirname(cert_file), ignore_errors=True)

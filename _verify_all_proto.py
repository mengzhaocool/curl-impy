"""Verify all protocols are enabled in the rebuilt DLL"""
import pefile, os, json

dll_path = r'd:\curl-impersonate-8.20.0\output\libcurl-impersonate.dll'
pe = pefile.PE(dll_path)

# Get exports
exports = []
if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
    for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if exp.name:
            exports.append(exp.name.decode('utf-8', errors='replace'))

dll_size = os.path.getsize(dll_path)

# Check protocol support via version info strings
proto_indicators = {
    'LDAP': ['curl_ldap'],
    'LDAPS': ['curl_ldap'],
    'IMAP': ['curl_imap'],
    'POP3': ['curl_pop3'],
    'SMTP': ['curl_smtp'],
    'SMB': ['curl_smb'],
    'MQTT': ['curl_mqtt'],
    'NTLM': ['Curl_ntlm_core', 'USE_CURL_NTLM_CORE'],
    'TELNET': ['curl_telnet'],
    'TFTP': ['curl_tftp'],
    'DICT': ['curl_dict'],
    'RTSP': ['curl_rtsp'],
    'GOPHER': ['curl_gopher'],
}

# Check curl_ API functions
curl_api = sorted([e for e in exports if e.startswith('curl_')])

# Check specific protocol handler symbols in exports
proto_handlers = {}
for proto in ['imap', 'pop3', 'smtp', 'smb', 'ldap', 'mqtt', 'telnet', 'tftp', 'dict', 'rtsp', 'gopher', 'ntlm']:
    matching = [e for e in exports if proto in e.lower()]
    proto_handlers[proto] = matching[:5]  # first 5

print(f"DLL Size: {dll_size:,} bytes ({dll_size/1024/1024:.2f} MB)")
print(f"Total Exports: {len(exports)}")
print(f"curl_ API count: {len(curl_api)}")
print()

# Key new APIs
key_apis = [
    'curl_easy_header', 'curl_easy_nextheader', 'curl_easy_impersonate_customized',
    'curl_easy_impersonate',
]
print("=== Key curl APIs ===")
for api in key_apis:
    print(f"  {api}: {'FOUND' if api in exports else 'MISSING'}")

# Check NTLM support
ntlm_syms = [e for e in exports if 'ntlm' in e.lower()]
print(f"\n=== NTLM symbols: {len(ntlm_syms)} ===")
for s in ntlm_syms[:10]:
    print(f"  {s}")

# Check protocol handlers
print(f"\n=== Protocol handlers ===")
for proto, syms in sorted(proto_handlers.items()):
    status = "PRESENT" if syms else "ABSENT"
    print(f"  {proto}: {status} ({len(syms)} symbols)")
    for s in syms[:3]:
        print(f"    - {s}")

# Protocol version info - check curl_version_info
print(f"\n=== Summary ===")
print(f"DLL size increase from last build (4,764,672): {dll_size - 4764672:,} bytes")
print(f"Expected protocols: dict file ftp ftps gopher gophers http https imap imaps ipfs ipns ldap ldaps mqtt mqtts pop3 pop3s rtsp smb smbs smtp smtps telnet tftp ws wss")

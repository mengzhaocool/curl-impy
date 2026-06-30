# Fix easyoptions.c v2 - add missing impersonate CURLOPT entries
import re

filepath = r"d:\curl-impersonate-8.20.0\deps\curl-8.20.0\lib\easyoptions.c"

# New entries: (name, curlopt, type)
new_entries = [
    ("FORM_BOUNDARY", "CURLOPT_FORM_BOUNDARY", "CURLOT_STRING"),
    ("HTTP2_NO_PRIORITY", "CURLOPT_HTTP2_NO_PRIORITY", "CURLOT_LONG"),
    ("HTTP2_PSEUDO_HEADERS_ORDER", "CURLOPT_HTTP2_PSEUDO_HEADERS_ORDER", "CURLOT_STRING"),
    ("HTTP2_SETTINGS", "CURLOPT_HTTP2_SETTINGS", "CURLOT_STRING"),
    ("HTTP2_STREAMS", "CURLOPT_HTTP2_STREAMS", "CURLOT_STRING"),
    ("HTTP2_WINDOW_UPDATE", "CURLOPT_HTTP2_WINDOW_UPDATE", "CURLOT_LONG"),
    ("HTTP3_PSEUDO_HEADERS_ORDER", "CURLOPT_HTTP3_PSEUDO_HEADERS_ORDER", "CURLOT_STRING"),
    ("HTTP3_SETTINGS", "CURLOPT_HTTP3_SETTINGS", "CURLOT_STRING"),
    ("HTTP3_SIG_HASH_ALGS", "CURLOPT_HTTP3_SIG_HASH_ALGS", "CURLOT_STRING"),
    ("HTTP3_TLS_EXTENSION_ORDER", "CURLOPT_HTTP3_TLS_EXTENSION_ORDER", "CURLOT_STRING"),
    ("HTTPBASEHEADER", "CURLOPT_HTTPBASEHEADER", "CURLOT_SLIST"),
    ("HTTPHEADER_ORDER", "CURLOPT_HTTPHEADER_ORDER", "CURLOT_STRING"),
    ("IMPERSONATE", "CURLOPT_IMPERSONATE", "CURLOT_STRING"),
    ("PROXY_CREDENTIAL_NO_REUSE", "CURLOPT_PROXY_CREDENTIAL_NO_REUSE", "CURLOT_LONG"),
    ("QUIC_TRANSPORT_PARAMETERS", "CURLOPT_QUIC_TRANSPORT_PARAMETERS", "CURLOT_STRING"),
    ("SPLIT_COOKIES", "CURLOPT_SPLIT_COOKIES", "CURLOT_LONG"),
    ("SSL_CERT_COMPRESSION", "CURLOPT_SSL_CERT_COMPRESSION", "CURLOT_STRING"),
    ("SSL_ENABLE_ALPS", "CURLOPT_SSL_ENABLE_ALPS", "CURLOT_LONG"),
    ("SSL_ENABLE_TICKET", "CURLOPT_SSL_ENABLE_TICKET", "CURLOT_LONG"),
    ("SSL_PERMUTE_EXTENSIONS", "CURLOPT_SSL_PERMUTE_EXTENSIONS", "CURLOT_LONG"),
    ("SSL_SIG_HASH_ALGS", "CURLOPT_SSL_SIG_HASH_ALGS", "CURLOT_STRING"),
    ("STREAM_EXCLUSIVE", "CURLOPT_STREAM_EXCLUSIVE", "CURLOT_LONG"),
    ("TLS_DELEGATED_CREDENTIALS", "CURLOPT_TLS_DELEGATED_CREDENTIALS", "CURLOT_STRING"),
    ("TLS_EXTENSION_ORDER", "CURLOPT_TLS_EXTENSION_ORDER", "CURLOT_STRING"),
    ("TLS_GREASE", "CURLOPT_TLS_GREASE", "CURLOT_LONG"),
    ("TLS_KEY_SHARES_LIMIT", "CURLOPT_TLS_KEY_SHARES_LIMIT", "CURLOT_LONG"),
    ("TLS_KEY_USAGE_NO_CHECK", "CURLOPT_TLS_KEY_USAGE_NO_CHECK", "CURLOT_LONG"),
    ("TLS_RECORD_SIZE_LIMIT", "CURLOPT_TLS_RECORD_SIZE_LIMIT", "CURLOT_LONG"),
    ("TLS_SIGNED_CERT_TIMESTAMPS", "CURLOPT_TLS_SIGNED_CERT_TIMESTAMPS", "CURLOT_LONG"),
    ("TLS_STATUS_REQUEST", "CURLOPT_TLS_STATUS_REQUEST", "CURLOT_LONG"),
    ("TLS_USE_NEW_ALPS_CODEPOINT", "CURLOPT_TLS_USE_NEW_ALPS_CODEPOINT", "CURLOT_LONG"),
]

# Anchor: insert new entry after the existing entry with this name
insert_after = {
    "FORBID_REUSE": ["FORM_BOUNDARY"],
    "HTTP200ALIASES": ["HTTP2_NO_PRIORITY", "HTTP2_PSEUDO_HEADERS_ORDER", "HTTP2_SETTINGS", "HTTP2_STREAMS", "HTTP2_WINDOW_UPDATE", "HTTP3_PSEUDO_HEADERS_ORDER", "HTTP3_SETTINGS", "HTTP3_SIG_HASH_ALGS", "HTTP3_TLS_EXTENSION_ORDER"],
    "HTTPAUTH": ["HTTPBASEHEADER"],
    "HTTPHEADER": ["HTTPHEADER_ORDER"],
    "INFILESIZE_LARGE": ["IMPERSONATE"],
    "PROXY_CAPATH": ["PROXY_CREDENTIAL_NO_REUSE"],
    "QUICK_EXIT": ["QUIC_TRANSPORT_PARAMETERS"],
    "SOCKS5_GSSAPI_SERVICE": ["SPLIT_COOKIES"],
    "SSLVERSION": ["SSL_CERT_COMPRESSION"],
    "SSL_ENABLE_ALPN": ["SSL_ENABLE_ALPS"],
    "SSL_ENABLE_NPN": ["SSL_ENABLE_TICKET"],
    "SSL_OPTIONS": ["SSL_PERMUTE_EXTENSIONS"],
    "SSL_SIGNATURE_ALGORITHMS": ["SSL_SIG_HASH_ALGS"],
    "STREAM_DEPENDS_E": ["STREAM_EXCLUSIVE"],
    "TLSAUTH_USERNAME": ["TLS_DELEGATED_CREDENTIALS", "TLS_EXTENSION_ORDER", "TLS_GREASE", "TLS_KEY_SHARES_LIMIT", "TLS_KEY_USAGE_NO_CHECK", "TLS_RECORD_SIZE_LIMIT", "TLS_SIGNED_CERT_TIMESTAMPS", "TLS_STATUS_REQUEST", "TLS_USE_NEW_ALPS_CODEPOINT"],
}

entry_lines = {}
for new_name, new_curlopt, new_type in new_entries:
    entry_lines[new_name] = f'  {{ "{new_name}", {new_curlopt}, {new_type}, 0 }},\n'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

result = []
added = set()
pattern = re.compile(r'\s+\{\s*"([^"]+)"')

for line in lines:
    result.append(line)
    m = pattern.match(line)
    if m:
        current_name = m.group(1)
        if current_name in insert_after:
            entries_to_add = insert_after[current_name]
            for entry_name in entries_to_add:
                if entry_name not in added and entry_name in entry_lines:
                    result.append(entry_lines[entry_name])
                    added.add(entry_name)
                    print(f"Added {entry_name} after {current_name}")

# Check for any missed entries
missed = [e[0] for e in new_entries if e[0] not in added]
if missed:
    print(f"\nWARNING: {len(missed)} entries were not added: {missed}")
else:
    print(f"\nAll {len(added)} new entries added successfully!")

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(result)

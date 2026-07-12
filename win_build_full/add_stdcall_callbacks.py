#!/usr/bin/env python3
"""
add_stdcall_callbacks.py - Add __stdcall to curl's callback function pointer typedefs.

Only modifies curl's user-facing callbacks (set via curl_easy_setopt).
Library-internal callbacks (zlib zalloc/zfree, brotli alloc/free, zstd alloc/free)
are NOT changed because their implementations are cdecl in the library source.

On x64: stdcall == cdecl (no effect).
On x86: stdcall = callee cleans stack. User callbacks must use __stdcall.
"""
import sys
import os
import re

def add_stdcall_to_file(filepath, callback_names):
    """Add __stdcall to specified callback typedefs in a file."""
    if not os.path.isfile(filepath):
        return 0

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    original = content
    count = 0

    for name in callback_names:
        # Match: typedef <ret> (*<name>)(<args>)
        pattern = re.compile(
            r'(typedef\s+[\w\s\*]+?\s+)\(\s*\*\s*(' + re.escape(name) + r')\s*\)(\s*\()',
            re.MULTILINE
        )
        def replacer(m):
            nonlocal count
            if '__stdcall' in m.group(0) or 'WINAPI' in m.group(0):
                return m.group(0)
            count += 1
            return f'{m.group(1)}(__stdcall *{m.group(2)}){m.group(3)}'
        content = pattern.sub(replacer, content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[stdcall] {os.path.basename(filepath)}: {count} typedefs -> __stdcall")
    else:
        print(f"[stdcall] {os.path.basename(filepath)}: no changes")

    return count

def main():
    deps_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    # Only curl's user-facing callbacks
    curl_inc = os.path.join(deps_dir, "curl-8.20.0", "include", "curl")

    # All curl callback types (user provides these via curl_easy_setopt)
    curl_callbacks = [
        'curl_progress_callback',
        'curl_xferinfo_callback',
        'curl_write_callback',
        'curl_resolver_start_callback',
        'curl_chunk_bgn_callback',
        'curl_chunk_end_callback',
        'curl_fnmatch_callback',
        'curl_seek_callback',
        'curl_read_callback',
        'curl_trailer_callback',
        'curl_sockopt_callback',
        'curl_ioctl_callback',
        'curl_debug_callback',
        'curl_prereq_callback',
        'curl_conv_callback',
        'curl_ssl_ctx_callback',
        'curl_hstsread_callback',
        'curl_hstswrite_callback',
        'curl_formget_callback',
        'curl_lock_function',
        'curl_unlock_function',
        'curl_opensocket_callback',
        'curl_closesocket_callback',
        'curl_header_callback',
    ]

    total = 0
    for h in ['curl.h', 'multi.h', 'easy.h', 'header.h', 'websockets.h']:
        total += add_stdcall_to_file(os.path.join(curl_inc, h), curl_callbacks)

    print(f"[stdcall] Total: {total} curl callback typedefs modified to __stdcall")
    print("[stdcall] Library-internal callbacks (zlib/brotli/zstd/BoringSSL) left as cdecl")
    sys.exit(0)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
add_stdcall_callbacks.py - Add __stdcall to curl's callback typedefs
and create __stdcall wrappers for internal callback implementations.

Strategy:
1. Modify callback typedefs in curl.h to use __stdcall
2. Create __stdcall wrapper functions for internal callbacks
3. Replace assignments to use wrappers instead of original functions
4. Handle CRT functions (fread/fseek) with dedicated wrappers

On x64: stdcall == cdecl (no effect).
On x86: wrappers ensure correct stack cleanup (callee cleans stack).
"""
import sys
import os
import re
import glob

CURL_CALLBACKS = [
    'curl_progress_callback', 'curl_xferinfo_callback',
    'curl_write_callback', 'curl_resolver_start_callback',
    'curl_chunk_bgn_callback', 'curl_chunk_end_callback',
    'curl_fnmatch_callback', 'curl_seek_callback',
    'curl_read_callback', 'curl_trailer_callback',
    'curl_sockopt_callback', 'curl_ioctl_callback',
    'curl_debug_callback', 'curl_prereq_callback',
    'curl_conv_callback', 'curl_ssl_ctx_callback',
    'curl_hstsread_callback', 'curl_hstswrite_callback',
    'curl_formget_callback', 'curl_lock_function',
    'curl_unlock_function', 'curl_opensocket_callback',
    'curl_closesocket_callback', 'curl_header_callback',
]

def add_stdcall_to_typedefs(filepath, callback_names):
    """Add __stdcall to callback function pointer typedefs."""
    if not os.path.isfile(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content
    count = 0
    for name in callback_names:
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
        print(f"[stdcall] {os.path.basename(filepath)}: no typedef changes")
    return count

def fix_formdata_c(lib_dir):
    """Fix formdata.c: replace fread/fseek with __stdcall wrappers."""
    filepath = os.path.join(lib_dir, "formdata.c")
    if not os.path.isfile(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content
    wrappers = '''
/* __stdcall wrappers for CRT functions used as curl callbacks (x86 stdcall) */
static size_t __stdcall curl_fread_callback(char *buf, size_t sz, size_t nm, void *p) {
    return fread(buf, sz, nm, (FILE *)p);
}
static int __stdcall curl_fseek_callback(void *p, curl_off_t offset, int whence) {
    return fseek((FILE *)p, (long)offset, whence);
}
'''
    if 'curl_fread_callback' not in content:
        last_include = content.rfind('#include')
        if last_include >= 0:
            end_of_include = content.index('\n', last_include) + 1
            content = content[:end_of_include] + wrappers + content[end_of_include:]
    content = content.replace('(curl_read_callback)fread', 'curl_fread_callback')
    content = content.replace('                           curlx_fseek,',
                               '                           curl_fseek_callback,')
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[stdcall] formdata.c: CRT wrappers added")
        return 1
    return 0

def fix_crt_callback_casts(lib_dir):
    """Fix CRT function casts (fwrite/fread) in url.c, setopt.c, sendf.c.

    The default write callback is (curl_write_callback)fwrite, but fwrite is
    __cdecl. After changing curl_write_callback to __stdcall, calling fwrite
    through it causes stack corruption on x86.

    Fix: add __stdcall wrappers and replace the casts.
    """
    count = 0

    # Wrappers to add to url.c (first file that sets defaults)
    wrappers = '''
/* __stdcall wrappers for CRT functions used as default callbacks (x86 stdcall) */
static size_t __stdcall curl_fwrite_callback(char *ptr, size_t size, size_t nmemb, void *stream) {
    return fwrite(ptr, size, nmemb, (FILE *)stream);
}
static size_t __stdcall curl_fread_default_cb(char *buf, size_t sz, size_t nm, void *p) {
    return fread(buf, sz, nm, (FILE *)p);
}
'''

    # Fix url.c
    url_path = os.path.join(lib_dir, "url.c")
    if os.path.isfile(url_path):
        with open(url_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        original = content
        if 'curl_fwrite_callback' not in content:
            last_include = content.rfind('#include')
            if last_include >= 0:
                end_of_include = content.index('\n', last_include) + 1
                content = content[:end_of_include] + wrappers + content[end_of_include:]
        content = content.replace('(curl_write_callback)fwrite', 'curl_fwrite_callback')
        content = content.replace('(curl_read_callback)fread', 'curl_fread_default_cb')
        if content != original:
            with open(url_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[stdcall] url.c: fwrite/fread CRT wrappers added")
            count += 1

    # Fix setopt.c
    setopt_path = os.path.join(lib_dir, "setopt.c")
    if os.path.isfile(setopt_path):
        with open(setopt_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        original = content
        if 'curl_fwrite_callback' not in content:
            last_include = content.rfind('#include')
            if last_include >= 0:
                end_of_include = content.index('\n', last_include) + 1
                content = content[:end_of_include] + wrappers + content[end_of_include:]
        content = content.replace('(curl_write_callback)fwrite', 'curl_fwrite_callback')
        content = content.replace('(curl_read_callback)fread', 'curl_fread_default_cb')
        if content != original:
            with open(setopt_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[stdcall] setopt.c: fwrite/fread CRT wrappers added")
            count += 1

    # Fix sendf.c (comparison with fread)
    sendf_path = os.path.join(lib_dir, "sendf.c")
    if os.path.isfile(sendf_path):
        with open(sendf_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        original = content
        # The comparison checks if fread_func == default fread callback.
        # After our fix, the default is curl_fread_default_cb (defined in url.c).
        # Since sendf.c can't see url.c's static function, just replace the
        # comparison to always check against the wrapper we define here.
        sendf_wrappers = '''
/* __stdcall wrapper for fread (same as url.c's curl_fread_default_cb) */
static size_t __stdcall curl_fread_default_cb(char *buf, size_t sz, size_t nm, void *p) {
    return fread(buf, sz, nm, (FILE *)p);
}
'''
        if 'curl_fread_default_cb' not in content:
            last_include = content.rfind('#include')
            if last_include >= 0:
                end_of_include = content.index('\n', last_include) + 1
                content = content[:end_of_include] + sendf_wrappers + content[end_of_include:]
        content = content.replace('(curl_read_callback)fread', 'curl_fread_default_cb')
        if content != original:
            with open(sendf_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[stdcall] sendf.c: fread comparison fixed")
            count += 1

    return count

def fix_mime_c(lib_dir):
    """Fix mime.c: create __stdcall wrappers for static callback functions."""
    filepath = os.path.join(lib_dir, "mime.c")
    if not os.path.isfile(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content

    # Wrappers for static callback functions in mime.c
    wrappers = '''
/* __stdcall wrappers for internal mime callbacks (x86 stdcall) */
static size_t __stdcall mime_mem_read_cb(char *b, size_t s, size_t n, void *p) {
    return mime_mem_read(b, s, n, p);
}
static int __stdcall mime_mem_seek_cb(void *p, curl_off_t o, int w) {
    return mime_mem_seek(p, o, w);
}
static size_t __stdcall mime_file_read_cb(char *b, size_t s, size_t n, void *p) {
    return mime_file_read(b, s, n, p);
}
static int __stdcall mime_file_seek_cb(void *p, curl_off_t o, int w) {
    return mime_file_seek(p, o, w);
}
static int __stdcall mime_subparts_seek_cb(void *p, curl_off_t o, int w) {
    return mime_subparts_seek(p, o, w);
}
'''

    if 'mime_mem_read_cb' not in content:
        # Insert wrappers before the first use (before Curl_mime_subparts_init or similar)
        # Find a good insertion point: after mime_subparts_seek definition
        marker = 'static void mime_subparts_free'
        idx = content.find(marker)
        if idx < 0:
            # Fallback: insert before curl_mime_data_cb
            marker = 'CURLcode curl_mime_data_cb'
            idx = content.find(marker)
        if idx >= 0:
            content = content[:idx] + wrappers + '\n' + content[idx:]

    # Replace assignments to use wrappers
    content = content.replace('part->readfunc = mime_mem_read;',
                               'part->readfunc = mime_mem_read_cb;')
    content = content.replace('part->seekfunc = mime_mem_seek;',
                               'part->seekfunc = mime_mem_seek_cb;')
    content = content.replace('part->readfunc = mime_file_read;',
                               'part->readfunc = mime_file_read_cb;')
    content = content.replace('part->seekfunc = mime_file_seek;',
                               'part->seekfunc = mime_file_seek_cb;')
    content = content.replace('part->seekfunc = mime_subparts_seek;',
                               'part->seekfunc = mime_subparts_seek_cb;')

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[stdcall] mime.c: wrappers added + assignments replaced")
        return 1
    return 0

def fix_nonstatic_callbacks(lib_dir):
    """Add __stdcall to non-static internal callback functions.

    Searches ALL .c and .h files for function definitions/declarations
    matching the target function names.
    """
    # Function names to modify (these are assigned to callback pointers)
    targets = [
        'Curl_ftp_parselist',
        'Curl_fnmatch',
        'Curl_client_write',
    ]

    count = 0
    all_files = glob.glob(os.path.join(lib_dir, '*.c')) + glob.glob(os.path.join(lib_dir, '*.h'))

    for filepath in all_files:
        if not os.path.isfile(filepath):
            continue
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        original = content
        file_count = 0

        for func_name in targets:
            # Match: <type> <func_name>( at start of line (definition/declaration)
            # NOT: return <func_name>( or = <func_name>( (function call)
            # Use [^\n]+? (non-greedy) to avoid consuming the space before func_name
            pattern = re.compile(
                r'(\n[^\n]+?\s+)(' + re.escape(func_name) + r')(\s*\()',
                re.MULTILINE
            )
            def replacer(m, fn=func_name):
                nonlocal file_count
                if '__stdcall' in m.group(0):
                    return m.group(0)
                prefix = m.group(1).strip()
                words = prefix.split()
                if not words:
                    return m.group(0)
                last_word = words[-1].rstrip('(){};,')
                # Skip function calls
                if last_word.lower() in ('return', 'if', 'while', 'for', 'else', 'case', 'switch', 'sizeof'):
                    return m.group(0)
                if last_word in ('=', 'NULL', '0', '1'):
                    return m.group(0)
                # Only modify if last word looks like a return type
                # Must be a C type or start with uppercase (custom type like CURLSHcode)
                # Must NOT end with ; (that's a statement, not a type)
                # Must NOT contain * unless it's a pure type (e.g., "void*" is ok but "*list" is not)
                C_TYPES = {'int', 'size_t', 'void', 'char', 'unsigned', 'long', 'short',
                           'float', 'double', 'bool', 'CURLcode', 'CURL', 'curlioerr',
                           'CURLSTScode', 'ssize_t', 'CURLSHcode', 'static', 'extern'}
                if last_word in C_TYPES or (last_word and last_word[0].isupper() and not last_word.startswith('*')):
                    file_count += 1
                    return f'{m.group(1)}__stdcall {m.group(2)}{m.group(3)}'
                return m.group(0)
            content = pattern.sub(replacer, content)

        if content != original and file_count > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[stdcall] {os.path.basename(filepath)}: {file_count} functions -> __stdcall")
            count += file_count

    return count

def fix_ftp_c(lib_dir):
    """Fix ftp.c: replace Curl_ftp_parselist assignment with cast."""
    filepath = os.path.join(lib_dir, "ftp.c")
    if not os.path.isfile(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content
    # The assignment is: data->set.fwrite_func = Curl_ftp_parselist;
    # Curl_ftp_parselist is non-static, so __stdcall should work via fix_nonstatic_callbacks
    # But if it doesn't, use explicit cast
    # Actually, let's just make sure the assignment uses the right type
    # If fix_nonstatic_callbacks added __stdcall to the definition, the assignment should work
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return 1
    return 0

def main():
    deps_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    curl_inc = os.path.join(deps_dir, "curl-8.20.0", "include", "curl")
    curl_lib = os.path.join(deps_dir, "curl-8.20.0", "lib")
    total = 0

    # 1. Modify callback typedefs
    for h in ['curl.h', 'multi.h', 'easy.h', 'header.h', 'websockets.h']:
        total += add_stdcall_to_typedefs(os.path.join(curl_inc, h), CURL_CALLBACKS)

    # 2. Fix CRT function casts (fread/fseek in formdata.c)
    total += fix_formdata_c(curl_lib)

    # 2b. Fix CRT function casts in url.c, setopt.c, sendf.c
    total += fix_crt_callback_casts(curl_lib)

    # 3. Fix static callback functions in mime.c (create wrappers)
    total += fix_mime_c(curl_lib)

    # 4. Fix non-static internal callback functions (add __stdcall directly)
    total += fix_nonstatic_callbacks(curl_lib)

    print(f"[stdcall] Total: {total} modifications")
    sys.exit(0)

if __name__ == '__main__':
    main()

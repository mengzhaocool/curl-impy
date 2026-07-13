#!/usr/bin/env python3
"""
fix_merge_forward_decl.py - Fix impersonation header injection (Bug 2) and
stdcall for Curl_share_lock/unlock.

1. Add forward declaration of Curl_http_merge_headers before Curl_add_custom_headers
2. Add merge call at the start of Curl_add_custom_headers
3. Add __stdcall to Curl_share_lock/unlock in curl_share.c and curl_share.h
"""
import sys
import os
import re

def fix_http_c(lib_dir):
    """Fix http.c: add forward declaration and merge call."""
    http_c = os.path.join(lib_dir, "http.c")
    if not os.path.isfile(http_c):
        print("[fix] http.c not found")
        return
    
    with open(http_c, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content
    
    # 0. Add #include "slist.h" if missing (needed for Curl_slist_duplicate)
    if '#include "slist.h"' not in content:
        # Add after the last #include
        last_include = content.rfind('#include ')
        if last_include >= 0:
            end_of_line = content.index('\n', last_include) + 1
            content = content[:end_of_line] + '#include "slist.h"\n' + content[end_of_line:]
            print("[fix] Added #include \"slist.h\" to http.c")
    
    # 1. Add forward declaration
    func_sig = "CURLcode Curl_add_custom_headers(struct Curl_easy *data,"
    if func_sig in content:
        before_func = content[:content.find(func_sig)]
        if "Curl_http_merge_headers" not in before_func:
            fwd = "/* Forward declaration for base header merging */\n"
            fwd += "static CURLcode Curl_http_merge_headers(struct Curl_easy *data);\n\n"
            content = content.replace(func_sig, fwd + func_sig, 1)
            print("[fix] Added forward declaration for Curl_http_merge_headers")
    
    # 2. Add merge call before noproxyheaders
    if "Curl_http_merge_headers(data)" not in content:
        # Find the noproxyheaders block (added by curl.patch)
        noproxy_idx = content.find("struct curl_slist *noproxyheaders")
        if noproxy_idx >= 0:
            # Find the comment before noproxyheaders
            comment_idx = content.rfind("/*", 0, noproxy_idx)
            if comment_idx >= 0:
                line_start = content.rfind('\n', 0, comment_idx) + 1
                merge = "\n  if(data->state.base_headers && !data->state.merged_headers) {\n"
                merge += "    CURLcode merge_result = Curl_http_merge_headers(data);\n"
                merge += "    if(merge_result)\n"
                merge += "      return merge_result;\n"
                merge += "  }\n\n"
                content = content[:line_start] + merge + content[line_start:]
                print("[fix] Added merge call")
    
    if content != original:
        with open(http_c, 'w', encoding='utf-8') as f:
            f.write(content)
        print("[fix] http.c patched")
    else:
        print("[fix] http.c no changes needed")
    
    # 3. Fix merge function definition: add 'static', remove unused 'int i;'
    with open(http_c, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content
    # Replace: CURLcode Curl_http_merge_headers( -> static CURLcode Curl_http_merge_headers(
    content = content.replace(
        'CURLcode Curl_http_merge_headers(struct Curl_easy *data)\n{\n  int i;\n',
        'static CURLcode Curl_http_merge_headers(struct Curl_easy *data)\n{\n'
    )
    if content != original:
        with open(http_c, 'w', encoding='utf-8') as f:
            f.write(content)
        print("[fix] Fixed merge function definition (static + removed int i)")

def fix_share_stdcall(lib_dir):
    """Add __stdcall to Curl_share_lock/unlock in .c and .h files."""
    targets = ['Curl_share_lock', 'Curl_share_unlock']
    
    for fname in ['curl_share.c', 'curl_share.h']:
        fpath = os.path.join(lib_dir, fname)
        if not os.path.isfile(fpath):
            continue
        
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        modified = False
        for i, line in enumerate(lines):
            if '__stdcall' in line:
                continue
            for func_name in targets:
                # Only match function definitions/declarations, not calls
                # A definition has a return type before the function name
                # A call has = return if while for etc. before it
                pattern = re.compile(r'\b' + re.escape(func_name) + r'\s*\(')
                match = pattern.search(line)
                if not match:
                    continue
                
                before = line[:match.start()].strip()
                words = before.split()
                if not words:
                    continue  # No preceding text (function call at start of line)
                
                last_word = words[-1].rstrip('(){};,')
                # Skip if it's a function call (preceded by keyword or =)
                if last_word.lower() in ('return', 'if', 'while', 'for', 'else', 'case', 'switch', 'sizeof'):
                    continue
                if last_word in ('=', 'NULL', '0', '1'):
                    continue
                # Skip if last_word ends with ; (statement) or is lowercase variable
                if last_word.endswith(';'):
                    continue
                # Only add __stdcall if last_word looks like a return type
                C_TYPES = {'int', 'size_t', 'void', 'char', 'unsigned', 'long', 'short',
                           'float', 'double', 'bool', 'CURLcode', 'CURL', 'curlioerr',
                           'CURLSTScode', 'ssize_t', 'CURLSHcode', 'static', 'extern'}
                if last_word in C_TYPES or (last_word and last_word[0].isupper() and not last_word.startswith('*')):
                    # Insert __stdcall before function name
                    idx = match.start()
                    lines[i] = line[:idx] + '__stdcall ' + line[idx:]
                    modified = True
                    print(f"[fix] {fname}:{i+1}: {func_name} -> __stdcall")
                    break
        
        if modified:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.writelines(lines)

def fix_slist_free(lib_dir):
    """Fix use-after-free: _do_impersonate frees slist that CURLOPT_HTTPBASEHEADER only stores."""
    easy_c = os.path.join(lib_dir, "easy.c")
    if not os.path.isfile(easy_c):
        return
    
    with open(easy_c, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    original = content
    
    # Remove curl_slist_free_all(headers) after CURLOPT_HTTPBASEHEADER
    # The slist is stored by reference, not duplicated, so freeing it causes use-after-free
    old = 'curl_easy_setopt(data, CURLOPT_HTTPBASEHEADER, headers);\n      curl_slist_free_all(headers);'
    new = 'curl_easy_setopt(data, CURLOPT_HTTPBASEHEADER, headers);\n      /* headers slist is now owned by curl, do not free */'
    if old in content:
        content = content.replace(old, new, 1)
        print("[fix] Removed slist free-after-setopt (use-after-free fix)")
    
    if content != original:
        with open(easy_c, 'w', encoding='utf-8') as f:
            f.write(content)

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_merge_forward_decl.py <curl_lib_dir>")
        sys.exit(1)
    
    lib_dir = sys.argv[1]
    fix_http_c(lib_dir)
    fix_share_stdcall(lib_dir)
    fix_slist_free(lib_dir)
    sys.exit(0)

if __name__ == '__main__':
    main()

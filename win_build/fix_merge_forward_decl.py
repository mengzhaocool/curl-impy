#!/usr/bin/env python3
"""
fix_merge_forward_decl.py - Post-patch fixes for stdcall on share lock/unlock.

All http.c merge-related fixes (slist.h include, forward declaration, merge call,
static keyword, slist_free removal) are now included in curl.patch directly.

This script only handles:
1. Curl_share_lock/unlock __stdcall conversion (for x86 stdcall callback support)
"""
import sys
import os
import re

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
                pattern = re.compile(r'\b' + re.escape(func_name) + r'\s*\(')
                match = pattern.search(line)
                if not match:
                    continue
                
                before = line[:match.start()].strip()
                words = before.split()
                if not words:
                    continue
                
                last_word = words[-1].rstrip('(){};,')
                if last_word.lower() in ('return', 'if', 'while', 'for', 'else', 'case', 'switch', 'sizeof'):
                    continue
                if last_word in ('=', 'NULL', '0', '1'):
                    continue
                if last_word.endswith(';'):
                    continue
                C_TYPES = {'int', 'size_t', 'void', 'char', 'unsigned', 'long', 'short',
                           'float', 'double', 'bool', 'CURLcode', 'CURL', 'curlioerr',
                           'CURLSTScode', 'ssize_t', 'CURLSHcode', 'static', 'extern'}
                if last_word in C_TYPES or (last_word and last_word[0].isupper() and not last_word.startswith('*')):
                    idx = match.start()
                    lines[i] = line[:idx] + '__stdcall ' + line[idx:]
                    modified = True
                    print(f"[fix] {fname}:{i+1}: {func_name} -> __stdcall")
                    break
        
        if modified:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.writelines(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_merge_forward_decl.py <curl_lib_dir>")
        sys.exit(1)
    
    lib_dir = sys.argv[1]
    fix_share_stdcall(lib_dir)
    sys.exit(0)

if __name__ == '__main__':
    main()

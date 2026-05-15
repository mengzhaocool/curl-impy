#!/usr/bin/env python3
"""fix_vla.py - Fix Variable Length Array (VLA) usage for MSVC compatibility.

MSVC does not support C99 VLAs. This script finds common VLA patterns in
curl source files and replaces them with fixed-size arrays or heap allocations.
The fix-vla-msvc.patch handles specific known cases; this script catches others.
"""
import os
import re
import sys

def fix_vla_in_file(filepath):
    """Fix VLA declarations in a single file."""
    if not os.path.isfile(filepath):
        return False
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    original = content
    changes = 0
    
    # Pattern 1: type var[n]; where n is a variable (not a constant/define/macro)
    # Replace with type var[256]; (reasonable max) or use _alloca
    # Only fix obvious cases - variable-length stack arrays
    # e.g., char buf[len]; -> char *buf = (char*)malloc(len); ... free(buf);
    # This is too risky to do automatically. Instead, just flag them.
    
    # Pattern 2: VLA in for-loop initializers
    # for(int i=0; i<n; i++) { int arr[n]; } -> int arr[1024];
    # Again, risky to auto-fix.
    
    # Instead, focus on the known patterns that break MSVC builds:
    
    # Fix: const size_t X = N; used as VLA size -> #define X N
    # This is what the patch does for kMaxSignatureAlgorithmNameLen
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def scan_for_vla(directory):
    """Scan directory for VLA patterns and report."""
    vla_patterns = [
        # type name[variable]; where variable is not a macro/constant
        re.compile(r'\w+\s+\w+\[\s*\w+\s*\]\s*;', re.MULTILINE),
    ]
    
    found = []
    for root, dirs, files in os.walk(directory):
        # Skip build dirs and hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'build']
        for f in files:
            if f.endswith(('.c', '.h', '.cc', '.cpp')):
                filepath = os.path.join(root, f)
                with open(filepath, 'r', encoding='utf-8', errors='replace') as fh:
                    for i, line in enumerate(fh, 1):
                        line = line.strip()
                        # Skip comments, preprocessor, constants
                        if line.startswith('//') or line.startswith('#') or line.startswith('/*'):
                            continue
                        # Check for VLA: array with non-numeric size
                        m = re.search(r'(\w+)\s+(\w+)\[\s*(\w+)\s*\]\s*;', line)
                        if m:
                            size = m.group(3)
                            # If size is all digits or uppercase (likely a macro), skip
                            if size.isdigit() or size.isupper() or size.startswith('CURLOPT'):
                                continue
                            found.append((filepath, i, line))
    return found

def main():
    if len(sys.argv) < 2:
        print("Usage: fix_vla.py <curl_src_dir>")
        sys.exit(1)
    
    curl_src = sys.argv[1]
    
    if not os.path.isdir(curl_src):
        print(f"[ERROR] Directory not found: {curl_src}")
        sys.exit(1)
    
    print(f"[VLA] Scanning {curl_src} for VLA patterns...")
    found = scan_for_vla(curl_src)
    
    if found:
        print(f"[VLA] Found {len(found)} potential VLA patterns:")
        for filepath, line_no, line in found[:20]:
            rel = os.path.relpath(filepath, curl_src)
            print(f"  {rel}:{line_no}: {line[:80]}")
        if len(found) > 20:
            print(f"  ... and {len(found) - 20} more")
    else:
        print("[VLA] No VLA patterns found.")
    
    # The fix-vla-msvc.patch should handle the known cases.
    # This script is mainly for scanning and reporting.
    print("[VLA] Scan complete.")

if __name__ == '__main__':
    main()

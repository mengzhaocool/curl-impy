"""Run _step6_build.py and capture output"""
import subprocess, sys, os

result = subprocess.run([sys.executable, r'd:\curl-impersonate-8.20.0\_step6_build.py'], 
                       capture_output=True, timeout=3600)

# Write raw bytes to file
with open(r'd:\curl-impersonate-8.20.0\_build_output.txt', 'wb') as f:
    f.write(b'=== STDOUT ===\n')
    f.write(result.stdout or b'(empty)')
    f.write(b'\n=== STDERR ===\n')
    f.write(result.stderr or b'(empty)')
    f.write(f'\n=== RC: {result.returncode} ===\n'.encode())

# Print last part - use sys.stdout with replacement
stdout_text = (result.stdout or b'').decode('utf-8', errors='replace')
if len(stdout_text) > 4000:
    sys.stdout.buffer.write(b'... (showing last 4000) ...\n')
    sys.stdout.buffer.write(stdout_text[-4000:].encode('utf-8', errors='replace'))
else:
    sys.stdout.buffer.write(stdout_text.encode('utf-8', errors='replace'))

sys.stdout.buffer.write(f'\nRC: {result.returncode}\n'.encode())

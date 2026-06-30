import subprocess, sys
r = subprocess.run(
    ['cmake', '--build', r'd:\curl-impersonate-8.20.0\build\curl-dll', '--config', 'Release'],
    capture_output=True, text=True, timeout=300,
    encoding='utf-8', errors='replace'
)
print(f"Return code: {r.returncode}")
print(f"STDOUT:\n{r.stdout[-3000:]}")
print(f"STDERR:\n{r.stderr[-3000:]}")

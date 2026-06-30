import subprocess, os

# Use the VS environment from the bat file
env_bat = r"D:\curl-impersonate-8.20.0\_msvc_env.bat"
result = subprocess.run(f'cmd /c "{env_bat} >nul 2>&1 && set"', capture_output=True, text=True)
env = {}
for line in result.stdout.splitlines():
    if '=' in line:
        k, v = line.split('=', 1)
        env[k] = v

cmake = r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
r = subprocess.run(
    [cmake, "--build", r"D:\curl-impersonate-8.20.0\build\curl", "--config", "Release"],
    capture_output=True, env=env, errors='replace'
)
out = (r.stdout or '') + (r.stderr or '')
with open(r"d:\curl-impersonate-8.20.0\_curl_build_err.txt", "w", encoding="utf-8") as f:
    f.write(out[-8000:])
print(f"RC={r.returncode}, output len={len(out)}")

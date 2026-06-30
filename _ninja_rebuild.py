import subprocess
r = subprocess.run(
    [r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe"],
    capture_output=True, text=True, cwd=r"D:\curl-impersonate-8.20.0\build\curl"
)
with open(r"d:\curl-impersonate-8.20.0\_ninja_output.txt", "w") as f:
    f.write("STDOUT:\n")
    f.write(r.stdout[-5000:] if r.stdout else "empty\n")
    f.write("\nSTDERR:\n")
    f.write(r.stderr[-5000:] if r.stderr else "empty\n")
print(f"RC={r.returncode}")

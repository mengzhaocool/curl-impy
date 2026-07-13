"""Compile C4 stdcall test for x86."""
import subprocess, os

bat_content = r'''@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat" x86 >nul 2>&1
cd /d D:\curl-impersonate\win_build_full\tests
cl /arch:SSE2 /nologo /W3 /Fe:c4_stdcall.exe c4_stdcall.c /link
'''

bat_path = os.path.join(os.path.dirname(__file__), '_compile_c4.bat')
with open(bat_path, 'w') as f:
    f.write(bat_content)

result = subprocess.run([bat_path], capture_output=True, shell=True)
print("STDOUT:", result.stdout.decode('gbk', errors='replace'))
print("STDERR:", result.stderr.decode('gbk', errors='replace'))
print("Return code:", result.returncode)

exe_path = os.path.join(os.path.dirname(__file__), 'c4_stdcall.exe')
if os.path.exists(exe_path):
    print(f"\nSUCCESS: {exe_path} ({os.path.getsize(exe_path)} bytes)")
else:
    print("\nFAILED")

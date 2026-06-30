"""Quick rebuild of just curl to see remaining errors"""
import subprocess, os

vs_path = r'C:\Program Files\Microsoft Visual Studio\2022\Community'
cl_dir = os.path.join(vs_path, 'VC', 'Tools', 'MSVC', '14.44.35207', 'bin', 'Hostx64', 'x64')
sdk_bin = r'D:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64'
env = os.environ.copy()
env['PATH'] = cl_dir + ';' + sdk_bin + ';' + env.get('PATH', '')
path_dirs = env['PATH'].split(';')
cleaned = [d for d in path_dirs if 'msys64' not in d.lower() and 'mingw' not in d.lower()]
env['PATH'] = ';'.join(cleaned)
msvc_ver = os.path.join(vs_path, 'VC', 'Tools', 'MSVC', '14.44.35207')
sdk_inc = r'D:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0'
sdk_lib = r'D:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0'
env['LIB'] = os.path.join(msvc_ver, 'lib', 'x64') + ';' + os.path.join(sdk_lib, 'ucrt', 'x64') + ';' + os.path.join(sdk_lib, 'um', 'x64')
env['INCLUDE'] = os.path.join(msvc_ver, 'include') + ';' + os.path.join(sdk_inc, 'ucrt') + ';' + os.path.join(sdk_inc, 'um') + ';' + os.path.join(sdk_inc, 'shared')

cmake = r'C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe'
bdir = r'd:\curl-impersonate-8.20.0\build\curl'

r = subprocess.run(f'"{cmake}" --build "{bdir}" --config Release -- -k 0', 
                   shell=True, capture_output=True, text=True, 
                   encoding='utf-8', errors='replace', env=env, timeout=300)

# Extract unique error lines
lines = r.stdout.split('\n') if r.stdout else []
errors = set()
for l in lines:
    l = l.strip()
    if 'error C' in l or 'fatal error' in l.lower():
        errors.add(l[:250])

print(f'Unique errors: {len(errors)}')
for e in sorted(errors)[:30]:
    print(f'  {e}')

print(f'\nRC: {r.returncode}')

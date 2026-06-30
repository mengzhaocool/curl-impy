"""Rebuild curl and capture detailed errors"""
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

# Build with verbose ninja to see actual commands
r = subprocess.run(f'"{cmake}" --build "{bdir}" --config Release -- -k 0', 
                   shell=True, capture_output=True, text=True, 
                   encoding='utf-8', errors='replace', env=env, timeout=300)

# Write full output to file
with open(r'd:\curl-impersonate-8.20.0\_curl_build_errors.txt', 'w', encoding='utf-8') as f:
    f.write(r.stdout or '')
    f.write('\n\n=== STDERR ===\n')
    f.write(r.stderr or '')

# Print error lines
lines = (r.stdout or '').split('\n')
errors = [l for l in lines if 'error C' in l or 'fatal error' in l.lower() or 'FAILED:' in l]
print(f'Error lines: {len(errors)}')
for e in errors[:30]:
    print(f'  {e[:250]}')

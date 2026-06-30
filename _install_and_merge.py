"""Install curl and merge static libs"""
import subprocess, os, shutil

vs = r'C:\Program Files\Microsoft Visual Studio\2022\Community'
cl = os.path.join(vs, 'VC', 'Tools', 'MSVC', '14.44.35207', 'bin', 'Hostx64', 'x64', 'cl.exe')
cl_dir = os.path.dirname(cl)
msvc_ver_dir = os.path.dirname(os.path.dirname(os.path.dirname(cl_dir)))

env = os.environ.copy()
env['PATH'] = cl_dir + ';' + r'D:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64;' + env.get('PATH', '')
path_dirs = env.get('PATH', '').split(';')
env['PATH'] = ';'.join([d for d in path_dirs if 'msys64' not in d.lower() and 'mingw' not in d.lower()])
env['LIB'] = ';'.join([
    os.path.join(msvc_ver_dir, 'lib', 'x64'),
    r'D:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\ucrt\x64',
    r'D:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0\um\x64'
])
env['INCLUDE'] = ';'.join([
    os.path.join(msvc_ver_dir, 'include'),
    r'D:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0\ucrt',
    r'D:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0\um',
    r'D:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0\shared'
])

cmake = r'C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe'
bdir = r'd:\curl-impersonate-8.20.0\build\curl'
curl_inst = r'd:\curl-impersonate-8.20.0\install\curl'
output_dir = r'd:\curl-impersonate-8.20.0\output'
install_dir = r'd:\curl-impersonate-8.20.0\install'

# Install
r = subprocess.run([cmake, '--install', bdir, '--config', 'Release'], 
                   capture_output=True, text=True, encoding='utf-8', errors='replace',
                   env=env, timeout=600)
print(f'Install RC: {r.returncode}')

# Find static lib
static_lib = None
for path in [
    os.path.join(bdir, 'lib', 'libcurl-impersonate.lib'),
    os.path.join(bdir, 'lib', 'Release', 'libcurl-impersonate.lib'),
]:
    if os.path.exists(path):
        static_lib = path
        break
if not static_lib:
    for root, dirs, files in os.walk(bdir):
        for f in files:
            if 'libcurl-impersonate' in f and f.endswith('.lib'):
                static_lib = os.path.join(root, f)
                break

if static_lib:
    print(f'Static lib: {static_lib} ({os.path.getsize(static_lib):,} bytes)')
    
    # Merge libs
    os.makedirs(output_dir, exist_ok=True)
    merged_lib = os.path.join(output_dir, 'libcurl-impersonate.lib')
    
    merge_libs = [
        static_lib,
        os.path.join(install_dir, 'boringssl', 'lib', 'libssl.lib'),
        os.path.join(install_dir, 'boringssl', 'lib', 'libcrypto.lib'),
        os.path.join(install_dir, 'zlib', 'lib', 'zlibstatic.lib'),
        os.path.join(install_dir, 'brotli', 'lib', 'brotlidec.lib'),
        os.path.join(install_dir, 'brotli', 'lib', 'brotlienc.lib'),
        os.path.join(install_dir, 'brotli', 'lib', 'brotlicommon.lib'),
        os.path.join(install_dir, 'nghttp2', 'lib', 'nghttp2.lib'),
        os.path.join(install_dir, 'ngtcp2', 'lib', 'ngtcp2.lib'),
        os.path.join(install_dir, 'ngtcp2', 'lib', 'ngtcp2_crypto_boringssl.lib'),
        os.path.join(install_dir, 'nghttp3', 'lib', 'nghttp3.lib'),
        os.path.join(install_dir, 'zstd', 'lib', 'zstd_static.lib'),
    ]
    merge_libs = [l for l in merge_libs if os.path.exists(l)]
    print(f'Merging {len(merge_libs)} libs...')
    
    lib_cmd = 'lib.exe /OUT:"' + merged_lib + '" ' + ' '.join(f'"{l}"' for l in merge_libs)
    r = subprocess.run(lib_cmd, shell=True, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    if r.returncode == 0:
        print(f'Merged lib: {merged_lib} ({os.path.getsize(merged_lib):,} bytes)')
    else:
        print(f'Merge failed: {r.stderr[:200]}')
        shutil.copy2(static_lib, merged_lib)
        print(f'Copied instead: {merged_lib} ({os.path.getsize(merged_lib):,} bytes)')
    
    # Copy headers
    out_inc = os.path.join(output_dir, 'include', 'curl')
    curl_inc = os.path.join(curl_inst, 'include', 'curl')
    if os.path.exists(curl_inc):
        if os.path.exists(out_inc):
            shutil.rmtree(out_inc)
        shutil.copytree(curl_inc, out_inc)
        print(f'Headers copied: {len(os.listdir(out_inc))} files')
    
    print('\nStatic lib build SUCCESS!')
else:
    print('ERROR: static lib not found!')

"""Rebuild only the DLL with WHOLEARCHIVE fix"""
import subprocess, os, sys, shutil

BASE = r"d:\curl-impersonate-8.20.0"
DEPS = os.path.join(BASE, "deps")
BUILD_DIR = os.path.join(BASE, "build")
INSTALL_DIR = os.path.join(BASE, "install")
OUTPUT_DIR = os.path.join(BASE, "output")

CURL_SRC = os.path.join(DEPS, "curl-8.20.0")
BORINGSSL_INST = os.path.join(INSTALL_DIR, "boringssl")
BROTLI_INST = os.path.join(INSTALL_DIR, "brotli")
NGHTTP2_INST = os.path.join(INSTALL_DIR, "nghttp2")
NGHTTP3_INST = os.path.join(INSTALL_DIR, "nghttp3")
NGTCP2_INST = os.path.join(INSTALL_DIR, "ngtcp2")
ZLIB_INST = os.path.join(INSTALL_DIR, "zlib")
ZSTD_INST = os.path.join(INSTALL_DIR, "zstd")

def run(cmd, cwd=None, timeout=600, env=None):
    print(f"  CMD: {cmd[:200]}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout
    )
    if result.returncode != 0:
        print(f"  ERROR: code {result.returncode}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:1000]}")
        return False
    return True


def find_vs():
    for vs in [r"C:\Program Files\Microsoft Visual Studio\2022\Community",
               r"C:\Program Files\Microsoft Visual Studio\2022\Professional",
               r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise"]:
        if os.path.exists(vs):
            return vs
    return None


def setup_msvc_env(arch="x64"):
    vs_path = find_vs()
    if not vs_path:
        print("ERROR: VS not found!")
        return None
    
    vcvarsall = os.path.join(vs_path, "VC", "Auxiliary", "Build", "vcvarsall.bat")
    
    # Find cl.exe
    msvc_root = os.path.join(vs_path, "VC", "Tools", "MSVC")
    cl_path = None
    if os.path.exists(msvc_root):
        for ver in sorted(os.listdir(msvc_root), reverse=True):
            cl = os.path.join(msvc_root, ver, "bin", "Hostx64", arch, "cl.exe")
            if os.path.exists(cl):
                cl_path = cl
                break
    
    if not cl_path:
        print("ERROR: cl.exe not found!")
        return None
    
    env = os.environ.copy()
    cl_dir = os.path.dirname(cl_path)
    env['PATH'] = cl_dir + ';' + env.get('PATH', '')
    env['CC'] = cl_path
    
    msvc_ver_dir = os.path.dirname(os.path.dirname(os.path.dirname(cl_dir)))
    
    # Find Windows SDK
    sdk_include = sdk_lib = None
    for sdk_base in [r'C:\Program Files (x86)\Windows Kits\10', r'D:\Program Files (x86)\Windows Kits\10']:
        inc_dir = os.path.join(sdk_base, 'Include')
        if os.path.exists(inc_dir):
            for ver in sorted(os.listdir(inc_dir), reverse=True):
                if os.path.exists(os.path.join(inc_dir, ver, 'um')) and os.path.exists(os.path.join(inc_dir, ver, 'ucrt')):
                    sdk_include = os.path.join(inc_dir, ver)
                    sdk_lib = os.path.join(sdk_base, 'Lib', ver)
                    break
            if sdk_include:
                break
    
    includes = [os.path.join(msvc_ver_dir, 'include')]
    if sdk_include:
        includes.append(os.path.join(sdk_include, 'ucrt'))
        includes.append(os.path.join(sdk_include, 'um'))
        includes.append(os.path.join(sdk_include, 'shared'))
    env['INCLUDE'] = ';'.join(includes)
    
    libs = [os.path.join(msvc_ver_dir, 'lib', arch)]
    if sdk_lib:
        libs.append(os.path.join(sdk_lib, 'ucrt', arch))
        libs.append(os.path.join(sdk_lib, 'um', arch))
    env['LIB'] = ';'.join(libs)
    
    # Find cmake and ninja
    for cmake_candidate in [r"C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe"]:
        if os.path.exists(cmake_candidate):
            env['CMAKE_EXE'] = cmake_candidate
            break
    
    for ninja_candidate in [r"C:\vcpkg\downloads\tools\ninja-1.13.2-windows\ninja.exe"]:
        if os.path.exists(ninja_candidate):
            env['NINJA_EXE'] = ninja_candidate
            break
    
    # Clean msys64 from PATH
    path_dirs = env.get('PATH', '').split(';')
    cleaned = [d for d in path_dirs if 'msys64' not in d.lower() and 'mingw' not in d.lower()]
    env['PATH'] = ';'.join(cleaned)
    
    return env


def main():
    print("=" * 60)
    print("  Rebuild DLL with WHOLEARCHIVE fix")
    print("=" * 60)
    
    env = setup_msvc_env("x64")
    if not env:
        sys.exit(1)
    
    cmake_exe = env.get('CMAKE_EXE', 'cmake')
    ninja_exe = env.get('NINJA_EXE', 'ninja')
    
    bdir = os.path.join(BUILD_DIR, "curl-dll")
    
    # Step 1: Delete CMake cache to force reconfigure
    cache = os.path.join(bdir, "CMakeCache.txt")
    if os.path.exists(cache):
        print(f"\n[1] Deleting CMake cache: {cache}")
        os.remove(cache)
    
    # Step 2: Reconfigure
    print(f"\n[2] CMake configure (DLL with WHOLEARCHIVE)...")
    
    cmake_args = [
        cmake_exe, '-G', 'Ninja', '-S', CURL_SRC, '-B', bdir,
        f'-DCMAKE_INSTALL_PREFIX={INSTALL_DIR}/curl',
        f'-DCMAKE_MAKE_PROGRAM={ninja_exe}',
        f'-DCMAKE_C_COMPILER={env["CC"]}',
        '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
        '-DCMAKE_BUILD_TYPE=Release',
        '-DCMAKE_C_FLAGS=/DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB',
        '-DCMAKE_CXX_FLAGS=/EHsc /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB',
        '-DBUILD_SHARED_LIBS=ON',
        '-DBUILD_STATIC_LIBS=OFF',
        '-DCURL_USE_OPENSSL=ON',
        '-DHAVE_BORINGSSL=ON',
        f'-DOPENSSL_ROOT_DIR={BORINGSSL_INST}',
        f'-DOPENSSL_INCLUDE_DIR={BORINGSSL_INST}\\include',
        f'-DOPENSSL_LIBRARIES={BORINGSSL_INST}\\lib\\libssl.lib;{BORINGSSL_INST}\\lib\\libcrypto.lib',
        '-DCURL_BROTLI=ON',
        f'-DBROTLI_INCLUDE_DIR={BROTLI_INST}\\include',
        f'-DBROTLIDEC_LIBRARY={BROTLI_INST}\\lib\\brotlidec.lib',
        f'-DBROTLIENC_LIBRARY={BROTLI_INST}\\lib\\brotlienc.lib',
        f'-DBROTLICOMMON_LIBRARY={BROTLI_INST}\\lib\\brotlicommon.lib',
        '-DUSE_NGHTTP2=ON',
        f'-DNGHTTP2_INCLUDE_DIR={NGHTTP2_INST}\\include',
        f'-DNGHTTP2_LIBRARY={NGHTTP2_INST}\\lib\\nghttp2.lib',
        f'-DNGHTTP2_ROOT={NGHTTP2_INST}',
        '-DUSE_NGTCP2=ON',
        f'-DNGTCP2_INCLUDE_DIR={NGTCP2_INST}\\include',
        f'-DNGTCP2_LIBRARY={NGTCP2_INST}\\lib\\ngtcp2.lib',
        f'-DNGTCP2_CRYPTO_BORINGSSL_LIBRARY={NGTCP2_INST}\\lib\\ngtcp2_crypto_boringssl.lib',
        '-DUSE_NGHTTP3=ON',
        f'-DNGHTTP3_INCLUDE_DIR={NGHTTP3_INST}\\include',
        f'-DNGHTTP3_LIBRARY={NGHTTP3_INST}\\lib\\nghttp3.lib',
        f'-DZLIB_INCLUDE_DIR={ZLIB_INST}\\include',
        f'-DZLIB_LIBRARY={ZLIB_INST}\\lib\\zlibstatic.lib',
        f'-DZLIB_ROOT={ZLIB_INST}',
        '-DCURL_ZSTD=ON',
        f'-DZSTD_INCLUDE_DIR={ZSTD_INST}\\include',
        f'-DZSTD_LIBRARY={ZSTD_INST}\\lib\\zstd_static.lib',
        f'-DZSTD_ROOT={ZSTD_INST}',
        '-DHTTP_ONLY=OFF',
        '-DENABLE_WEBSOCKETS=ON',
        '-DUSE_LIBIDN2=OFF',
        '-DCURL_USE_LIBPSL=OFF',
        '-DUSE_QUICHE=OFF',
        '-DENABLE_MANUAL=OFF',
        '-DCURL_USE_LIBSSH2=OFF',
        '-DCURL_USE_GSSAPI=OFF',
        '-DBUILD_CURL_EXE=OFF',
        '-DCURL_HIDDEN_SYMBOLS=OFF',
        '-DCURL_STATIC_CRT=ON',
    ]
    
    cmd = ' '.join(f'"{a}"' if ' ' in a else a for a in cmake_args)
    if not run(cmd, env=env, timeout=600):
        print("FATAL: CMake configure failed!")
        sys.exit(1)
    
    # Check if WHOLEARCHIVE message appears in CMake output
    print("\n  Checking for WHOLEARCHIVE in CMake output...")
    
    # Step 3: Build
    print(f"\n[3] Building DLL...")
    build_cmd = f'"{cmake_exe}" --build "{bdir}" --config Release'
    if not run(build_cmd, env=env, timeout=1800):
        print("FATAL: Build failed!")
        sys.exit(1)
    
    # Step 4: Find and copy DLL
    dll_path = None
    for path in [
        os.path.join(bdir, "lib", "libcurl-impersonate.dll"),
        os.path.join(bdir, "bin", "libcurl-impersonate.dll"),
    ]:
        if os.path.exists(path):
            dll_path = path
            break
    
    if not dll_path:
        for root, dirs, files in os.walk(bdir):
            for f in files:
                if f == 'libcurl-impersonate.dll':
                    dll_path = os.path.join(root, f)
                    break
    
    if dll_path:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        dst = os.path.join(OUTPUT_DIR, "libcurl-impersonate.dll")
        shutil.copy2(dll_path, dst)
        
        sz = os.path.getsize(dst)
        print(f"\n  DLL: {dst} ({sz:,} bytes = {sz/1024/1024:.1f} MB)")
        
        # Copy import lib
        lib_name = os.path.splitext(os.path.basename(dll_path))[0] + '.lib'
        import_lib = os.path.join(os.path.dirname(dll_path), lib_name)
        if os.path.exists(import_lib):
            shutil.copy2(import_lib, os.path.join(OUTPUT_DIR, "libcurl-impersonate_imp.lib"))
        
        # Also copy DLL to project root
        shutil.copy2(dst, os.path.join(BASE, "libcurl-impersonate.dll"))
        
        if sz > 5_000_000:
            print(f"  OK: DLL size looks correct (>5MB with all deps statically linked)")
        else:
            print(f"  WARN: DLL seems small ({sz/1024/1024:.1f} MB), expected ~6MB with WHOLEARCHIVE")
    else:
        print("  ERROR: DLL not found!")
    
    # Step 5: Also rebuild merged static lib
    print(f"\n[5] Rebuilding merged static lib...")
    curl_build = os.path.join(BUILD_DIR, "curl")
    curl_static = os.path.join(curl_build, "lib", "libcurl-impersonate.lib")
    
    if os.path.exists(curl_static):
        merge_libs = [
            curl_static,
            os.path.join(BORINGSSL_INST, "lib", "libssl.lib"),
            os.path.join(BORINGSSL_INST, "lib", "libcrypto.lib"),
            os.path.join(ZLIB_INST, "lib", "zlibstatic.lib"),
            os.path.join(BROTLI_INST, "lib", "brotlidec.lib"),
            os.path.join(BROTLI_INST, "lib", "brotlienc.lib"),
            os.path.join(BROTLI_INST, "lib", "brotlicommon.lib"),
            os.path.join(NGHTTP2_INST, "lib", "nghttp2.lib"),
            os.path.join(NGTCP2_INST, "lib", "ngtcp2.lib"),
            os.path.join(NGTCP2_INST, "lib", "ngtcp2_crypto_boringssl.lib"),
            os.path.join(NGHTTP3_INST, "lib", "nghttp3.lib"),
            os.path.join(ZSTD_INST, "lib", "zstd_static.lib"),
        ]
        merge_libs = [l for l in merge_libs if os.path.exists(l)]
        
        merged_lib = os.path.join(OUTPUT_DIR, "libcurl-impersonate.lib")
        lib_cmd = 'lib.exe /OUT:"' + merged_lib + '" ' + ' '.join(f'"{l}"' for l in merge_libs)
        if run(lib_cmd, env=env):
            sz = os.path.getsize(merged_lib)
            print(f"  Merged static lib: {merged_lib} ({sz:,} bytes = {sz/1024/1024:.1f} MB)")
        else:
            print("  WARN: lib.exe merge failed!")
    
    print("\n" + "=" * 60)
    print("  REBUILD COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

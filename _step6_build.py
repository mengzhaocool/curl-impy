"""
Step 6: Build curl-impersonate from existing patched source.
Build order: zlib → zstd → brotli → nghttp2 → nghttp3 → BoringSSL → ngtcp2 → curl-lib → curl-dll
Uses tool paths from win_build/detect_env.bat as reference.
"""
import subprocess, os, sys, shutil, glob

BASE = r"d:\curl-impersonate-8.20.0"
DEPS = os.path.join(BASE, "deps")
BUILD_DIR = os.path.join(BASE, "build")
INSTALL_DIR = os.path.join(BASE, "install")
OUTPUT_DIR = os.path.join(BASE, "output")
PATCHES_DIR = os.path.join(BASE, "patches")
WIN_BUILD = os.path.join(BASE, "win_build")

# Source dirs
ZLIB_SRC = os.path.join(DEPS, "zlib-1.3.1")
ZSTD_SRC = os.path.join(DEPS, "zstd-1.5.7")
BROTLI_SRC = os.path.join(DEPS, "brotli-1.2.0")
NGHTTP2_SRC = os.path.join(DEPS, "nghttp2-1.63.0")
NGHTTP3_SRC = os.path.join(DEPS, "nghttp3-1.15.0")
BORINGSSL_SRC = os.path.join(DEPS, "boringssl")
NGTCP2_SRC = os.path.join(DEPS, "ngtcp2-1.20.0")
CURL_SRC = os.path.join(DEPS, "curl-8.20.0")

# Install dirs
ZLIB_INST = os.path.join(INSTALL_DIR, "zlib")
ZSTD_INST = os.path.join(INSTALL_DIR, "zstd")
BROTLI_INST = os.path.join(INSTALL_DIR, "brotli")
NGHTTP2_INST = os.path.join(INSTALL_DIR, "nghttp2")
NGHTTP3_INST = os.path.join(INSTALL_DIR, "nghttp3")
BORINGSSL_INST = os.path.join(INSTALL_DIR, "boringssl")
NGTCP2_INST = os.path.join(INSTALL_DIR, "ngtcp2")
CURL_INST = os.path.join(INSTALL_DIR, "curl")


def find_tool(candidates, name):
    """Find a tool from a list of candidate paths"""
    for path in candidates:
        if os.path.exists(path):
            return os.path.normpath(path)
    print(f"  WARN: {name} not found from candidates, trying PATH...")
    r = subprocess.run(f"where {name}", shell=True, capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().split('\n')[0].strip()
    return None


def detect_tools(env):
    """Detect build tools, referencing win_build/detect_env.bat paths"""
    print("\n[detect] Finding build tools...")
    
    cmake = find_tool([
        r"C:\vcpkg\downloads\tools\cmake-3.31.10-windows\cmake-3.31.10-windows-x86_64\bin\cmake.exe",
        r"C:\msys64\mingw64\bin\cmake.exe",
    ], "cmake")
    
    ninja = find_tool([
        r"C:\vcpkg\downloads\tools\ninja-1.13.2-windows\ninja.exe",
        r"C:\msys64\mingw64\bin\ninja.exe",
    ], "ninja")
    
    nasm = find_tool([
        r"C:\vcpkg\downloads\tools\nasm\nasm-3.01\nasm.exe",
    ], "nasm")
    
    git = find_tool([
        r"C:\Program Files\Git\cmd\git.exe",
    ], "git")
    
    perl = find_tool([
        r"C:\Program Files\Git\usr\bin\perl.exe",
    ], "perl")
    
    go = find_tool([
        r"C:\Program Files\Go\bin\go.exe",
    ], "go")
    
    tools = {
        'CMAKE': cmake, 'NINJA': ninja, 'NASM': nasm,
        'GIT': git, 'PERL': perl, 'GO': go
    }
    
    for name, path in tools.items():
        status = "OK" if path else "MISSING"
        print(f"  {name}: {status} {path or ''}")
    
    # CMake and Ninja are required
    if not cmake:
        print("FATAL: CMake not found!")
        sys.exit(1)
    if not ninja:
        print("FATAL: Ninja not found!")
        sys.exit(1)
    
    # Add tool paths to env (but DON'T add their dirs to PATH,
    # because msys64 dirs contain ld.exe which conflicts with MSVC link.exe)
    for name, path in tools.items():
        if path:
            env[name + '_EXE'] = path
    
    # Remove msys64 paths from PATH to avoid ld.exe conflict
    path_dirs = env.get('PATH', '').split(';')
    cleaned = [d for d in path_dirs if 'msys64' not in d.lower() and 'mingw' not in d.lower()]
    env['PATH'] = ';'.join(cleaned)
    print(f"  PATH cleaned: removed msys64/mingw entries ({len(path_dirs)-len(cleaned)} removed)")
    
    return tools


def run(cmd, cwd=None, env=None, timeout=600):
    """Run command and capture output"""
    print(f"  CMD: {cmd[:200]}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout
    )
    if result.returncode != 0:
        print(f"  ERROR: command failed with code {result.returncode}")
        if result.stderr:
            # Print last 1000 chars of stderr
            err = result.stderr
            if len(err) > 1000:
                print(f"  STDERR (last 1000): ...{err[-1000:]}")
            else:
                print(f"  STDERR: {err}")
        if result.stdout:
            out = result.stdout
            if len(out) > 500:
                print(f"  STDOUT (last 500): ...{out[-500:]}")
            else:
                print(f"  STDOUT: {out}")
        return False
    return True


def find_vs():
    """Find Visual Studio installation"""
    for vs in [r"C:\Program Files\Microsoft Visual Studio\2022\Community",
               r"C:\Program Files\Microsoft Visual Studio\2022\Professional",
               r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise",
               r"D:\Program Files\Microsoft Visual Studio\2022\Community",
               r"D:\Program Files\Microsoft Visual Studio\2022\Professional",
               r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community",
               r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional"]:
        if os.path.exists(vs):
            return vs
    vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    if os.path.exists(vswhere):
        result = subprocess.run(
            [vswhere, "-latest", "-property", "installationPath"],
            capture_output=True, text=True
        )
        path = result.stdout.strip()
        if path and os.path.exists(path):
            return path
    return None


def setup_msvc_env(arch="x64"):
    """Setup MSVC build environment by calling vcvarsall.bat"""
    vs_path = find_vs()
    if not vs_path:
        print("ERROR: Visual Studio not found!")
        return None
    
    vcvarsall = os.path.join(vs_path, "VC", "Auxiliary", "Build", "vcvarsall.bat")
    if not os.path.exists(vcvarsall):
        print(f"ERROR: vcvarsall.bat not found at {vcvarsall}")
        return None
    
    print(f"  VS: {vs_path}")
    print(f"  vcvarsall: {vcvarsall}")
    
    # Find cl.exe path directly
    cl_path = None
    msvc_root = os.path.join(vs_path, "VC", "Tools", "MSVC")
    if os.path.exists(msvc_root):
        for ver in sorted(os.listdir(msvc_root), reverse=True):
            cl = os.path.join(msvc_root, ver, "bin", "Hostx64", arch, "cl.exe")
            if os.path.exists(cl):
                cl_path = cl
                break
    
    if not cl_path:
        print("  ERROR: cl.exe not found in VS directory!")
        return None
    
    print(f"  cl.exe: {cl_path}")
    
    # Build a clean environment with MSVC tools
    env = os.environ.copy()
    
    # Add cl.exe directory to PATH (front)
    cl_dir = os.path.dirname(cl_path)
    env['PATH'] = cl_dir + ';' + env.get('PATH', '')
    env['CC'] = cl_path
    
    # Set LIB, INCLUDE, LIBPATH manually for MSVC
    msvc_ver_dir = os.path.dirname(os.path.dirname(os.path.dirname(cl_dir)))  # e.g. 14.44.35207
    
    # Find Windows SDK
    sdk_include = sdk_lib = None
    for sdk_base in [r'C:\Program Files (x86)\Windows Kits\10', r'D:\Program Files (x86)\Windows Kits\10']:
        inc_dir = os.path.join(sdk_base, 'Include')
        if os.path.exists(inc_dir):
            for ver in sorted(os.listdir(inc_dir), reverse=True):
                um_inc = os.path.join(inc_dir, ver, 'um')
                ucrt_inc = os.path.join(inc_dir, ver, 'ucrt')
                if os.path.exists(um_inc) and os.path.exists(ucrt_inc):
                    sdk_include = os.path.join(inc_dir, ver)
                    sdk_lib = os.path.join(sdk_base, 'Lib', ver)
                    break
            if sdk_include:
                break
    
    if sdk_include and sdk_lib:
        print(f"  Windows SDK: {os.path.basename(sdk_include)}")
        # Add Windows SDK bin directory to PATH (for rc.exe, mt.exe, etc.)
        sdk_bin_base = os.path.join(os.path.dirname(os.path.dirname(sdk_include)), 'bin')
        if os.path.exists(sdk_bin_base):
            for ver in sorted(os.listdir(sdk_bin_base), reverse=True):
                sdk_bin = os.path.join(sdk_bin_base, ver, arch)
                if os.path.exists(sdk_bin) and os.path.exists(os.path.join(sdk_bin, 'rc.exe')):
                    env['PATH'] = sdk_bin + ';' + env.get('PATH', '')
                    print(f"  SDK bin: {sdk_bin}")
                    break
    
    # Build INCLUDE
    includes = []
    includes.append(os.path.join(msvc_ver_dir, 'include'))
    if sdk_include:
        includes.append(os.path.join(sdk_include, 'ucrt'))
        includes.append(os.path.join(sdk_include, 'um'))
        includes.append(os.path.join(sdk_include, 'shared'))
    env['INCLUDE'] = ';'.join(includes)
    
    # Build LIB
    libs = []
    libs.append(os.path.join(msvc_ver_dir, 'lib', arch))
    if sdk_lib:
        libs.append(os.path.join(sdk_lib, 'ucrt', arch))
        libs.append(os.path.join(sdk_lib, 'um', arch))
    env['LIB'] = ';'.join(libs)
    
    # Build LIBPATH
    libpaths = []
    libpaths.append(os.path.join(msvc_ver_dir, 'lib', arch))
    env['LIBPATH'] = ';'.join(libpaths)
    
    # Remove msys64/mingw from PATH to avoid ld.exe conflict
    path_dirs = env.get('PATH', '').split(';')
    cleaned = [d for d in path_dirs if 'msys64' not in d.lower() and 'mingw' not in d.lower()]
    removed = len(path_dirs) - len(cleaned)
    if removed > 0:
        print(f"  Removed {removed} msys64/mingw entries from PATH")
    env['PATH'] = ';'.join(cleaned)
    
    # Print key env vars
    for key in ['LIB', 'INCLUDE']:
        val = env.get(key, '')
        if len(val) > 100:
            print(f"  {key}={val[:100]}...")
        else:
            print(f"  {key}={val}")
    
    return env


def cmake_configure(src_dir, build_dir, install_dir, extra_args, env):
    """Run CMake configure with Ninja generator"""
    os.makedirs(build_dir, exist_ok=True)
    
    cmake_exe = env.get('CMAKE_EXE', 'cmake')
    ninja_exe = env.get('NINJA_EXE', 'ninja')
    
    cmd = [cmake_exe, '-G', 'Ninja', '-S', src_dir, '-B', build_dir]
    cmd.append(f'-DCMAKE_INSTALL_PREFIX={install_dir}')
    cmd.append(f'-DCMAKE_MAKE_PROGRAM={ninja_exe}')
    
    cc = env.get('CC', 'cl')
    cmd.append(f'-DCMAKE_C_COMPILER={cc}')
    
    if 'CXX' in env:
        cmd.append(f'-DCMAKE_CXX_COMPILER={env["CXX"]}')
    
    cmd.append('-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded')
    cmd.append('-DCMAKE_BUILD_TYPE=Release')
    cmd.append('-DCMAKE_C_FLAGS_RELEASE=/MT /O2 /DNDEBUG')
    
    # Parse extra_args
    import shlex
    cmd.extend(shlex.split(extra_args))
    
    print(f"  CMD: {' '.join(cmd[:6])}... ({len(cmd)} args)")
    result = subprocess.run(
        cmd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=600
    )
    if result.returncode != 0:
        print(f"  ERROR: cmake configure failed with code {result.returncode}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:1000]}")
        return False
    return True


def cmake_build(build_dir, env, target=None, timeout=1200):
    """Run CMake build"""
    cmake_exe = env.get('CMAKE_EXE', 'cmake')
    cmd = [cmake_exe, '--build', build_dir, '--config', 'Release']
    if target:
        cmd.extend(['--target', target])
    print(f"  CMD: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout
    )
    if result.returncode != 0:
        print(f"  ERROR: cmake build failed with code {result.returncode}")
        err = result.stderr + result.stdout
        if len(err) > 2000:
            print(f"  OUTPUT (last 2000): ...{err[-2000:]}")
        elif err:
            print(f"  OUTPUT: {err}")
        return False
    return True


def cmake_install(build_dir, env):
    """Run CMake install"""
    cmake_exe = env.get('CMAKE_EXE', 'cmake')
    cmd = [cmake_exe, '--install', build_dir, '--config', 'Release']
    print(f"  CMD: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=600
    )
    if result.returncode != 0:
        print(f"  ERROR: cmake install failed with code {result.returncode}")
        if result.stderr:
            print(f"  STDERR: {result.stderr[:500]}")
        return False
    return True


# ========================================================================
# Individual build functions
# ========================================================================

def build_zlib(env):
    """Build zlib - ref: win_build/build_zlib.bat"""
    print("\n=== Building zlib ===")
    # Skip if already built
    if os.path.exists(os.path.join(ZLIB_INST, "lib", "zlibstatic.lib")):
        print("  zlib already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "zlib")
    
    if not cmake_configure(ZLIB_SRC, bdir, ZLIB_INST,
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG" '
        '-DCMAKE_INSTALL_LIBDIR=lib', env):
        return False
    if not cmake_build(bdir, env):
        return False
    if not cmake_install(bdir, env):
        return False
    
    # Verify
    for lib_name in ['zlibstatic.lib', 'zlib.lib']:
        lib_path = os.path.join(ZLIB_INST, "lib", lib_name)
        if os.path.exists(lib_path):
            print(f"  zlib OK: {lib_path}")
            return True
    print("  ERROR: zlib lib not found!")
    return False


def build_zstd(env):
    """Build zstd - ref: win_build/build_zstd.bat"""
    print("\n=== Building zstd ===")
    if os.path.exists(os.path.join(ZSTD_INST, "lib", "zstd_static.lib")):
        print("  zstd already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "zstd")
    src_cmake = os.path.join(ZSTD_SRC, "build", "cmake")
    
    if not cmake_configure(src_cmake, bdir, ZSTD_INST,
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG" '
        '-DZSTD_BUILD_SHARED=OFF '
        '-DZSTD_BUILD_PROGRAMS=OFF '
        '-DZSTD_MULTITHREAD_SUPPORT=OFF', env):
        return False
    if not cmake_build(bdir, env):
        return False
    if not cmake_install(bdir, env):
        return False
    print("  zstd OK")
    return True


def build_brotli(env):
    """Build brotli - ref: win_build/build_brotli.bat"""
    print("\n=== Building brotli ===")
    if os.path.exists(os.path.join(BROTLI_INST, "lib", "brotlidec.lib")) or \
       os.path.exists(os.path.join(BROTLI_INST, "lib", "brotlidec.lib")):
        print("  brotli already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "brotli")
    
    if not cmake_configure(BROTLI_SRC, bdir, BROTLI_INST,
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG" '
        '-DCMAKE_CXX_FLAGS="/MT /O2 /DNDEBUG /EHsc" '
        '-DBUILD_SHARED_LIBS=OFF '
        '-DBROTLI_BUNDLED_MODE=OFF', env):
        return False
    if not cmake_build(bdir, env):
        return False
    if not cmake_install(bdir, env):
        return False
    print("  brotli OK")
    return True


def build_nghttp2(env):
    """Build nghttp2 - ref: win_build/build_nghttp2.bat"""
    print("\n=== Building nghttp2 ===")
    if os.path.exists(os.path.join(NGHTTP2_INST, "lib", "nghttp2.lib")):
        print("  nghttp2 already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "nghttp2")
    
    if not cmake_configure(NGHTTP2_SRC, bdir, NGHTTP2_INST,
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG" '
        '-DENABLE_LIB_ONLY=ON '
        '-DBUILD_SHARED_LIBS=OFF '
        '-DBUILD_STATIC_LIBS=ON '
        '-DNGHTTP2_ENABLE_DOC=OFF', env):
        return False
    if not cmake_build(bdir, env):
        return False
    if not cmake_install(bdir, env):
        return False
    print("  nghttp2 OK")
    return True


def build_nghttp3(env):
    """Build nghttp3 - ref: win_build/build_nghttp3.bat"""
    print("\n=== Building nghttp3 ===")
    if os.path.exists(os.path.join(NGHTTP3_INST, "lib", "nghttp3.lib")):
        print("  nghttp3 already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "nghttp3")
    
    if not cmake_configure(NGHTTP3_SRC, bdir, NGHTTP3_INST,
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG" '
        '-DENABLE_LIB_ONLY=ON '
        '-DENABLE_SHARED_LIB=OFF '
        '-DENABLE_STATIC_LIB=ON '
        '-DNGHTTP3_ENABLE_DOC=OFF', env):
        return False
    if not cmake_build(bdir, env):
        return False
    if not cmake_install(bdir, env):
        return False
    print("  nghttp3 OK")
    return True


def build_boringssl(env):
    """Build BoringSSL - ref: win_build/build_boringssl.bat"""
    print("\n=== Building BoringSSL ===")
    if os.path.exists(os.path.join(BORINGSSL_INST, "lib", "libssl.lib")):
        print("  BoringSSL already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "boringssl")
    nasm_exe = env.get('NASM_EXE', '')
    
    cmake_args = (
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG /D_CRT_NONSTDC_NO_DEPRECATE /D_CRT_SECURE_NO_WARNINGS /wd4996" '
        '-DCMAKE_CXX_FLAGS="/MT /O2 /DNDEBUG /EHsc /D_CRT_NONSTDC_NO_DEPRECATE /D_CRT_SECURE_NO_WARNINGS /wd4996" '
        ''
        '-DCMAKE_POSITION_INDEPENDENT_CODE=ON '
        '-DBUILD_TESTING=OFF '
        '-DBENCHMARK_ENABLE_TESTING=OFF'
    )
    if nasm_exe:
        cmake_args += f' -DCMAKE_ASM_NASM_COMPILER="{nasm_exe}"'
    
    if not cmake_configure(BORINGSSL_SRC, bdir, BORINGSSL_INST, cmake_args, env):
        return False
    if not cmake_build(bdir, env, timeout=1800):
        return False
    
    # Fix directory structure for curl compatibility (like build_boringssl.bat)
    # Copy libs to lib/ with libssl.lib / libcrypto.lib names
    build_lib = os.path.join(bdir, "lib")
    os.makedirs(build_lib, exist_ok=True)
    
    # Find and copy ssl.lib → libssl.lib
    ssl_found = False
    for src_name, dst_name in [
        (os.path.join(bdir, "ssl", "ssl.lib"), "libssl.lib"),
        (os.path.join(bdir, "ssl", "ssl_static.lib"), "libssl.lib"),
        (os.path.join(bdir, "ssl.lib"), "libssl.lib"),
    ]:
        if os.path.exists(src_name):
            shutil.copy2(src_name, os.path.join(build_lib, dst_name))
            ssl_found = True
            print(f"  Copied {src_name} → {build_lib}\\{dst_name}")
            break
    
    # Find and copy crypto.lib → libcrypto.lib
    crypto_found = False
    for src_name, dst_name in [
        (os.path.join(bdir, "crypto", "crypto.lib"), "libcrypto.lib"),
        (os.path.join(bdir, "crypto", "crypto_static.lib"), "libcrypto.lib"),
        (os.path.join(bdir, "crypto.lib"), "libcrypto.lib"),
    ]:
        if os.path.exists(src_name):
            shutil.copy2(src_name, os.path.join(build_lib, dst_name))
            crypto_found = True
            print(f"  Copied {src_name} → {build_lib}\\{dst_name}")
            break
    
    if not ssl_found or not crypto_found:
        print(f"  ERROR: BoringSSL libs not found! ssl={ssl_found}, crypto={crypto_found}")
        # Search for all .lib files
        for root, dirs, files in os.walk(bdir):
            for f in files:
                if f.endswith('.lib'):
                    print(f"    Found: {os.path.join(root, f)}")
        return False
    
    # Copy include directory
    src_inc = os.path.join(BORINGSSL_SRC, "include")
    build_inc = os.path.join(bdir, "include")
    if not os.path.exists(build_inc) and os.path.exists(src_inc):
        shutil.copytree(src_inc, build_inc)
    
    # Install to install directory
    inst_lib = os.path.join(BORINGSSL_INST, "lib")
    inst_inc = os.path.join(BORINGSSL_INST, "include")
    os.makedirs(inst_lib, exist_ok=True)
    os.makedirs(inst_inc, exist_ok=True)
    
    # Copy libs
    for f in os.listdir(build_lib):
        if f.endswith('.lib'):
            shutil.copy2(os.path.join(build_lib, f), inst_lib)
    
    # Copy includes
    if os.path.exists(build_inc):
        if os.path.exists(inst_inc):
            shutil.rmtree(inst_inc)
        shutil.copytree(build_inc, inst_inc)
    elif os.path.exists(src_inc):
        if os.path.exists(inst_inc):
            shutil.rmtree(inst_inc)
        shutil.copytree(src_inc, inst_inc)
    
    # Create opensslconf.h stub (BoringSSL doesn't provide this)
    conf_h = os.path.join(inst_inc, "openssl", "opensslconf.h")
    if not os.path.exists(conf_h):
        os.makedirs(os.path.dirname(conf_h), exist_ok=True)
        with open(conf_h, 'w') as f:
            f.write("/* opensslconf.h - Stub for BoringSSL compatibility */\n")
            f.write("#ifndef OPENSSL_OPENSSLCONF_H\n")
            f.write("#define OPENSSL_OPENSSLCONF_H\n")
            f.write("#endif\n")
        print("  Created opensslconf.h stub")
    
    # Create ocsp.h stub if available
    ocsp_stub = os.path.join(WIN_BUILD, "patches", "boringssl-ocsp-stub.h")
    ocsp_h = os.path.join(inst_inc, "openssl", "ocsp.h")
    if not os.path.exists(ocsp_h) and os.path.exists(ocsp_stub):
        shutil.copy2(ocsp_stub, ocsp_h)
        print("  Copied ocsp.h stub")
    
    # Verify
    if os.path.exists(os.path.join(inst_lib, "libssl.lib")):
        print("  BoringSSL OK")
        return True
    else:
        print("  ERROR: libssl.lib not in install dir!")
        return False


def build_ngtcp2(env):
    """Build ngtcp2 - ref: win_build/build_ngtcp2.bat"""
    print("\n=== Building ngtcp2 ===")
    if os.path.exists(os.path.join(NGTCP2_INST, "lib", "ngtcp2.lib")):
        print("  ngtcp2 already installed, skipping.")
        return True
    bdir = os.path.join(BUILD_DIR, "ngtcp2")
    
    # Fix BoringSSL opensslv.h for CMake FindOpenSSL compatibility
    opensslv_h = os.path.join(BORINGSSL_INST, "include", "openssl", "opensslv.h")
    if not os.path.exists(opensslv_h):
        # Create stub
        os.makedirs(os.path.dirname(opensslv_h), exist_ok=True)
        with open(opensslv_h, 'w') as f:
            f.write("/* opensslv.h - Stub for BoringSSL */\n")
            f.write("#ifndef OPENSSL_OPENSSLV_H\n")
            f.write("#define OPENSSL_OPENSSLV_H\n")
            f.write('#define OPENSSL_VERSION_TEXT "BoringSSL"\n')
            f.write('#define OPENSSL_VERSION_NUMBER 0x10101000L\n')
            f.write("#endif\n")
        print("  Created opensslv.h stub for ngtcp2")
    
    cmake_args = (
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG" '
        '-DCMAKE_CXX_FLAGS="/MT /O2 /DNDEBUG /EHsc" '
        '-DCMAKE_POSITION_INDEPENDENT_CODE=ON '
        '-DENABLE_LIB_ONLY=ON '
        '-DENABLE_STATIC_LIB=ON '
        '-DENABLE_SHARED_LIB=OFF '
        '-DENABLE_EXAMPLES=OFF '
        '-DENABLE_TESTS=OFF '
        '-DENABLE_OPENSSL=OFF '
        '-DENABLE_BORINGSSL=ON '
        f'-DHAVE_BORINGSSL=TRUE '
        f'-DBORINGSSL_INCLUDE_DIR="{BORINGSSL_INST}\\include" '
        f'-DBORINGSSL_LIBRARIES="{BORINGSSL_INST}\\lib\\libssl.lib;{BORINGSSL_INST}\\lib\\libcrypto.lib" '
        f'-DOPENSSL_ROOT_DIR="{BORINGSSL_INST}" '
        f'-DOPENSSL_INCLUDE_DIR="{BORINGSSL_INST}\\include" '
        f'-DOPENSSL_LIBRARIES="{BORINGSSL_INST}\\lib\\libssl.lib;{BORINGSSL_INST}\\lib\\libcrypto.lib" '
        f'-DOPENSSL_CRYPTO_LIBRARY="{BORINGSSL_INST}\\lib\\libcrypto.lib" '
        f'-DOPENSSL_SSL_LIBRARY="{BORINGSSL_INST}\\lib\\libssl.lib" '
        f'-DOPENSSL_FOUND=TRUE '
        f'-DOPENSSL_VERSION="3.0.0" '
        f'-DCMAKE_PREFIX_PATH="{BORINGSSL_INST};{NGHTTP3_INST}"'
    )
    
    if not cmake_configure(NGTCP2_SRC, bdir, NGTCP2_INST, cmake_args, env):
        return False
    if not cmake_build(bdir, env):
        return False
    if not cmake_install(bdir, env):
        return False
    print("  ngtcp2 OK")
    return True


def apply_curl_patches(env):
    """Apply patches to curl source - ref: build_curl_lib.bat steps 3-6"""
    print("\n=== Applying curl patches ===")
    git_exe = env.get('GIT_EXE', 'git')
    
    # Check if already patched
    if os.path.exists(os.path.join(CURL_SRC, ".patched")):
        print("  Already patched, skipping.")
        return True
    
    # Step 3a: Copy cJSON and impersonate_register source files
    for fname in ['cJSON.h', 'cJSON.c', 'impersonate_register.h', 'impersonate_register.c']:
        src = os.path.join(PATCHES_DIR, fname)
        dst = os.path.join(CURL_SRC, "lib", fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  Copied {fname}")
        elif os.path.exists(dst):
            print(f"  {fname} already exists in lib/")
        else:
            print(f"  WARN: {fname} not found in patches/ or lib/")
    
    # Step 3b: Add cJSON and impersonate_register to Makefile.inc
    makefile_inc = os.path.join(CURL_SRC, "lib", "Makefile.inc")
    if os.path.exists(makefile_inc):
        with open(makefile_inc, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'impersonate_register.c' not in content:
            content = content.replace(' impersonate.c', ' impersonate.c impersonate_register.c cJSON.c')
            content = content.replace(' impersonate.h', ' impersonate.h impersonate_register.h cJSON.h')
            with open(makefile_inc, 'w', encoding='utf-8') as f:
                f.write(content)
            print("  Updated Makefile.inc")
    
    # Step 3c: Apply custom impersonate_register patches
    apply_script = os.path.join(PATCHES_DIR, "apply_custom_impersonate.py")
    if os.path.exists(apply_script):
        print("  Running apply_custom_impersonate.py...")
        run(f'python "{apply_script}" "{CURL_SRC}"', env=env)
    
    # Step 3d: Ensure output name is libcurl-impersonate
    for cmake_file, old, new in [
        (os.path.join(CURL_SRC, "lib", "CMakeLists.txt"),
         'set(LIBCURL_OUTPUT_NAME libcurl CACHE',
         'set(LIBCURL_OUTPUT_NAME libcurl-impersonate CACHE'),
        (os.path.join(CURL_SRC, "src", "CMakeLists.txt"),
         'set(EXE_NAME curl)',
         'set(EXE_NAME curl-impersonate)'),
    ]:
        if os.path.exists(cmake_file):
            with open(cmake_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if new not in content and old in content:
                content = content.replace(old, new)
                with open(cmake_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  Fixed output name in {os.path.basename(cmake_file)}")
    
    # Step 4: Fix VLA issue for MSVC
    fix_vla = os.path.join(WIN_BUILD, "fix_vla.py")
    if os.path.exists(fix_vla):
        print("  Running fix_vla.py...")
        run(f'python "{fix_vla}"', cwd=CURL_SRC, env=env)
    
    # Step 5: Fix BoringSSL detection in CMakeLists.txt
    patch_boringssl_def = os.path.join(WIN_BUILD, "patch_boringssl_def.py")
    cmakelists = os.path.join(CURL_SRC, "lib", "CMakeLists.txt")
    if os.path.exists(patch_boringssl_def) and os.path.exists(cmakelists):
        print("  Running patch_boringssl_def.py...")
        run(f'python "{patch_boringssl_def}" "{cmakelists}"', env=env)
    
    # Step 6: Patch CMakeLists.txt for DLL export
    patch_cmake_dll = os.path.join(WIN_BUILD, "patch_cmake_dll.py")
    if os.path.exists(patch_cmake_dll) and os.path.exists(cmakelists):
        print("  Running patch_cmake_dll.py...")
        run(f'python "{patch_cmake_dll}" "{cmakelists}"', env=env)
    
    # Mark as patched
    with open(os.path.join(CURL_SRC, ".patched"), 'w') as f:
        f.write("patched\n")
    
    print("  Patches applied.")
    return True


def build_curl_lib(env):
    """Build curl-impersonate static lib - ref: build_curl_lib.bat"""
    print("\n=== Building curl-impersonate static lib ===")
    bdir = os.path.join(BUILD_DIR, "curl")
    
    cmake_args = (
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB /DCURL_STATICLIB" '
        '-DCMAKE_CXX_FLAGS="/MT /O2 /DNDEBUG /EHsc /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB /DCURL_STATICLIB" '
        ''
        '-DBUILD_SHARED_LIBS=OFF '
        '-DBUILD_STATIC_LIBS=ON '
        '-DCURL_USE_OPENSSL=ON '
        '-DHAVE_BORINGSSL=ON '
        f'-DOPENSSL_ROOT_DIR="{BORINGSSL_INST}" '
        f'-DOPENSSL_INCLUDE_DIR="{BORINGSSL_INST}\\include" '
        f'-DOPENSSL_LIBRARIES="{BORINGSSL_INST}\\lib\\libssl.lib;{BORINGSSL_INST}\\lib\\libcrypto.lib" '
        '-DCURL_BROTLI=ON '
        f'-DBROTLI_INCLUDE_DIR="{BROTLI_INST}\\include" '
        f'-DBROTLIDEC_LIBRARY="{BROTLI_INST}\\lib\\brotlidec.lib" '
        f'-DBROTLIENC_LIBRARY="{BROTLI_INST}\\lib\\brotlienc.lib" '
        f'-DBROTLICOMMON_LIBRARY="{BROTLI_INST}\\lib\\brotlicommon.lib" '
        '-DUSE_NGHTTP2=ON '
        f'-DNGHTTP2_INCLUDE_DIR="{NGHTTP2_INST}\\include" '
        f'-DNGHTTP2_LIBRARY="{NGHTTP2_INST}\\lib\\nghttp2.lib" '
        f'-DNGHTTP2_ROOT="{NGHTTP2_INST}" '
        '-DUSE_NGTCP2=ON '
        f'-DNGTCP2_INCLUDE_DIR="{NGTCP2_INST}\\include" '
        f'-DNGTCP2_LIBRARY="{NGTCP2_INST}\\lib\\ngtcp2.lib" '
        f'-DNGTCP2_CRYPTO_LIBRARY="{NGTCP2_INST}\\lib\\ngtcp2_crypto_boringssl.lib" '
        '-DUSE_NGHTTP3=ON '
        f'-DNGHTTP3_INCLUDE_DIR="{NGHTTP3_INST}\\include" '
        f'-DNGHTTP3_LIBRARY="{NGHTTP3_INST}\\lib\\nghttp3.lib" '
        f'-DZLIB_INCLUDE_DIR="{ZLIB_INST}\\include" '
        f'-DZLIB_LIBRARY="{ZLIB_INST}\\lib\\zlibstatic.lib" '
        f'-DZLIB_ROOT="{ZLIB_INST}" '
        '-DCURL_ZSTD=ON '
        f'-DZSTD_INCLUDE_DIR="{ZSTD_INST}\\include" '
        f'-DZSTD_LIBRARY="{ZSTD_INST}\\lib\\zstd_static.lib" '
        f'-DZSTD_ROOT="{ZSTD_INST}" '
        '-DHTTP_ONLY=OFF '
        '-DENABLE_WEBSOCKETS=ON '
        '-DUSE_LIBIDN2=OFF '
        '-DCURL_USE_LIBPSL=OFF '
        '-DUSE_QUICHE=OFF '
        '-DENABLE_MANUAL=OFF '
        '-DCURL_USE_LIBSSH2=OFF '
        '-DCURL_USE_GSSAPI=OFF '
        '-DBUILD_CURL_EXE=OFF'
    )
    
    # Clear CMake cache if it exists (to ensure new options take effect)
    cache_file = os.path.join(bdir, "CMakeCache.txt")
    if os.path.exists(cache_file):
        print("  Clearing CMake cache...")
        os.remove(cache_file)
    
    if not cmake_configure(CURL_SRC, bdir, CURL_INST, cmake_args, env):
        return False
    if not cmake_build(bdir, env, timeout=1800):
        return False
    if not cmake_install(bdir, env):
        return False
    
    # Find the static lib
    static_lib = None
    for path in [
        os.path.join(bdir, "lib", "libcurl-impersonate.lib"),
        os.path.join(bdir, "lib", "Release", "libcurl-impersonate.lib"),
    ]:
        if os.path.exists(path):
            static_lib = path
            break
    
    if not static_lib:
        # Search
        for root, dirs, files in os.walk(bdir):
            for f in files:
                if 'libcurl-impersonate' in f and f.endswith('.lib'):
                    static_lib = os.path.join(root, f)
                    break
    
    if static_lib:
        print(f"  Static lib: {static_lib}")
        
        # Merge static libs (like build_curl_lib.bat Step 11)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        merged_lib = os.path.join(OUTPUT_DIR, "libcurl-impersonate.lib")
        
        merge_libs = [
            static_lib,
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
        
        # Only include libs that exist
        all_merge_libs = merge_libs  # save original for comparison
        merge_libs = [l for l in merge_libs if os.path.exists(l)]
        if len(merge_libs) < len(all_merge_libs):
            missing = [l for l in all_merge_libs if not os.path.exists(l)]
            print(f"  WARN: Missing merge libs: {missing}")
        
        print(f"  Merging {len(merge_libs)} static libs into {merged_lib}...")
        lib_cmd = 'lib.exe /OUT:"' + merged_lib + '" ' + ' '.join(f'"{l}"' for l in merge_libs)
        if run(lib_cmd, env=env):
            merged_sz = os.path.getsize(merged_lib)
            print(f"  Merged lib: {merged_lib} ({merged_sz:,} bytes)")
            if merged_sz < os.path.getsize(static_lib):
                print("  WARN: Merged lib is smaller than curl-only lib, merge may have failed!")
        else:
            print("  WARN: lib.exe merge failed, copying static lib instead")
            shutil.copy2(static_lib, merged_lib)
        
        # Copy headers
        out_inc = os.path.join(OUTPUT_DIR, "include")
        curl_inc = os.path.join(CURL_INST, "include", "curl")
        if os.path.exists(curl_inc):
            dst = os.path.join(out_inc, "curl")
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(curl_inc, dst)
        
        print("  curl-impersonate static lib OK")
        return True
    else:
        print("  ERROR: static lib not found after build!")
        return False


def build_curl_dll(env):
    """Build curl-impersonate DLL - ref: build_curl_dll.bat"""
    print("\n=== Building curl-impersonate DLL ===")
    
    # Re-configure for DLL build (need BUILD_SHARED_LIBS=ON)
    bdir = os.path.join(BUILD_DIR, "curl-dll")
    
    # Copy .def file if available
    def_src = os.path.join(WIN_BUILD, "libcurl-impersonate.def")
    def_dst = os.path.join(CURL_SRC, "lib", "libcurl-impersonate.def")
    if os.path.exists(def_src):
        shutil.copy2(def_src, def_dst)
    
    # Generate .def file
    gen_def = os.path.join(WIN_BUILD, "generate_def_file.py")
    if os.path.exists(gen_def):
        print("  Generating .def file...")
        cmd = (f'python "{gen_def}" '
               f'--curl-include "{CURL_SRC}\\include" '
               f'--boringssl-lib-dir "{BORINGSSL_INST}\\lib" '
               f'--zlib-def "{ZLIB_SRC}\\win32\\zlib.def" '
               f'--brotli-lib-dir "{BROTLI_INST}\\lib" '
               f'--nghttp2-lib-dir "{NGHTTP2_INST}\\lib" '
               f'--output "{def_dst}" '
               f'--dll-name libcurl-impersonate')
        run(cmd, env=env)
    
    cmake_args = (
        '-DCMAKE_C_FLAGS="/MT /O2 /DNDEBUG /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB" '
        '-DCMAKE_CXX_FLAGS="/MT /O2 /DNDEBUG /EHsc /DNGHTTP2_STATICLIB /DNGTCP2_STATICLIB /DNGHTTP3_STATICLIB" '
        ''
        '-DBUILD_SHARED_LIBS=ON '
        '-DBUILD_STATIC_LIBS=OFF '
        '-DCURL_USE_OPENSSL=ON '
        '-DHAVE_BORINGSSL=ON '
        f'-DOPENSSL_ROOT_DIR="{BORINGSSL_INST}" '
        f'-DOPENSSL_INCLUDE_DIR="{BORINGSSL_INST}\\include" '
        f'-DOPENSSL_LIBRARIES="{BORINGSSL_INST}\\lib\\libssl.lib;{BORINGSSL_INST}\\lib\\libcrypto.lib" '
        '-DCURL_BROTLI=ON '
        f'-DBROTLI_INCLUDE_DIR="{BROTLI_INST}\\include" '
        f'-DBROTLIDEC_LIBRARY="{BROTLI_INST}\\lib\\brotlidec.lib" '
        f'-DBROTLIENC_LIBRARY="{BROTLI_INST}\\lib\\brotlienc.lib" '
        f'-DBROTLICOMMON_LIBRARY="{BROTLI_INST}\\lib\\brotlicommon.lib" '
        '-DUSE_NGHTTP2=ON '
        f'-DNGHTTP2_INCLUDE_DIR="{NGHTTP2_INST}\\include" '
        f'-DNGHTTP2_LIBRARY="{NGHTTP2_INST}\\lib\\nghttp2.lib" '
        f'-DNGHTTP2_ROOT="{NGHTTP2_INST}" '
        '-DUSE_NGTCP2=ON '
        f'-DNGTCP2_INCLUDE_DIR="{NGTCP2_INST}\\include" '
        f'-DNGTCP2_LIBRARY="{NGTCP2_INST}\\lib\\ngtcp2.lib" '
        f'-DNGTCP2_CRYPTO_BORINGSSL_LIBRARY="{NGTCP2_INST}\\lib\\ngtcp2_crypto_boringssl.lib" '
        '-DUSE_NGHTTP3=ON '
        f'-DNGHTTP3_INCLUDE_DIR="{NGHTTP3_INST}\\include" '
        f'-DNGHTTP3_LIBRARY="{NGHTTP3_INST}\\lib\\nghttp3.lib" '
        f'-DZLIB_INCLUDE_DIR="{ZLIB_INST}\\include" '
        f'-DZLIB_LIBRARY="{ZLIB_INST}\\lib\\zlibstatic.lib" '
        f'-DZLIB_ROOT="{ZLIB_INST}" '
        '-DCURL_ZSTD=ON '
        f'-DZSTD_INCLUDE_DIR="{ZSTD_INST}\\include" '
        f'-DZSTD_LIBRARY="{ZSTD_INST}\\lib\\zstd_static.lib" '
        f'-DZSTD_ROOT="{ZSTD_INST}" '
        '-DHTTP_ONLY=OFF '
        '-DENABLE_WEBSOCKETS=ON '
        '-DUSE_LIBIDN2=OFF '
        '-DCURL_USE_LIBPSL=OFF '
        '-DUSE_QUICHE=OFF '
        '-DENABLE_MANUAL=OFF '
        '-DCURL_USE_LIBSSH2=OFF '
        '-DCURL_USE_GSSAPI=OFF '
        '-DBUILD_CURL_EXE=OFF '
        '-DCURL_HIDDEN_SYMBOLS=OFF '
        '-DCURL_STATIC_CRT=ON '
        '-DCMAKE_POLICY_DEFAULT_CMP0156=NEW'
    )
    
    # Clear CMake cache if it exists (to ensure new options take effect)
    cache_file = os.path.join(bdir, "CMakeCache.txt")
    if os.path.exists(cache_file):
        print("  Clearing CMake cache...")
        os.remove(cache_file)
    
    if not cmake_configure(CURL_SRC, bdir, CURL_INST, cmake_args, env):
        return False
    if not cmake_build(bdir, env, timeout=1800):
        return False
    
    # Find DLL
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
        shutil.copy2(dll_path, os.path.join(OUTPUT_DIR, "libcurl-impersonate.dll"))
        
        # Copy import lib
        lib_name = os.path.splitext(os.path.basename(dll_path))[0] + '.lib'
        import_lib = os.path.join(os.path.dirname(dll_path), lib_name)
        if os.path.exists(import_lib):
            shutil.copy2(import_lib, os.path.join(OUTPUT_DIR, "libcurl-impersonate.lib"))
        
        print(f"  DLL: {dll_path}")
        print("  curl-impersonate DLL OK")
        return True
    else:
        print("  WARN: DLL not found (may be OK if static lib is sufficient)")
        return True  # Non-fatal


def verify_build(env):
    """Verify final build artifacts"""
    print("\n=== Verifying build ===")
    artifacts = []
    
    # Check static lib
    static_lib = os.path.join(OUTPUT_DIR, "libcurl-impersonate.lib")
    if os.path.exists(static_lib):
        sz = os.path.getsize(static_lib)
        print(f"  Static lib: {static_lib} ({sz:,} bytes)")
        artifacts.append(static_lib)
    
    # Check DLL
    dll = os.path.join(OUTPUT_DIR, "libcurl-impersonate.dll")
    if os.path.exists(dll):
        sz = os.path.getsize(dll)
        print(f"  DLL: {dll} ({sz:,} bytes)")
        artifacts.append(dll)
    
    # Check exe
    exe = os.path.join(OUTPUT_DIR, "curl-impersonate.exe")
    if not os.path.exists(exe):
        # Search build dir
        for root, dirs, files in os.walk(os.path.join(BUILD_DIR, "curl")):
            for f in files:
                if f == 'curl-impersonate.exe':
                    exe = os.path.join(root, f)
                    break
    
    if os.path.exists(exe):
        sz = os.path.getsize(exe)
        print(f"  EXE: {exe} ({sz:,} bytes)")
        # Copy to output
        shutil.copy2(exe, os.path.join(OUTPUT_DIR, "curl-impersonate.exe"))
        artifacts.append(os.path.join(OUTPUT_DIR, "curl-impersonate.exe"))
        
        # Test
        print("\n  Testing curl-impersonate.exe -V ...")
        r = subprocess.run([os.path.join(OUTPUT_DIR, "curl-impersonate.exe"), "-V"],
                          capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=env, timeout=10)
        if r.returncode == 0:
            print(f"  Output: {r.stdout[:500]}")
        else:
            print(f"  Error: {r.stderr[:300]}")
    
    # List all output files
    print("\n  All output files:")
    if os.path.exists(OUTPUT_DIR):
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for f in files:
                fp = os.path.join(root, f)
                sz = os.path.getsize(fp)
                rel = os.path.relpath(fp, OUTPUT_DIR)
                print(f"    {rel} ({sz:,} bytes)")
    
    return len(artifacts) > 0


def main():
    print("=" * 60)
    print("  curl-impersonate Windows Build")
    print("  (from existing patched source)")
    print("=" * 60)
    
    # Step 1: Setup MSVC environment
    print("\n[1/10] Setting up MSVC environment...")
    env = setup_msvc_env("x64")
    if not env:
        print("FATAL: Could not setup MSVC environment")
        sys.exit(1)
    
    # Step 2: Detect tools
    print("\n[2/10] Detecting build tools...")
    tools = detect_tools(env)
    
    # Create directories
    for d in [BUILD_DIR, INSTALL_DIR, OUTPUT_DIR]:
        os.makedirs(d, exist_ok=True)
    
    # Verify source directories exist
    for name, path in [
        ("zlib", ZLIB_SRC), ("zstd", ZSTD_SRC), ("brotli", BROTLI_SRC),
        ("nghttp2", NGHTTP2_SRC), ("nghttp3", NGHTTP3_SRC),
        ("BoringSSL", BORINGSSL_SRC), ("ngtcp2", NGTCP2_SRC),
        ("curl", CURL_SRC),
    ]:
        if not os.path.exists(path):
            print(f"FATAL: Source directory missing: {name} at {path}")
            sys.exit(1)
    
    # Build dependencies
    steps = [
        ("zlib", build_zlib),
        ("zstd", build_zstd),
        ("brotli", build_brotli),
        ("nghttp2", build_nghttp2),
        ("nghttp3", build_nghttp3),
        ("BoringSSL", build_boringssl),
        ("ngtcp2", build_ngtcp2),
    ]
    
    for i, (name, builder) in enumerate(steps, 3):
        print(f"\n[{i}/10] Building {name}...")
        if not builder(env):
            print(f"FATAL: {name} build failed!")
            sys.exit(1)
    
    # Apply curl patches
    print(f"\n[{len(steps)+3}/10] Applying curl patches...")
    if not apply_curl_patches(env):
        print("FATAL: curl patching failed!")
        sys.exit(1)
    
    # Build curl
    print(f"\n[{len(steps)+4}/10] Building curl-impersonate...")
    if not build_curl_lib(env):
        print("FATAL: curl-impersonate static lib build failed!")
        sys.exit(1)
    
    # Build DLL (non-fatal)
    print(f"\n[{len(steps)+5}/10] Building curl-impersonate DLL...")
    build_curl_dll(env)
    
    # Verify
    print(f"\n[{len(steps)+6}/10] Verifying build...")
    if verify_build(env):
        print("\n" + "=" * 60)
        print("  BUILD COMPLETE!")
        print("=" * 60)
    else:
        print("\n  BUILD PARTIALLY COMPLETE (no artifacts found)")


if __name__ == "__main__":
    main()

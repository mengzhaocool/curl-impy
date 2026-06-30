import sys
sys.path.insert(0, r'd:\curl-impersonate-8.20.0')
try:
    from _build_all import setup_msvc_env, find_vs
    vs_path, vcvarsall = find_vs('2022')
    print(f"VS: {vs_path}")
    print(f"vcvarsall: {vcvarsall}")
    env = setup_msvc_env('x64', vcvarsall)
    print(f"OK, env keys: {len(env)}")
    print(f"CMAKE: {env.get('CMAKE_EXE','')}")
    print(f"NINJA: {env.get('NINJA_EXE','')}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

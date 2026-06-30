import shutil, os
deps = r'd:\curl-impersonate-8.20.0\deps'
# Directories that have .git but no real source (incomplete extraction)
incomplete = []
for d in sorted(os.listdir(deps)):
    p = os.path.join(deps, d)
    if not os.path.isdir(p):
        continue
    files = os.listdir(p)
    # If only .git exists, or .git + very few files, it's incomplete
    non_git = [f for f in files if f != '.git']
    if len(non_git) < 5:  # A real source tree has many files
        incomplete.append(d)
        shutil.rmtree(p, True)
        print(f'Removed incomplete: {d} (had {len(non_git)} non-git items)')
    
# Also remove marker files
for f in ['.sources_downloaded', '.all_patched']:
    p = os.path.join(deps, f)
    if os.path.exists(p):
        os.remove(p)
        print(f'Removed marker: {f}')
print('Done')

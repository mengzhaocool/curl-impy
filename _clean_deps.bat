@echo off
cd /d d:\curl-impersonate-8.20.0\deps
for /d %d in (*) do (
    rmdir /s /q "%d" 2>nul
    echo Removed %d
)
del .sources_downloaded 2>nul
del .all_patched 2>nul
echo Done

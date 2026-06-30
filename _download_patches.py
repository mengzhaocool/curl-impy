# Download lexiforest patch files for reference during manual modifications
import subprocess, os

CURL_BAT = r"C:\Users\hmz\bin\curl.bat"
PATCHES_DIR = r"d:\curl-impersonate-8.20.0\patches"
os.makedirs(PATCHES_DIR, exist_ok=True)

patches = [
    ("boringssl.patch", "https://ghfast.top/https://raw.githubusercontent.com/lexiforest/curl-impersonate/refs/heads/main/patches/boringssl.patch"),
    ("ngtcp2.patch", "https://ghfast.top/https://raw.githubusercontent.com/lexiforest/curl-impersonate/refs/heads/main/patches/ngtcp2.patch"),
    ("nghttp3.patch", "https://ghfast.top/https://raw.githubusercontent.com/lexiforest/curl-impersonate/refs/heads/main/patches/nghttp3.patch"),
    ("brotli.patch", "https://ghfast.top/https://raw.githubusercontent.com/lexiforest/curl-impersonate/refs/heads/main/patches/brotli.patch"),
    ("curl.patch", "https://ghfast.top/https://raw.githubusercontent.com/lexiforest/curl-impersonate/refs/heads/main/patches/curl.patch"),
]

for name, url in patches:
    out = os.path.join(PATCHES_DIR, name)
    if os.path.exists(out) and os.path.getsize(out) > 100:
        print(f"[EXISTS] {name} ({os.path.getsize(out):,} bytes)")
        continue
    print(f"[DOWNLOAD] {name}...")
    r = subprocess.run(
        ["cmd", "/c", CURL_BAT, "-L", "-o", out, url],
        timeout=120
    )
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100:
        print(f"  OK ({os.path.getsize(out):,} bytes)")
    else:
        print(f"  FAILED, trying direct URL...")
        url_direct = url.replace("https://ghfast.top/https://", "https://")
        r = subprocess.run(["cmd", "/c", CURL_BAT, "-L", "-o", out, url_direct], timeout=120)
        if r.returncode == 0 and os.path.getsize(out) > 100:
            print(f"  OK direct ({os.path.getsize(out):,} bytes)")
        else:
            print(f"  FAILED!")

print("\nDone!")

import platform
import sys

import curl_impy


def print_doctor() -> None:
    print("curl-impy doctor")
    print("----------------")
    print(f"python: {sys.version.split()[0]}")
    print(f"executable: {sys.executable}")
    print(f"platform: {platform.platform()}")
    print(f"machine: {platform.machine()}")
    print(f"curl_impy: {curl_impy.__version__}")
    print(f"libcurl: {curl_impy.__curl_version__}")
    print(f"impersonate_targets: {len(curl_impy.impersonate_list())}")

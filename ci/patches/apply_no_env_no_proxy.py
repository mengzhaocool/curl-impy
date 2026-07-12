#!/usr/bin/env python3
"""
apply_no_env_no_proxy.py - Post-patch for curl-impersonate

Removes environment variable based features that should not be in the DLL:
1. CURL_IMPERSONATE env var blocks in easy.c (curl_easy_init + curl_easy_reset)
2. env_target/env_headers variable declarations in easy.c
3. Environment proxy detection in url.c (detect_proxy function)
4. NO_PROXY env var reading in url.c

This script should be run AFTER applying curl-impersonate-8.20.0.patch
and INSTEAD OF apply_xweb_default.py.

Usage: python apply_no_env_no_proxy.py <curl_src_dir>
"""
import sys
import os
import re

def patch_easy_c(easy_c_path):
    """Remove CURL_IMPERSONATE env var blocks from easy.c"""
    with open(easy_c_path, 'r', encoding='utf-8') as f:
        content = f.read()

    changed = False

    # 1. Remove env_target/env_headers variable declarations
    pattern_decl = r'  char \*env_target; /\* curl-impersonate \*/\n  char \*env_headers; /\* curl-impersonate \*/\n'
    if re.search(pattern_decl, content):
        content = re.sub(pattern_decl, '', content)
        print('[OK] Removed env_target/env_headers declarations')
        changed = True
    else:
        print('[SKIP] env_target/env_headers declarations not found (may already be removed)')

    # 2. Remove CURL_IMPERSONATE block in curl_easy_init
    # Pattern: the comment block + env_target = curl_getenv("CURL_IMPERSONATE") ... }
    pattern_init = r'''  /\*
   \* curl-impersonate: Hook into curl_easy_init\(\) to set the required options
   \* from an environment variable\.
   \*/
  env_target = curl_getenv\("CURL_IMPERSONATE"\);
  if\(env_target\) \{
    env_headers = curl_getenv\("CURL_IMPERSONATE_HEADERS"\);
    if\(env_headers\) \{
      result = curl_easy_impersonate\(data, env_target,
                                     !strcasecompare\(env_headers, "no"\)\);
      curl_free\(env_headers\);
    \} else \{
      result = curl_easy_impersonate\(data, env_target, true\);
    \}
    curl_free\(env_target\);
    if\(result\) \{
      Curl_close\(&data\);
      return NULL;
    \}
  \}'''

    if re.search(pattern_init, content):
        content = re.sub(pattern_init, '', content)
        print('[OK] Removed CURL_IMPERSONATE block from curl_easy_init')
        changed = True
    else:
        # Try flexible pattern
        pattern_init_flex = r'  /\*\s*\n   \* curl-impersonate: Hook into curl_easy_init.*?env_target = curl_getenv.*?\n  if\(env_target\).*?return NULL;\s*\n    \}\n  \}'
        if re.search(pattern_init_flex, content, re.DOTALL):
            content = re.sub(pattern_init_flex, '', content, flags=re.DOTALL)
            print('[OK] Removed CURL_IMPERSONATE block from curl_easy_init (flexible)')
            changed = True
        else:
            print('[SKIP] CURL_IMPERSONATE block in curl_easy_init not found')

    # 3. Remove CURL_IMPERSONATE block in curl_easy_reset
    pattern_reset = r'''  /\*
   \* curl-impersonate: Hook into curl_easy_reset\(\) to set the required options
   \* from an environment variable, just like in curl_easy_init\(\)\.
   \*/
  \{
    char \*env_target = curl_getenv\("CURL_IMPERSONATE"\);
    if\(env_target\) \{
      char \*env_headers = curl_getenv\("CURL_IMPERSONATE_HEADERS"\);
      if\(env_headers\) \{
        curl_easy_impersonate\(data, env_target,
                              !strcasecompare\(env_headers, "no"\)\);
        curl_free\(env_headers\);
      \} else \{
        curl_easy_impersonate\(data, env_target, true\);
      \}
      curl_free\(env_target\);
    \}
  \}'''

    if re.search(pattern_reset, content):
        content = re.sub(pattern_reset, '', content)
        print('[OK] Removed CURL_IMPERSONATE block from curl_easy_reset')
        changed = True
    else:
        pattern_reset_flex = r'  /\*\s*\n   \* curl-impersonate: Hook into curl_easy_reset.*?\n   \*/\n  \{[^}]*curl_getenv.*?\n  \}'
        if re.search(pattern_reset_flex, content, re.DOTALL):
            content = re.sub(pattern_reset_flex, '', content, flags=re.DOTALL)
            print('[OK] Removed CURL_IMPERSONATE block from curl_easy_reset (flexible)')
            changed = True
        else:
            print('[SKIP] CURL_IMPERSONATE block in curl_easy_reset not found')

    # 4. Remove any XWEB_AUTO_IMPERSONATE code if present
    if 'XWEB_AUTO_IMPERSONATE' in content:
        # Remove xweb registration in curl_global_init
        content = re.sub(
            r'  /\* XWEB_AUTO_IMPERSONATE:.*?\*/\s*\n\s*if\(result == CURLE_OK\) \{.*?curl_easy_impersonate_register\("xweb", xweb_json\);\s*\n\s*\}\s*\n',
            '',
            content,
            flags=re.DOTALL
        )
        # Remove xweb auto-impersonate in curl_easy_init
        content = re.sub(
            r'  /\* XWEB_AUTO_IMPERSONATE:.*?\*/\s*\n\s*result = curl_easy_impersonate\(data, "xweb", true\);\s*\n\s*if\(result\) \{.*?return NULL;\s*\n\s*\}\s*\n',
            '',
            content,
            flags=re.DOTALL
        )
        # Remove xweb auto-impersonate in curl_easy_reset
        content = re.sub(
            r'  /\* XWEB_AUTO_IMPERSONATE:.*?\*/\s*\n\s*curl_easy_impersonate\(data, "xweb", true\);\s*\n',
            '',
            content,
            flags=re.DOTALL
        )
        # Remove orphaned xweb_json string
        content = re.sub(
            r'    static const char xweb_json\[\] =\s*\n.*?";\s*\n\s*curl_easy_impersonate_register\("xweb", xweb_json\);\s*\n\s*\}\s*\n',
            '',
            content,
            flags=re.DOTALL
        )
        print('[OK] Removed XWEB_AUTO_IMPERSONATE code')
        changed = True

    if changed:
        with open(easy_c_path, 'w', encoding='utf-8') as f:
            f.write(content)

    return changed


def patch_url_c(url_c_path):
    """Disable environment proxy detection in url.c"""
    with open(url_c_path, 'r', encoding='utf-8') as f:
        content = f.read()

    changed = False

    # 1. Replace detect_proxy function body
    old_detect = r'''static char \*detect_proxy\(struct Curl_easy \*data,\s*\n\s*struct connectdata \*conn\)\s*\n\{\s*\n  char \*proxy = NULL;\s*\n\s*\n  /\* If proxy was not specified.*?\*/\s*\n  char proxy_env\[20\];.*?return proxy;\s*\n\}'''

    new_detect = '''static char *detect_proxy(struct Curl_easy *data,
                          struct connectdata *conn)
{
  char *proxy = NULL;

  /* curl-impersonate: Do NOT read proxy from environment variables.
   * Only use proxy explicitly set by the user via CURLOPT_PROXY.
   * If no proxy is set, default to direct connection (no proxy).
   */
  (void)data;
  (void)conn;
  return proxy;  /* always NULL - no environment proxy detection */
}'''

    if re.search(old_detect, content, re.DOTALL):
        content = re.sub(old_detect, new_detect, content, flags=re.DOTALL)
        print('[OK] Disabled environment proxy detection in detect_proxy()')
        changed = True
    else:
        print('[SKIP] detect_proxy() not found or already patched')

    # 2. Disable NO_PROXY env var reading
    old_noproxy = r'''  if\(!data->set\.str\[STRING_NOPROXY\]\) \{
    const char \*p = "no_proxy";
    no_proxy = curl_getenv\(p\);
    if\(!no_proxy\) \{
      p = "NO_PROXY";
      no_proxy = curl_getenv\(p\);
    \}
    if\(no_proxy\) \{
      infof\(data, "Uses proxy env variable %s == '%s'", p, no_proxy\);
    \}
  \}'''

    new_noproxy = '''  if(!data->set.str[STRING_NOPROXY]) {
    /* curl-impersonate: Do NOT read NO_PROXY from environment.
     * Only use proxy settings explicitly set by the user.
     */
  }'''

    if re.search(old_noproxy, content):
        content = re.sub(old_noproxy, new_noproxy, content)
        print('[OK] Disabled NO_PROXY env var reading')
        changed = True
    else:
        print('[SKIP] NO_PROXY env var reading not found or already patched')

    if changed:
        with open(url_c_path, 'w', encoding='utf-8') as f:
            f.write(content)

    return changed


def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <curl_src_dir>')
        sys.exit(1)

    curl_src = sys.argv[1]
    easy_c = os.path.join(curl_src, 'lib', 'easy.c')
    url_c = os.path.join(curl_src, 'lib', 'url.c')

    for path in [easy_c, url_c]:
        if not os.path.isfile(path):
            print(f'[ERROR] {path} not found')
            sys.exit(1)

    print('=== apply_no_env_no_proxy.py ===')
    print(f'curl_src: {curl_src}\n')

    changed1 = patch_easy_c(easy_c)
    changed2 = patch_url_c(url_c)

    if changed1 or changed2:
        print('\n[OK] Post-patch applied successfully')
        # Create marker file
        marker = os.path.join(curl_src, '.no_env_patched')
        with open(marker, 'w') as f:
            f.write('no-env no-proxy patch applied\n')
    else:
        print('\n[SKIP] No changes needed (may already be patched)')

    return 0

if __name__ == '__main__':
    sys.exit(main())

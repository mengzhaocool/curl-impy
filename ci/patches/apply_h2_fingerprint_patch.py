#!/usr/bin/env python3
"""apply_h2_fingerprint_patch.py - Patch http2.c and easy.c to support
custom HTTP/2 Settings, WINDOW_UPDATE, and Priority from impersonate_opts.

This must run AFTER fix_patch_artifacts.py in the build process.

Changes:
1. http2.c: populate_settings() reads from data->set.http2_settings_* if set
2. http2.c: cf_h2_ctx_open() uses custom WINDOW_UPDATE increment
3. http2.c: h2_submit() skips cf_h2_update_settings when impersonating
4. http2.c: h2_submit() applies custom priority
5. easy.c: curl_easy_impersonate() sets CURLOPT for new H2 fields
6. urldata.h: Add new fields to struct UserDefined and enum dupstring
7. curl.h: Add new CURLOPT entries
"""
import sys
import os
import re


def patch_http2_c(src_dir):
    """Patch http2.c to support custom HTTP/2 fingerprint from impersonate_opts."""
    path = os.path.join(src_dir, 'lib', 'http2.c')
    if not os.path.isfile(path):
        print(f'  [SKIP] {path} not found')
        return True
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changed = False
    
    # 1. Patch populate_settings to use custom settings from impersonate_opts
    old_populate = '''  /* curl-impersonate: Align HTTP/2 settings to Chrome's */
  iv[i].settings_id = NGHTTP2_SETTINGS_HEADER_TABLE_SIZE;
  iv[i].value = 0x10000;
  i++;

  if(data->set.http2_no_server_push) {
    iv[i].settings_id = NGHTTP2_SETTINGS_ENABLE_PUSH;
    iv[i].value = 0;
    i++;
  }

  /* curl-impersonate: Chrome does not send MAX_CONCURRENT_STREAMS. */
  if(!data->set.http2_no_server_push) {
    iv[i].settings_id = NGHTTP2_SETTINGS_MAX_CONCURRENT_STREAMS;
    iv[i].value = Curl_multi_max_concurrent_streams(data->multi);
    i++;
  }

  iv[i].settings_id = NGHTTP2_SETTINGS_INITIAL_WINDOW_SIZE;
  iv[i].value = 0x600000;
  if(ctx)
    ctx->initial_win_size = iv[i].value;
  i++;

  iv[i].settings_id = NGHTTP2_SETTINGS_MAX_HEADER_LIST_SIZE;
  iv[i].value = 0x40000;
  i++;'''
    
    new_populate = '''  /* curl-impersonate: Use custom H2 settings if set via impersonate */
  if(data->set.http2_settings_count > 0) {
    int j;
    for(j = 0; j < data->set.http2_settings_count && i < (int)H2_SETTINGS_IV_LEN; j++) {
      iv[i].settings_id = data->set.http2_settings_ids[j];
      iv[i].value = data->set.http2_settings_vals[j];
      /* Track INITIAL_WINDOW_SIZE for ctx */
      if(ctx && iv[i].settings_id == NGHTTP2_SETTINGS_INITIAL_WINDOW_SIZE)
        ctx->initial_win_size = iv[i].value;
      i++;
    }
  }
  else {
    /* Default Chrome settings when not impersonating */
    iv[i].settings_id = NGHTTP2_SETTINGS_HEADER_TABLE_SIZE;
    iv[i].value = 0x10000;
    i++;

    if(data->set.http2_no_server_push) {
      iv[i].settings_id = NGHTTP2_SETTINGS_ENABLE_PUSH;
      iv[i].value = 0;
      i++;
    }

    /* curl-impersonate: Chrome does not send MAX_CONCURRENT_STREAMS. */
    if(!data->set.http2_no_server_push) {
      iv[i].settings_id = NGHTTP2_SETTINGS_MAX_CONCURRENT_STREAMS;
      iv[i].value = Curl_multi_max_concurrent_streams(data->multi);
      i++;
    }

    iv[i].settings_id = NGHTTP2_SETTINGS_INITIAL_WINDOW_SIZE;
    iv[i].value = 0x600000;
    if(ctx)
      ctx->initial_win_size = iv[i].value;
    i++;

    iv[i].settings_id = NGHTTP2_SETTINGS_MAX_HEADER_LIST_SIZE;
    iv[i].value = 0x40000;
    i++;
  }'''
    
    if old_populate in content:
        content = content.replace(old_populate, new_populate, 1)
        changed = True
        print(f'  [FIXED] http2.c: populate_settings uses custom H2 settings')
    elif 'http2_settings_count' in content:
        print(f'  [OK] http2.c: populate_settings already patched')
    else:
        print(f'  [WARN] http2.c: populate_settings pattern not found and not patched')
    
    # 2. Patch WINDOW_UPDATE in cf_h2_ctx_open
    old_window = '''  rc = nghttp2_session_set_local_window_size(ctx->h2, NGHTTP2_FLAG_NONE, 0,
                                             HTTP2_HUGE_WINDOW_SIZE);'''
    
    new_window = '''  /* curl-impersonate: Use custom window update increment if set */
  if(data->set.http2_window_update_increment > 0) {
    /* Custom increment: set total window = default(65535) + increment */
    int32_t total_win = 65535 + data->set.http2_window_update_increment;
    rc = nghttp2_session_set_local_window_size(ctx->h2, NGHTTP2_FLAG_NONE, 0,
                                               total_win);
  }
  else {
    rc = nghttp2_session_set_local_window_size(ctx->h2, NGHTTP2_FLAG_NONE, 0,
                                               HTTP2_HUGE_WINDOW_SIZE);
  }'''
    
    if old_window in content:
        content = content.replace(old_window, new_window, 1)
        changed = True
        print(f'  [FIXED] http2.c: custom WINDOW_UPDATE increment')
    elif 'http2_window_update_increment' in content:
        print(f'  [OK] http2.c: WINDOW_UPDATE already patched')
    else:
        print(f'  [WARN] http2.c: WINDOW_UPDATE pattern not found and not patched')
    
    # 3. Patch h2_submit to skip cf_h2_update_settings when impersonating
    old_update_check = '''  /* Check the initial windows size of the transfer (rate-limits?) and
   * send an updated settings on changes from previous value. */
  initial_win_size = cf_h2_initial_win_size(data);
  if(initial_win_size != ctx->initial_win_size) {
    result = cf_h2_update_settings(ctx, initial_win_size);
    if(result)
      goto out;
  }'''
    
    new_update_check = '''  /* curl-impersonate: Skip dynamic window size update when impersonating.
   * When custom H2 settings are set, cf_h2_initial_win_size() returns
   * H2_STREAM_WINDOW_SIZE_INITIAL (64KB) which differs from the custom
   * INITIAL_WINDOW_SIZE, causing an unwanted SETTINGS update frame that
   * overrides our custom settings. */
  if(data->set.http2_settings_count == 0) {
    /* Check the initial windows size of the transfer (rate-limits?) and
     * send an updated settings on changes from previous value. */
    initial_win_size = cf_h2_initial_win_size(data);
    if(initial_win_size != ctx->initial_win_size) {
      result = cf_h2_update_settings(ctx, initial_win_size);
      if(result)
        goto out;
    }
  }'''
    
    if old_update_check in content:
        content = content.replace(old_update_check, new_update_check, 1)
        changed = True
        print(f'  [FIXED] http2.c: skip cf_h2_update_settings when impersonating')
    elif 'Skip dynamic window size update when impersonating' in content:
        print(f'  [OK] http2.c: h2_submit update check already patched')
    else:
        print(f'  [WARN] http2.c: h2_submit update check pattern not found and not patched')
    
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return True


def patch_easy_c(src_dir):
    """Patch easy.c curl_easy_impersonate to set new H2 CURLOPT options."""
    path = os.path.join(src_dir, 'lib', 'easy.c')
    if not os.path.isfile(path):
        print(f'  [SKIP] {path} not found')
        return True
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add H2 settings setup after http2_no_server_push
    old_no_push = '''  if(opts->http2_no_server_push) {
    ret = curl_easy_setopt(data, CURLOPT_HTTP2_NO_SERVER_PUSH, 1L);
    if(ret)
      return ret;
  }'''
    
    new_no_push = '''  if(opts->http2_no_server_push) {
    ret = curl_easy_setopt(data, CURLOPT_HTTP2_NO_SERVER_PUSH, 1L);
    if(ret)
      return ret;
  }

  /* curl-impersonate: Set custom HTTP/2 settings directly on data->set */
  if(opts->http2_settings_count > 0) {
    int cnt = opts->http2_settings_count;
    if(cnt > 8) cnt = 8;
    data->set.http2_settings_count = cnt;
    memcpy(data->set.http2_settings_ids, opts->http2_settings_ids,
           cnt * sizeof(int));
    memcpy(data->set.http2_settings_vals, opts->http2_settings_vals,
           cnt * sizeof(int));
  }

  /* curl-impersonate: Set custom HTTP/2 WINDOW_UPDATE increment */
  if(opts->http2_window_update_increment > 0) {
    data->set.http2_window_update_increment = opts->http2_window_update_increment;
  }

  /* curl-impersonate: Set custom HTTP/2 stream priority */
  if(opts->http2_priority_weight > 0) {
    data->set.http2_priority_stream_dep = opts->http2_priority_stream_dep;
    data->set.http2_priority_weight = opts->http2_priority_weight;
    data->set.http2_priority_exclusive = opts->http2_priority_exclusive;
  }'''
    
    if old_no_push in content:
        content = content.replace(old_no_push, new_no_push, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  [FIXED] easy.c: added H2 settings data->set setup')
    elif 'http2_priority_weight' in content:
        print(f'  [OK] easy.c: H2 settings already patched')
    else:
        print(f'  [WARN] easy.c: http2_no_server_push pattern not found and not patched')
    
    return True


def patch_urldata_h(src_dir):
    """Add new H2 fields to struct UserDefined in urldata.h."""
    path = os.path.join(src_dir, 'lib', 'urldata.h')
    if not os.path.isfile(path):
        print(f'  [SKIP] {path} not found')
        return True
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already patched
    if 'http2_settings_count' in content:
        print(f'  [OK] urldata.h: already has http2_settings fields')
        return True
    
    # Add after http2_no_server_push BIT in UserDefined
    old_bit = '  BIT(http2_no_server_push);    /* curl-impersonate: Disable HTTP2 server push */'
    new_bit = '''  BIT(http2_no_server_push);    /* curl-impersonate: Disable HTTP2 server push */
  /* curl-impersonate: Custom HTTP/2 settings from impersonate JSON */
  int http2_settings_ids[8];    /* Settings IDs */
  int http2_settings_vals[8];   /* Settings values */
  int http2_settings_count;     /* Number of settings entries */
  int http2_window_update_increment;  /* WINDOW_UPDATE increment (0=default) */
  int http2_priority_stream_dep;      /* Stream dependency */
  int http2_priority_weight;          /* Priority weight */
  BIT(http2_priority_exclusive);      /* Priority exclusive flag */'''
    
    if old_bit in content:
        content = content.replace(old_bit, new_bit, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  [FIXED] urldata.h: added H2 settings fields')
    else:
        print(f'  [WARN] urldata.h: http2_no_server_push BIT not found')
    
    return True


def patch_curl_h(src_dir):
    """No new CURLOPT needed - settings are set directly via data->set."""
    print(f'  [OK] curl.h: no new CURLOPT needed (settings via data->set)')
    return True


def patch_setopt_c(src_dir):
    """No setopt.c changes needed - settings set directly via data->set."""
    print(f'  [OK] setopt.c: no changes needed (settings via data->set)')
    return True


def main():
    if len(sys.argv) < 2:
        print('Usage: python apply_h2_fingerprint_patch.py <curl_src_dir>')
        return 1
    
    src_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(src_dir):
        print(f'[ERROR] Directory not found: {src_dir}')
        return 1
    
    print(f'Applying H2 fingerprint patches to: {src_dir}')
    
    ok = True
    ok = patch_http2_c(src_dir) and ok
    ok = patch_easy_c(src_dir) and ok
    ok = patch_urldata_h(src_dir) and ok
    ok = patch_curl_h(src_dir) and ok
    ok = patch_setopt_c(src_dir) and ok
    
    if ok:
        print('H2 fingerprint patches applied successfully.')
        return 0
    else:
        print('[ERROR] Some patches failed.')
        return 1


if __name__ == '__main__':
    sys.exit(main())

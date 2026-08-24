import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
os.makedirs(ASSETS_DIR, exist_ok=True)

DEFAULT_USER = 'Eliasilyz'
DEFAULT_DAYS = 3
TRACKER_FILE = os.path.join(ASSETS_DIR, 'following_tracker.json')
WHITELIST_FILE = os.path.join(ASSETS_DIR, 'whitelist.txt')
UNFOLLOW_COUNTER_FILE = os.path.join(ASSETS_DIR, 'unfollow_counter.txt')

import base64

# Base64 Encoded Protected Whitelist (Tersembunyi)
_DEFAULT_PROTECTED_B64 = 'TmF5bGEtSGFuaWZhaCxOYXlsYXRvZDcsRGFuYVB1dHJhMTMzLEVSTEFOUkFITUFULElNUEhORU4sU2Fua2FWb2xsZXJlaWksc2lwdXR6eCxCT1RDQUhYLGRyZWFteXNhbmQsUml6a2FydHosS2FlZGVBSSxNYWFuLXB5'

def _decode_b64(raw_str):
    try:
        decoded = base64.b64decode(raw_str.strip().encode('utf-8')).decode('utf-8')
        return decoded
    except Exception:
        return raw_str

def load_tracker():
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Failed to read {TRACKER_FILE}: {e}. Initializing empty tracker.")
    return {}

def save_tracker(tracker):
    try:
        with open(TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(tracker, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Error] Failed to save {TRACKER_FILE}: {e}")

def load_whitelist():
    whitelist = set()

    # 1. Muat default protected list dari Base64
    for u in _decode_b64(_DEFAULT_PROTECTED_B64).split(','):
        u = u.strip().lower()
        if u:
            whitelist.add(u)

    # 1. Utamakan dari Environment Variable / GitHub Secret (100% Private & Tersembunyi)
    env_whitelist = os.getenv('UNFOLLOW_WHITELIST') or os.getenv('WHITELIST')
    if env_whitelist:
        # Mendukung base64 decode otomatis jika di-encode
        try:
            import base64
            decoded = base64.b64decode(env_whitelist.encode('utf-8')).decode('utf-8')
            if any(c.isalnum() for c in decoded):
                env_whitelist = decoded
        except Exception:
            pass

        for item in env_whitelist.replace(',', '\n').splitlines():
            item = item.strip()
            if item and not item.startswith('#'):
                whitelist.add(item.lower())

    # 2. Cek file lokal tersembunyi (.whitelist atau assets/.whitelist atau assets/whitelist.txt)
    possible_files = [
        os.path.join(BASE_DIR, '.whitelist'),
        os.path.join(ASSETS_DIR, '.whitelist'),
        os.path.join(ASSETS_DIR, 'whitelist.txt')
    ]
    for path in possible_files:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            whitelist.add(line.lower())
                break
            except Exception:
                pass

    return whitelist

def update_unfollow_counter(count):
    current_count = 0
    if os.path.exists(UNFOLLOW_COUNTER_FILE):
        try:
            with open(UNFOLLOW_COUNTER_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    current_count = int(content)
        except Exception:
            current_count = 0
    total_unfollowed = current_count + count
    try:
        with open(UNFOLLOW_COUNTER_FILE, 'w', encoding='utf-8') as f:
            f.write(str(total_unfollowed) + '\n')
    except Exception as e:
        print(f"[Warning] Failed to update unfollow_counter.txt: {e}")
    return total_unfollowed

def http_get_json(url, token):
    if HAS_REQUESTS:
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}',
            'User-Agent': 'GitHub-Unfollow-Bot'
        }
        res = requests.get(url, headers=headers)
        return res.status_code, res.json() if res.status_code == 200 else res.text
    else:
        req = urllib.request.Request(url, headers={
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}',
            'User-Agent': 'GitHub-Unfollow-Bot'
        })
        try:
            with urllib.request.urlopen(req) as response:
                status = response.getcode()
                body = json.loads(response.read().decode('utf-8'))
                return status, body
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            return e.code, err_body
        except Exception as e:
            return 500, str(e)

def http_delete(url, token):
    if HAS_REQUESTS:
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}',
            'User-Agent': 'GitHub-Unfollow-Bot'
        }
        res = requests.delete(url, headers=headers)
        return res.status_code, res.text
    else:
        req = urllib.request.Request(url, headers={
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}',
            'User-Agent': 'GitHub-Unfollow-Bot'
        }, method='DELETE')
        try:
            with urllib.request.urlopen(req) as response:
                return response.getcode(), ""
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            return e.code, err_body
        except Exception as e:
            return 500, str(e)

def fetch_all_pages(url, token, entity_name="items"):
    items = []
    page = 1
    while True:
        paged_url = f"{url}?page={page}&per_page=100" if "?" not in url else f"{url}&page={page}&per_page=100"
        status_code, data = http_get_json(paged_url, token)
        
        if status_code != 200:
            print(f"[Error] Failed to fetch {entity_name} on page {page} (Status {status_code}): {data}")
            break
            
        if not data or not isinstance(data, list):
            break
            
        for entry in data:
            login = entry.get('login')
            if login:
                items.append(login)
                
        if len(data) < 100:
            break
        page += 1
        
    return items

def main():
    parser = argparse.ArgumentParser(description="Unfollow GitHub users who do not follow back within N days.")
    parser.add_argument('--user', type=str, default=None, help="GitHub username (default: env or Eliasilyz)")
    parser.add_argument('--token', type=str, default=None, help="GitHub Personal Access Token")
    parser.add_argument('--days', type=float, default=DEFAULT_DAYS, help=f"Number of days to wait before unfollowing (default: {DEFAULT_DAYS})")
    parser.add_argument('--dry-run', action='store_true', help="Preview unfollow targets without making any actual API changes")
    parser.add_argument('--immediate', action='store_true', help="Unfollow all non-followers immediately ignoring the days threshold")
    parser.add_argument('--force', action='store_true', help="Do not ask for interactive confirmation before unfollowing")
    args = parser.parse_args()

    github_user = args.user or os.getenv('github_user') or os.getenv('GITHUB_USER') or DEFAULT_USER
    personal_github_token = (
        args.token 
        or os.getenv('personal_github_token') 
        or os.getenv('PERSONAL_GITHUB_TOKEN') 
        or os.getenv('PAT_TOKEN')
        or os.getenv('GITHUB_TOKEN')
    )

    if not personal_github_token:
        print("[Error] GitHub Personal Access Token is required!")
        print("Set GITHUB_TOKEN / PERSONAL_GITHUB_TOKEN environment variable or use --token <your_token>")
        sys.exit(1)

    print("=" * 60)
    print(" GitHub Unfollow Bot - Non-Follower Cleaner")
    print(f" Target User : {github_user}")
    print(f" Day Grace   : {'IMMEDIATE (0 days)' if args.immediate else f'{args.days} day(s)'}")
    print(f" Mode        : {'DRY RUN (Simulation)' if args.dry_run else 'LIVE EXECUTION'}")
    print(f" Assets Path : {ASSETS_DIR}")
    print("=" * 60)

    # 1. Load whitelist and tracker
    whitelist = load_whitelist()
    tracker = load_tracker()
    now_utc = datetime.now(timezone.utc)

    # 2. Fetch current followers & following
    print("\n[1/4] Fetching your current followers list from GitHub...")
    followers_list = fetch_all_pages(f'https://api.github.com/users/{github_user}/followers', personal_github_token, "followers")
    followers_set = set(u.lower() for u in followers_list)
    print(f"      -> Found {len(followers_set)} followers.")

    print("\n[2/4] Fetching your current following list from GitHub...")
    following_list = fetch_all_pages(f'https://api.github.com/users/{github_user}/following', personal_github_token, "following")
    following_set = set(following_list)
    print(f"      -> Found {len(following_set)} users you are following.")

    # 3. Synchronize tracking database
    print("\n[3/4] Updating following tracking records...")
    new_tracked_count = 0
    for u in following_list:
        if u not in tracker:
            tracker[u] = {
                "followed_at": now_utc.isoformat()
            }
            new_tracked_count += 1

    # Remove users we no longer follow from the tracker
    tracked_users = list(tracker.keys())
    for u in tracked_users:
        if u not in following_set:
            del tracker[u]

    save_tracker(tracker)
    if new_tracked_count > 0:
        print(f"      -> Added {new_tracked_count} newly discovered following accounts into tracker.")

    # 4. Analyze non-followers and grace periods
    print("\n[4/4] Analyzing follower relationships...")
    
    mutuals = []
    whitelisted = []
    in_grace_period = []
    eligible_for_unfollow = []

    for u in following_list:
        u_lower = u.lower()
        if u_lower in followers_set:
            mutuals.append(u)
        elif u_lower in whitelist:
            whitelisted.append(u)
        else:
            # Check elapsed time
            record = tracker.get(u, {})
            followed_at_str = record.get("followed_at")
            if followed_at_str:
                try:
                    followed_at = datetime.fromisoformat(followed_at_str)
                    if followed_at.tzinfo is None:
                        followed_at = followed_at.replace(tzinfo=timezone.utc)
                    elapsed_days = (now_utc - followed_at).total_seconds() / 86400.0
                except Exception:
                    elapsed_days = 0.0
            else:
                elapsed_days = 0.0

            if args.immediate or elapsed_days >= args.days:
                eligible_for_unfollow.append((u, elapsed_days))
            else:
                in_grace_period.append((u, elapsed_days))

    print("\n" + "-" * 60)
    print(" SUMMARY")
    print("-" * 60)
    print(f" Total Following               : {len(following_list)}")
    print(f" Total Followers               : {len(followers_set)}")
    print(f" Mutual Followers (Follow back): {len(mutuals)}")
    print(f" Whitelisted Accounts          : {len(whitelisted)}")
    print(f" Non-followers (Grace period)  : {len(in_grace_period)}")
    print(f" Non-followers To Unfollow     : {len(eligible_for_unfollow)}")
    print("-" * 60)

    if in_grace_period:
        print(f"\n[Info] Accounts in grace period (waiting to reach {args.days} days):")
        for u, days in in_grace_period[:15]:
            print(f"  • {u} (followed {days:.1f} days ago)")
        if len(in_grace_period) > 15:
            print(f"  ... and {len(in_grace_period) - 15} more.")

    if not eligible_for_unfollow:
        print("\n[✓] No accounts meet the unfollow criteria. You're all good!")
        return

    print(f"\n[!] Accounts eligible to be unfollowed ({len(eligible_for_unfollow)}):")
    for u, days in eligible_for_unfollow[:25]:
        print(f"  ✗ {u} (followed {days:.1f} days ago - does not follow back)")
    if len(eligible_for_unfollow) > 25:
        print(f"  ... and {len(eligible_for_unfollow) - 25} more.")

    if args.dry_run:
        print("\n[Dry Run] No accounts were unfollowed because --dry-run is active.")
        return

    # Interactive confirmation if not --force
    if not args.force:
        confirm = input(f"\nAre you sure you want to unfollow {len(eligible_for_unfollow)} user(s)? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("Operation cancelled by user.")
            return

    print("\nStarting unfollow execution...")
    unfollowed_count = 0
    failed_count = 0

    for u, days in eligible_for_unfollow:
        unfollow_url = f'https://api.github.com/user/following/{u}'
        status_code, err_msg = http_delete(unfollow_url, personal_github_token)
        
        if status_code == 204:
            print(f"  [Unfollowed] {u} (was followed {days:.1f} days ago)")
            unfollowed_count += 1
            if u in tracker:
                del tracker[u]
        else:
            print(f"  [Failed] {u} (Status {status_code}): {err_msg}")
            failed_count += 1

        time.sleep(0.5)  # Small delay to prevent rate-limiting

    save_tracker(tracker)
    total_unfollowed_historical = update_unfollow_counter(unfollowed_count)

    print("\n" + "=" * 60)
    print(f" Completed! Unfollowed: {unfollowed_count} | Failed: {failed_count}")
    print(f" Total Historical Unfollowed   : {total_unfollowed_historical}")
    print("=" * 60)

if __name__ == '__main__':
    main()

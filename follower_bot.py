import os
import requests

print('Hi! I am GitHub follower bot.')
print('Letting you follow all your followers!')
print('Starting fetching your follower lists...\n')

github_user = os.getenv('github_user') or os.getenv('GITHUB_USER') or 'Eliasilyz'
personal_github_token = os.getenv('personal_github_token') or os.getenv('PERSONAL_GITHUB_TOKEN') or os.getenv('GITHUB_TOKEN')

if not personal_github_token:
    print('Error: personal_github_token is not set!')
    exit(1)

headers = {
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': f'token {personal_github_token}',
    'User-Agent': 'Mozilla/5.0 (GitHub-Follower-Bot)'
}

followers_file = './followers.txt'
follower_txt_lists = set()

if os.path.exists(followers_file):
    with open(followers_file, 'r', encoding='utf-8') as f:
        follower_txt_lists = set(line.strip() for line in f if line.strip())

page = 1
follower_counter = 0
new_followed_count = 0

with open(followers_file, 'a', encoding='utf-8') as f:
    while True:
        follower_url = f'https://api.github.com/users/{github_user}/followers?page={page}&per_page=100'
        response = requests.get(follower_url, headers=headers)
        
        if response.status_code != 200:
            print(f'Failed to fetch followers (Status {response.status_code}): {response.text}')
            break

        follower_lists = response.json()
        if not follower_lists:
            break

        follower_counter += len(follower_lists)

        for follower_info in follower_lists:
            user = follower_info.get('login')
            if not user or user in follower_txt_lists:
                continue

            update_url = f'https://api.github.com/user/following/{user}'
            put_res = requests.put(update_url, headers=headers)

            if put_res.status_code == 204:
                print(f'User: {user} has been followed!')
                f.write(f'{user}\n')
                f.flush()
                follower_txt_lists.add(user)
                new_followed_count += 1
            else:
                print(f'Failed to follow {user} (Status {put_res.status_code}): {put_res.text}')

        page += 1

with open('follower_counter.txt', 'w', encoding='utf-8') as f:
    f.write(str(follower_counter) + '\n')

print(f'\nFinished! Total followers counted: {follower_counter}. New followers followed: {new_followed_count}.')

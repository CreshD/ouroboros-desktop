#!/usr/bin/env python3
"""
Find forks and visual resources from GitHub forks of Ouroboros.
"""
import json
import urllib.request
import os

def github_request(path, token):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Ouroboros-Agent"
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN not set")
        return 1
    
    # Get forks of main repo
    try:
        result = github_request("/repos/joi-lab/ouroboros-desktop/forks", token)
        print(f"Found {len(result)} forks:")
        for fork in result:
            owner = fork['owner']['login']
            name = fork['name']
            full_name = fork['full_name']
            url = fork['html_url']
            pushed_at = fork.get('pushed_at', 'never')
            lang = fork.get('language', 'N/A')
            print(f"  - {full_name}")
            print(f"    Language: {lang}")
            print(f"    URL: {url}")
            print(f"    Last push: {pushed_at}")
            print()
    except Exception as e:
        print(f"Error fetching forks: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
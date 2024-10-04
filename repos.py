#!/usr/bin/env python

import csv
import re
import requests
import requests_cache
from datetime import datetime
from decouple import config
from time import sleep

# Environment variables
BASE_URL = 'https://api.github.com'
ENDPOINT = config('ENDPOINT', default='/search/repositories')
URL = BASE_URL + ENDPOINT
QUERY = config('QUERY', default='quasar OR quasar-framework in:topics')
PER_PAGE = config('PER_PAGE', default=100, cast=int)
CSV_FILE = config('CSV_FILE', default='quasar_repos.csv')
GITHUB_TOKEN = config('GITHUB_TOKEN')

# Install cache
requests_cache.install_cache('github_cache', expire_after=3600)


def get_repos(url, params=None):
    headers = {
        'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {GITHUB_TOKEN}'
    }
    while True:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 429 or response.status_code == 403:
            reset_time = int(response.headers.get('x-ratelimit-reset', 0)) - int(time.time())
            print(f"Rate limit exceeded. Waiting for {reset_time} seconds.")
            sleep(reset_time + 1)
            continue
        response.raise_for_status()
        return response


def parse_link_header(link_header):
    links = {}
    if link_header:
        for link in link_header.split(', '):
            url, rel = re.search(r'<(.*)>; rel="(.*)"', link).groups()
            links[rel] = url
    return links


def pager(url, params):
    total_count = None
    while url:
        response = get_repos(url, params)
        data = response.json()

        if total_count is None:
            total_count = data['total_count']
            print(f"Total repositories to fetch: {total_count}")

        yield from data['items']

        links = parse_link_header(response.headers.get('Link', ''))
        url = links.get('next')
        params = None  # new url contains query parameters


def truncate_description(description, max_length=80):
    if description and len(description) > max_length:
        return description[: max_length - 3] + '...'
    return description if description else ''


def write_csv(repos, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['full_name', 'description', 'stargazers_count', 'language', 'updated_at', 'url'])
        for repo in sorted(
            repos, key=lambda x: (-x['stargazers_count'], datetime.strptime(x['updated_at'], '%Y-%m-%dT%H:%M:%SZ')), reverse=True
        ):
            writer.writerow(
                [
                    repo['full_name'],
                    truncate_description(repo['description']),
                    repo['stargazers_count'],
                    repo['language'],
                    repo['updated_at'],
                    repo['html_url'],
                ]
            )


def main():
    params = {
        'q': QUERY,
        'per_page': PER_PAGE,
        'sort': 'stars',
        'order': 'desc'
    }

    repos = list(pager(URL, params))
    print(f"Total repositories fetched: {len(repos)}")

    write_csv(repos, CSV_FILE)
    print(f"Data written to {CSV_FILE}")


if __name__ == "__main__":
    main()

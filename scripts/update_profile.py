"""Refresh public profile data using GitHub REST; no external runtime dependencies."""
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USER = 'Crazy4Lamb'


def fetch(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Crazy4Lamb-profile'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request('https://api.github.com' + path, headers=headers), timeout=30) as response:
        return json.load(response)


def load_repos():
    result = []
    for page in range(1, 101):
        batch = fetch(f'/users/{USER}/repos?type=owner&per_page=100&sort=pushed&page={page}')
        result.extend(batch)
        if len(batch) < 100:
            return [r for r in result if not r['fork'] and not r['private']]
    raise RuntimeError('Pagination limit exceeded')


def safe(value):
    """Treat API data as source material, never as Markdown or HTML."""
    return escape(str(value or '').replace('|', '/').replace('\n', ' ').replace('\r', ' '))


def public_projects(repos):
    return sorted(
        (r for r in repos if r['name'].lower() != USER.lower() and not r['archived']),
        key=lambda r: r['pushed_at'] or '',
        reverse=True,
    )


def latest_project(repos):
    projects = sorted(public_projects(repos), key=lambda r: r['created_at'] or '', reverse=True)
    if not projects:
        return 'New experiments are on the way. / 新的实验正在路上。'
    repo = projects[0]
    description = repo.get('description') or 'An ongoing experiment / 持续探索中'
    topics = [safe(topic) for topic in (repo.get('topics') or [])[:4]]
    stack = ' · '.join(([safe(repo.get('language'))] if repo.get('language') else []) + topics)
    lines = [
        f"### 🚀 [{safe(repo['name'])}]({repo['html_url']})",
        '',
        safe(description),
    ]
    if stack:
        lines += ['', f'`{stack}`']
    return '\n'.join(lines)


def projects_table(repos):
    rows = ['| Project / 项目 | Description / 简介 | Stack / 技术 |', '|---|---|---|']
    for repo in public_projects(repos):
        description = repo.get('description') or 'An ongoing experiment / 持续探索中'
        if len(description) > 180:
            description = description[:177] + '…'
        topics = [safe(topic) for topic in (repo.get('topics') or [])[:3]]
        stack = ' · '.join(([safe(repo.get('language'))] if repo.get('language') else []) + topics)
        rows.append(f"| [{safe(repo['name'])}]({repo['html_url']}) | {safe(description)} | {stack or '—'} |")
    return '\n'.join(rows)


def recent_table(repos):
    rows = ['| Project | Description / 简介 | Updated (UTC) |', '|---|---|---|']
    recent = public_projects(repos)[:6]
    for repo in recent:
        description = repo.get('description') or 'An ongoing experiment / 持续探索中'
        if len(description) > 160:
            description = description[:157] + '…'
        rows.append(f"| [{safe(repo['name'])}]({repo['html_url']}) | {safe(description)} | {(repo['pushed_at'] or '')[:10]} |")
    return '\n'.join(rows)


def stats_svg(repos, followers, now):
    metrics = [('PUBLIC REPOS', len(repos)), ('STARS', sum(r['stargazers_count'] for r in repos)), ('FORKS', sum(r['forks_count'] for r in repos)), ('FOLLOWERS', followers)]
    langs = Counter(r['language'] for r in repos if r.get('language'))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="210" viewBox="0 0 960 210" role="img" aria-label="GitHub public account statistics">', '<rect width="960" height="210" rx="20" fill="#f6f3ff"/>', '<text x="30" y="35" font-family="Segoe UI,Arial,sans-serif" font-size="15" font-weight="600" fill="#7040db">PUBLIC WORK / AT A GLANCE</text>']
    for index, (label, value) in enumerate(metrics):
        x = 30 + index * 235
        parts += [f'<text x="{x}" y="87" font-family="Segoe UI,Arial,sans-serif" font-size="35" font-weight="700" fill="#29213f">{value}</text>', f'<text x="{x}" y="113" font-family="Segoe UI,Arial,sans-serif" font-size="12" letter-spacing="1" fill="#716780">{label}</text>']
    language_text = ' · '.join(f'{lang} ({count})' for lang, count in langs.most_common(5)) or 'More experiments ahead'
    parts += [f'<text x="30" y="156" font-family="Segoe UI,Arial,sans-serif" font-size="14" fill="#49316e">Primary languages by repo: {escape(language_text)}</text>', f'<text x="30" y="187" font-family="Segoe UI,Arial,sans-serif" font-size="12" fill="#716780">Updated {now} UTC · Owned public repos, excluding forks</text>', '</svg>']
    return '\n'.join(parts)


def main():
    repos = load_repos()
    profile = fetch('/users/' + USER)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    path = ROOT / 'README.md'
    text = path.read_text(encoding='utf-8-sig')
    blocks = {
        'LATEST': latest_project(repos),
        'PROJECTS': projects_table(repos),
        'RECENT': recent_table(repos),
    }
    updated = text
    for name, content in blocks.items():
        pattern = rf'<!-- {name}:START -->.*?<!-- {name}:END -->'
        if len(re.findall(pattern, updated, re.S)) != 1:
            raise ValueError(f'README must contain exactly one {name.lower()} block')
        replacement = f'<!-- {name}:START -->\n{content}\n<!-- {name}:END -->'
        updated = re.sub(pattern, lambda _: replacement, updated, flags=re.S)
    # Fetch everything successfully before writing either output.
    svg = stats_svg(repos, profile['followers'], now)
    path.write_text(updated, encoding='utf-8', newline='\n')
    (ROOT / 'assets/stats.svg').write_text(svg, encoding='utf-8', newline='\n')
    print(f'Updated public statistics for {len(repos)} repositories.')


if __name__ == '__main__':
    main()

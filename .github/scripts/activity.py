"""Render a small activity chart from GitHub's available public push events."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

zone = timezone(timedelta(hours=7))
cutoff = datetime.now(timezone.utc) - timedelta(days=14)
events = []
for page in range(1, 4):
    request = Request(
        f'https://api.github.com/users/SugguSCH/events/public?per_page=100&page={page}',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'SugguSCH-profile',
                 'Authorization': f'Bearer {os.environ["GH_TOKEN"]}'},
    )
    with urlopen(request, timeout=30) as response:
        batch = json.load(response)
    events.extend(batch)
    if len(batch) < 100 or datetime.fromisoformat(batch[-1]['created_at'].replace('Z', '+00:00')) < cutoff:
        break

pushes = [datetime.fromisoformat(event['created_at'].replace('Z', '+00:00')).astimezone(zone)
          for event in events if event['type'] == 'PushEvent'
          and event['actor']['login'].lower() == 'suggusch'
          and datetime.fromisoformat(event['created_at'].replace('Z', '+00:00')) >= cutoff]
hours = Counter(value.hour for value in pushes)
days = Counter(value.weekday() for value in pushes)
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="700" height="340" viewBox="0 0 700 340" role="img">',
       '<title>Public push activity by hour and day, Bangkok time</title>',
       '<rect width="700" height="340" rx="14" fill="#0d1117"/>',
       '<g fill="#c9d1d9" font-family="Arial,sans-serif">',
       '<text x="24" y="32" font-size="19" font-weight="bold">Activity patterns</text>',
       f'<text x="24" y="56" font-size="12">{len(pushes)} public push events found in the last 14 days · Bangkok (UTC+7)</text>']

def chart(counts, labels, y, width):
    maximum = max(counts.values(), default=1) or 1
    step = width / len(labels)
    for index, label in enumerate(labels):
        x = 24 + step * index
        height = counts[index] / maximum * 65
        svg.append(f'<rect x="{x:.1f}" y="{y-height:.1f}" width="{step-5:.1f}" height="{height:.1f}" rx="2" fill="#79c0ff"><title>{escape(label)}: {counts[index]} push events</title></rect>')
        svg.append(f'<text x="{x+step/2-2:.1f}" y="{y+18}" text-anchor="middle" font-size="10">{escape(label)}</text>')

svg.append('<text x="24" y="86" font-size="13">By hour</text>')
chart(hours, [f'{hour:02}' for hour in range(24)], 165, 650)
svg.append('<text x="24" y="213" font-size="13">By day</text>')
chart(days, ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], 290, 650)
svg.append('<text x="24" y="330" font-size="10">Based on available public events; push counts are not commit counts or coding hours.</text></g></svg>')
Path('metrics').mkdir(exist_ok=True)
Path('metrics/habits.svg').write_text(''.join(svg), encoding='utf-8')

# GitHub now provides before/head SHAs rather than a commit list on PushEvent.
# Sample distinct public push heads; this measures changed lines, not coding time.
extensions = {
    '.ts': 'TypeScript', '.tsx': 'TypeScript', '.js': 'JavaScript', '.jsx': 'JavaScript',
    '.mjs': 'JavaScript', '.cjs': 'JavaScript', '.py': 'Python', '.java': 'Java',
    '.dart': 'Dart', '.r': 'R', '.html': 'HTML', '.css': 'CSS', '.scss': 'SCSS',
    '.sql': 'SQL', '.c': 'C', '.h': 'C', '.cpp': 'C++', '.ino': 'C++',
    '.sh': 'Shell', '.ps1': 'PowerShell', '.yml': 'YAML', '.yaml': 'YAML',
}
languages = Counter()
seen = set()
sampled = 0
for event in events:
    if event['type'] != 'PushEvent' or event['actor']['login'].lower() != 'suggusch':
        continue
    if datetime.fromisoformat(event['created_at'].replace('Z', '+00:00')) < cutoff:
        continue
    repository, head = event['repo']['name'], event['payload'].get('head')
    if not head or (repository, head) in seen:
        continue
    seen.add((repository, head))
    request = Request(f'https://api.github.com/repos/{repository}/commits/{head}',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'SugguSCH-profile',
                 'Authorization': f'Bearer {os.environ["GH_TOKEN"]}'})
    try:
        with urlopen(request, timeout=30) as response:
            commit = json.load(response)
    except HTTPError as error:
        if error.code in (404, 422):
            continue
        raise
    sampled += 1
    for file in commit.get('files', []):
        language = extensions.get(Path(file['filename']).suffix.lower())
        if language:
            languages[language] += file.get('changes', 0)
    if sampled >= 20:
        break

top = languages.most_common(6)
total = sum(languages.values())
height = 125 + max(1, len(top)) * 32
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="700" height="{height}" viewBox="0 0 700 {height}" role="img">',
    '<title>Recent language activity sampled from public push heads</title>',
    f'<rect width="700" height="{height}" rx="14" fill="#0d1117"/>',
    '<g font-family="Arial,sans-serif" fill="#c9d1d9">',
    '<text x="24" y="32" font-size="19" font-weight="bold">Recent language activity</text>',
    f'<text x="24" y="56" font-size="12">Changed lines in {sampled} sampled public push heads · last 14 days</text>']
for i, (language, changes) in enumerate(top):
    y = 88 + 32 * i
    share = changes / total
    parts.extend([f'<text x="24" y="{y+4}" font-size="12">{escape(language)}</text>',
        f'<rect x="150" y="{y-10}" width="{share*450:.1f}" height="16" rx="3" fill="#79c0ff"/>',
        f'<text x="615" y="{y+4}" font-size="12">{share:.1%}</text>'])
if not top:
    parts.append('<text x="24" y="92" font-size="12">No supported code changes found in this sample.</text>')
parts.append(f'<text x="24" y="{height-20}" font-size="10">Inferred from file extensions; sampled activity, not all commits or skill level.</text></g></svg>')
Path('metrics/recent-languages.svg').write_text(''.join(parts), encoding='utf-8')

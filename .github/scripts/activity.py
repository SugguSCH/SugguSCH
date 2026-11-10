"""Render a small activity chart from GitHub's available public push events."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
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

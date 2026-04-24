"""
Fetches all registered RSS feeds and writes a merged JSON archive to data/feeds.json.
Runs in GitHub Actions every 12 hours. Preserves existing items across runs so
the archive accumulates over time.
"""
import feedparser
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FEEDS = [
    {"name": "CBA TV",          "url": "https://cbatv.net/feed/"},
    {"name": "Daily Somalia",   "url": "https://dailysomalia.com/feed/"},
    {"name": "Dhacdo",          "url": "https://dhacdo.net/feed/"},
    {"name": "Radio Muqdisho",  "url": "https://radiomuqdisho.so/feed/"},
    {"name": "Radio Dalsan",    "url": "https://www.radiodalsan.com/feed/"},
    {"name": "Radio Ergo",      "url": "https://radioergo.org/feed/"},
    {"name": "Somali Guardian", "url": "https://www.somaliguardian.com/feed/"},
    {"name": "WardheerNews",    "url": "https://wardheernews.com/feed/"},
    {"name": "Somaliweyn",      "url": "https://somaliweyn.org/feed"},
    {"name": "Qaran News",      "url": "https://qarannews.com/feed"},
    {"name": "Caasimada",       "url": "https://caasimada.net/feed"},
    {"name": "Raxanreeb",       "url": "https://www.raxanreeb.com/feed/"},
    {"name": "Goobjoog",        "url": "https://goobjoog.com/feed/"},
    {"name": "Mareeg",          "url": "https://www.mareeg.com/feed/"},
    {"name": "Horseed Media",   "url": "https://horseedmedia.net/category/news/feed/"},
    {"name": "Calamada",        "url": "https://calamada1.com/feed/",
     "flag": "as_aligned", "flagLabel": "AS-aligned"},
]

PRUNE_DAYS = 45
DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "feeds.json"


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_date(entry):
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def fetch_one(feed):
    try:
        parsed = feedparser.parse(feed["url"], request_headers={
            "User-Agent": "Mozilla/5.0 (compatible; SomaliaTracker/1.0; +github-actions)"
        })
    except Exception as e:
        print(f"  !! {feed['name']}: fetch error: {e}", file=sys.stderr)
        return []

    if parsed.bozo and not parsed.entries:
        print(f"  !! {feed['name']}: parse error, {getattr(parsed, 'bozo_exception', 'unknown')}", file=sys.stderr)
        return []

    items = []
    for entry in parsed.entries:
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        description = strip_html(entry.get("summary", "") or entry.get("description", ""))
        full_content = ""
        if "content" in entry and entry.content:
            full_content = strip_html(entry.content[0].get("value", ""))
        pub_date = parse_date(entry)

        items.append({
            "title": title,
            "link": link,
            "description": description if len(description) >= len(full_content) else full_content,
            "fullContent": full_content,
            "pubDate": pub_date,
            "source": feed["name"],
            "flag": feed.get("flag"),
            "flagLabel": feed.get("flagLabel"),
        })
    print(f"  .. {feed['name']}: {len(items)} items")
    return items


def load_existing():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            return {"items": []}
    return {"items": []}


def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it.get("link") or it.get("title", "")).lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def prune(items, days):
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    kept = []
    for it in items:
        try:
            t = datetime.fromisoformat(it["pubDate"].replace("Z", "+00:00")).timestamp()
            if t >= cutoff:
                kept.append(it)
        except Exception:
            kept.append(it)   # keep items with unparseable dates
    return kept


def main():
    DATA_DIR.mkdir(exist_ok=True)
    print(f"Fetching {len(FEEDS)} feeds at {datetime.now(timezone.utc).isoformat()}")

    fresh = []
    for feed in FEEDS:
        fresh.extend(fetch_one(feed))

    existing = load_existing()
    merged = dedupe(fresh + existing.get("items", []))
    merged = prune(merged, PRUNE_DAYS)
    merged.sort(key=lambda x: x.get("pubDate", ""), reverse=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feed_count": len(FEEDS),
        "item_count": len(merged),
        "items": merged,
    }

    DATA_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Wrote {len(merged)} items to {DATA_FILE}")


if __name__ == "__main__":
    main()

"""
Scrape, summarise, and push the result into Redis for the website to serve.

This is what runs on a schedule in the cloud. Nothing here writes HTML - the
website reads the data and renders it, so the dashboard is always as fresh as
the last run.

    python publish.py                 last 7 days
    python publish.py --days 2        just catch up the last couple of days
    python publish.py --dry-run       do the work, print, but don't write

Credentials come from the environment so nothing sensitive lives in the repo:

    KV_REST_API_URL      from Vercel (Storage tab), or UPSTASH_REDIS_REST_URL
    KV_REST_API_TOKEN    from Vercel,               or UPSTASH_REDIS_REST_TOKEN
    GROQ_API_KEY         optional, falls back to config.json
    GEMINI_API_KEY       optional, falls back to config.json

Data layout, one key per day so old days expire on their own:

    mt:day:2026-08-10   ->  JSON list of that day's important filings
    mt:index            ->  JSON list of the days we currently hold
    mt:meta             ->  when it last ran, and what it found
"""

import argparse
import datetime
import json
import os
import sys

import requests

import pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
KEEP_DAYS = 7
TTL_SECONDS = 60 * 60 * 24 * (KEEP_DAYS + 2)      # a little slack past 7 days


# ---------------------------------------------------------------- config

def redis_creds():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    tok = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return url, tok


def load_providers():
    """Prefer environment keys (that's how the cloud gets them), else config.json."""
    groq = os.environ.get("GROQ_API_KEY", "")
    gem = os.environ.get("GEMINI_API_KEY", "")

    cfg = {}
    path = os.path.join(HERE, "config.json")
    if os.path.exists(path):
        try:
            cfg = json.load(open(path, encoding="utf-8"))
        except Exception:
            cfg = {}

    out = []
    for p in cfg.get("providers", []):
        p = dict(p)
        if p.get("kind") == "groq" and groq:
            p["key"] = groq
        if p.get("kind") == "gemini" and gem:
            p["key"] = gem
        if p.get("key") and not p["key"].startswith("PUT_YOUR"):
            out.append(p)

    if not out:                        # no config file at all - build defaults
        if groq:
            out.append({"kind": "groq", "key": groq, "tpm": 8000, "vision": False,
                        "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]})
        if gem:
            out.append({"kind": "gemini", "key": gem, "tpm": 250000, "vision": True,
                        "models": ["gemini-flash-lite-latest", "gemini-3-flash-preview",
                                   "gemini-2.0-flash"]})
    return out


# ---------------------------------------------------------------- redis

def redis(url, token, command):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"},
                      json=command, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Redis {r.status_code}: {r.text[:200]}")
    return r.json().get("result")


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=KEEP_DAYS,
                   help=f"how many days back to scrape (default {KEEP_DAYS})")
    p.add_argument("--min-score", type=int, default=55)
    p.add_argument("--max-summaries", type=int, default=60)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    url, token = redis_creds()
    if not args.dry_run and not (url and token):
        sys.exit("No Redis credentials. Set KV_REST_API_URL and KV_REST_API_TOKEN.")

    provider_list = load_providers()
    print(f"AI providers configured: {[p['kind'] for p in provider_list] or 'none'}\n")

    rows, stats = pipeline.run(
        days=args.days,
        min_score=args.min_score,
        max_summaries=args.max_summaries,
        provider_list=provider_list,
        workers=args.workers,
    )

    # Group by the day the filing was made.
    cutoff = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS - 1)).isoformat()
    by_day = {}
    for r in rows:
        day = r.get("date") or ""
        if day and day >= cutoff:
            by_day.setdefault(day, []).append(r)

    days = sorted(by_day, reverse=True)
    print(f"\nGrouped into {len(days)} days:")
    for d in days:
        n = len(by_day[d])
        s = sum(1 for x in by_day[d] if x.get("summary"))
        print(f"  {d}   {n:>4} important, {s:>3} summarised")

    if args.dry_run:
        print("\n(dry run - nothing written)")
        return

    for d in days:
        redis(url, token, ["SET", f"mt:day:{d}", json.dumps(by_day[d], ensure_ascii=False),
                           "EX", str(TTL_SECONDS)])

    meta = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
        **stats,
    }
    redis(url, token, ["SET", "mt:index", json.dumps(days)])
    redis(url, token, ["SET", "mt:meta", json.dumps(meta, ensure_ascii=False)])

    total = sum(len(v) for v in by_day.values())
    print(f"\nPublished {total} filings across {len(days)} days.")
    print(f"Last updated: {meta['updated']}")


if __name__ == "__main__":
    main()

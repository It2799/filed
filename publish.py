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

# The "All" tab doesn't need summaries or the long headline, and trimming keeps
# a busy day's payload well under Upstash's request size limit.
SLIM_FIELDS = ("id", "exchange", "company", "ticker", "category", "headline",
               "time", "date", "score", "tag", "pdf_url")

MAX_BYTES = 700_000        # stay comfortably inside the REST request limit


def redis(url, token, command):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"},
                      json=command, timeout=90)
    if not r.ok:
        raise RuntimeError(f"Redis {r.status_code}: {r.text[:200]}")
    return r.json().get("result")


def write_day(url, token, key, rows):
    """
    Write one day's rows, splitting into parts if they're too big for a single
    request. A heavy results day can carry over a thousand filings.
    """
    if not rows:
        redis(url, token, ["SET", key, "[]", "EX", str(TTL_SECONDS)])
        return 1

    blob = json.dumps(rows, ensure_ascii=False)
    if len(blob.encode("utf-8")) <= MAX_BYTES:
        redis(url, token, ["SET", key, blob, "EX", str(TTL_SECONDS)])
        redis(url, token, ["SET", key + ":parts", "1", "EX", str(TTL_SECONDS)])
        return 1

    parts = (len(blob.encode("utf-8")) // MAX_BYTES) + 1
    size = (len(rows) // parts) + 1
    chunks = [rows[i:i + size] for i in range(0, len(rows), size)]
    for i, chunk in enumerate(chunks):
        redis(url, token, ["SET", f"{key}:{i}",
                           json.dumps(chunk, ensure_ascii=False), "EX", str(TTL_SECONDS)])
    redis(url, token, ["SET", key + ":parts", str(len(chunks)), "EX", str(TTL_SECONDS)])
    redis(url, token, ["DEL", key])          # the single-blob form is now stale
    return len(chunks)


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=KEEP_DAYS,
                   help=f"how many days back to scrape (default {KEEP_DAYS})")
    p.add_argument("--min-score", type=int, default=20,
                   help="lowest score worth storing at all (feeds the All tab)")
    p.add_argument("--important-at", type=int, default=55,
                   help="score at which a filing counts as Important")
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

    # Two tiers per day, so the dashboard's default view stays small and fast:
    #   mt:day:DATE  the important ones, with their summaries
    #   mt:all:DATE  everything else, trimmed, for the "All" tab
    cutoff = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS - 1)).isoformat()
    important, rest = {}, {}
    for r in rows:
        day = r.get("date") or ""
        if not day or day < cutoff:
            continue
        if r.get("score", 0) >= args.important_at:
            important.setdefault(day, []).append(r)
        else:
            rest.setdefault(day, []).append(
                {k: r.get(k, "") for k in SLIM_FIELDS})

    days = sorted(set(important) | set(rest), reverse=True)
    print(f"\nGrouped into {len(days)} days:")
    for d in days:
        imp = len(important.get(d, []))
        oth = len(rest.get(d, []))
        s = sum(1 for x in important.get(d, []) if x.get("summary"))
        print(f"  {d}   {imp:>4} important ({s:>3} summarised), {oth:>4} other")

    if args.dry_run:
        print("\n(dry run - nothing written)")
        return

    for d in days:
        write_day(url, token, f"mt:day:{d}", important.get(d, []))
        write_day(url, token, f"mt:all:{d}", rest.get(d, []))

    meta = {
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
        "important_at": args.important_at,
        "important": sum(len(v) for v in important.values()),
        "other": sum(len(v) for v in rest.values()),
        **stats,
    }
    redis(url, token, ["SET", "mt:index", json.dumps(days)])
    redis(url, token, ["SET", "mt:meta", json.dumps(meta, ensure_ascii=False)])

    print(f"\nPublished {meta['important']} important + {meta['other']} other "
          f"across {len(days)} days.")
    print(f"Last updated: {meta['updated']}")


if __name__ == "__main__":
    main()

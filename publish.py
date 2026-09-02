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

import dedupe
import mcap
import triage
import pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
KEEP_DAYS = 7

# The exchanges, the filings and the readers are all Indian, but the scheduler
# runs on UTC. Between midnight and 05:30 IST, UTC is still on yesterday's
# date - which built the window a day behind and left today off the dashboard.
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def today_ist():
    return datetime.datetime.now(IST).date()
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
    orouter = os.environ.get("OPENROUTER_API_KEY", "")

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
        if p.get("kind") == "openrouter" and orouter:
            p["key"] = orouter
        if p.get("key") and not p["key"].startswith("PUT_YOUR"):
            out.append(p)

    if not out:                        # no config file at all - build defaults
        if groq:
            out.append({"kind": "groq", "key": groq, "tpm": 8000, "vision": False,
                        "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]})
        if gem:
            # Gemini's free tier allows 500 requests a day PER MODEL, so the
            # length of this list is the daily ceiling: five models is 2,500
            # summaries, two was 1,000 and ran out halfway through a backfill.
            # gemini-2.0-flash was retired by Google and 404s on every call.
            out.append({"kind": "gemini", "key": gem, "tpm": 250000, "vision": True,
                        "models": ["gemini-3.6-flash", "gemini-3.5-flash",
                                   "gemini-3.1-flash-lite",
                                   "gemini-flash-lite-latest",
                                   "gemini-3-flash-preview"]})
        if orouter:
            # Free models, checked to return valid JSON against our schema.
            out.append({"kind": "openrouter", "key": orouter, "tpm": 60000,
                        "vision": False,
                        "models": ["dots-studio/dots-3-note-preview:free",
                                   "z-ai/glm-5.2:free",
                                   "google/gemma-4-31b-it:free",
                                   "google/gemma-4-26b-a4b-it:free"]})
    return out


# ---------------------------------------------------------------- redis

# The "All" tab doesn't need summaries or the long headline, and trimming keeps
# a busy day's payload well under Upstash's request size limit.
SLIM_FIELDS = ("id", "exchange", "company", "ticker", "category", "headline",
               "time", "date", "score", "tag", "pdf_url", "mcap")

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




def publish_index(url, token, today, run_stats):
    """
    Rebuild the day index and the headline figures from what is genuinely in
    the store. Called after every day so the site keeps pace with the work.
    Returns (days, totals).
    """
    window = [(today - datetime.timedelta(days=i)).isoformat()
              for i in range(KEEP_DAYS)]
    marks = redis(url, token, ["MGET", *[f"mt:count:{d}" for d in window]]) or []

    live_days, totals = [], {"important": 0, "other": 0, "summarised": 0,
                            "scanned": 0, "read": 0}
    for d, mark in zip(window, marks):
        if not mark:
            continue
        live_days.append(d)
        try:
            c = json.loads(mark)
            for k in totals:
                totals[k] += int(c.get(k) or 0)
        except Exception:
            pass

    meta = {
        # Run tallies first, then the window-wide totals on top - the whole
        # week is what the dashboard claims to describe, so the week wins.
        **run_stats,
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": live_days,
        # Days written before per-day tallies existed carry none, and a zero
        # there would blank the headline rather than correct it. So a summed
        # figure only replaces the run's own when it actually adds up to
        # something.
        **{k: v for k, v in totals.items() if v},
    }
    redis(url, token, ["SET", "mt:index", json.dumps(live_days)])
    redis(url, token, ["SET", "mt:meta", json.dumps(meta, ensure_ascii=False)])
    return live_days, totals


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=KEEP_DAYS,
                   help=f"how many days back to scrape (default {KEEP_DAYS})")
    p.add_argument("--min-score", type=int, default=0,
                   help="lowest score worth storing. 0 keeps everything, which "
                        "is what triage needs - a filing scoring 18 on its "
                        "headline can turn out to be a chief executive resigning.")
    p.add_argument("--important-at", type=int, default=55,
                   help="score at which a filing counts as Important")
    p.add_argument("--max-summaries", type=int, default=0,
                   help="0 means summarise every important filing. Set a number "
                        "only if you want to cap AI calls for a run. Summaries "
                        "are cached, so a rerun only pays for what is new.")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--force", action="store_true",
                   help="overwrite a day even if the stored one is fuller")
    # Reading PDFs is waiting on a download, not on a model, so it can run
    # far wider than summarising - which has a rate limit to respect.
    p.add_argument("--read-workers", type=int, default=0,
                   help="threads for downloading PDFs (default: 3x --workers)")
    p.add_argument("--no-mcap", action="store_true",
                   help="skip the market-cap lookup")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    url, token = redis_creds()
    if not args.dry_run and not (url and token):
        sys.exit("No Redis credentials. Set KV_REST_API_URL and KV_REST_API_TOKEN.")

    provider_list = load_providers()
    print(f"Reading PDFs on {args.read_workers or max(1, args.workers) * 3} threads, summarising on {args.workers}")
    print(f"AI providers configured: {[p['kind'] for p in provider_list] or 'none'}\n")

    today = today_ist()
    first = today - datetime.timedelta(days=max(0, args.days))
    cutoff = (today - datetime.timedelta(days=KEEP_DAYS - 1)).isoformat()

    # Work newest day first and publish each one the moment it is finished,
    # rather than doing everything and writing at the end. A full read of a
    # week takes the better part of an hour; publishing only at the end meant
    # nothing appeared for that whole time, and a cancelled run threw away
    # every bit of it. Today's filings now land within a couple of minutes.
    day_list = [today - datetime.timedelta(days=k)
                for k in range((today - first).days + 1)]

    read_workers = args.read_workers or max(1, args.workers) * 3

    run = {"scanned": 0, "stored": 0, "read": 0, "promoted": 0, "summarised": 0}

    for n, day in enumerate(day_list, 1):
        iso = day.isoformat()
        if iso < cutoff:
            continue
        print("=" * 62)
        print(f"DAY {n}/{len(day_list)}   {iso}")
        print("=" * 62)

        raw, kept = pipeline.fetch_and_score(day, day, args.min_score)
        kept = dedupe.collapse(kept)
        triage.triage(kept, important_at=args.important_at, workers=read_workers)
        tri = getattr(triage, "last_stats", {"read": 0, "promoted": 0})

        # Reading the PDFs re-labels filings, which can reveal that two entries
        # sitting under different tags were the same event all along. So the
        # duplicate check runs again now that the tags are trustworthy.
        kept = dedupe.collapse(kept)

        worth = [a for a in kept if a.get("score", 0) >= args.important_at]
        cap = args.max_summaries or len(worth)
        print(f"{len(kept)} stored, {len(worth)} relevant. Summarising "
              + ("all." if not args.max_summaries else f"up to {cap}."))
        pipeline.summarise(worth, provider_list, cap, workers=args.workers)

        if not args.no_mcap:
            mcap.attach(kept, workers=read_workers)

        rows = pipeline.to_rows(kept)

        # Worth reading means summarised - the two are the same set, so the
        # dashboard can never show one number for what matters and a smaller
        # one for what was explained. A filing we genuinely could not read
        # (a scan no model could see through) is not shown as a headline item
        # with a blank where its summary belongs; it drops to the full list.
        def is_headline(r):
            return r.get("score", 0) >= args.important_at and r.get("summary")

        important = [r for r in rows if is_headline(r)]
        rest = [{k: r.get(k, "") for k in SLIM_FIELDS}
                for r in rows if not is_headline(r)]
        done = len(important)

        run["scanned"] += len(raw)
        run["stored"] += len(kept)
        run["read"] += tri.get("read", 0)
        run["promoted"] += tri.get("promoted", 0)
        run["summarised"] += done

        print(f"  -> {len(important)} important ({done} summarised), {len(rest)} other")

        if args.dry_run:
            continue

        # A day that is already richer than what this run produced is left
        # alone. Summaries depend on a daily AI quota, and a run that starts
        # after that quota is spent will summarise almost nothing - without
        # this guard the nightly full pass would overwrite a complete day with
        # a threadbare one, and a week of reading would be gone. Growth is
        # always allowed; only a large drop is refused.
        held = redis(url, token, ["GET", f"mt:count:{iso}"])
        if held and not args.force:
            try:
                mark = json.loads(held)
                was = int(mark.get("important") or 0)
                was_rules = mark.get("rules") or ""
            except Exception:
                was, was_rules = 0, ""

            # The guard exists so a starved run - NSE down, quota gone - cannot
            # replace a full day with half of one. But a rules change also
            # lowers the count, on purpose: fixing a rule that wrongly promoted
            # filings means fewer of them, and that is the whole point.
            #
            # Told apart by the rules fingerprint stored with the day. Same
            # rules and far fewer filings means something went wrong. Different
            # rules means the drop was intended, and refusing it would freeze
            # every correction out of the site - which is exactly what happened
            # to 30 August, where an AGM notice sat under Acquisition through
            # four passes because each one produced 7 filings where the old
            # rules had produced 14.
            rules_changed = was_rules and was_rules != triage.rules_fingerprint()
            if was and len(important) < was * 0.7 and not rules_changed:
                print(f"  -> KEPT the stored day: it has {was} summarised, "
                      f"this run only managed {len(important)}. "
                      f"Re-run with --force to overwrite anyway.")
                continue
            if rules_changed and len(important) < was * 0.7:
                print(f"  -> the rules changed since this day was written "
                      f"({was} -> {len(important)}); publishing the new verdict")

        write_day(url, token, f"mt:day:{iso}", important)
        write_day(url, token, f"mt:all:{iso}", rest)
        redis(url, token, ["SET", f"mt:count:{iso}", json.dumps({
            "important": len(important), "other": len(rest), "summarised": done,
            # Per-day, so the headline figures describe the whole week rather
            # than whichever days the last run happened to touch. A 45-minute
            # top-up scrapes one day; without this it would report that day's
            # filing count as the week's.
            "scanned": len(raw), "read": tri.get("read", 0),
            # Which rules produced these numbers, so the guard above can tell a
            # deliberate drop from a starved one.
            "rules": triage.rules_fingerprint(),
        }), "EX", str(TTL_SECONDS)])

        publish_index(url, token, today, run)
        print(f"  -> published. The dashboard is showing {iso} now.")

    if args.dry_run:
        print("(dry run - nothing written)")
        return

    live_days, totals = publish_index(url, token, today, run)

    span = f"{live_days[-1]} to {live_days[0]}" if live_days else "nothing"
    print("")
    print(f"Index now lists {len(live_days)} days ({span})")
    print(f"Holding {totals['important']} important + {totals['other']} other, "
          f"{totals['summarised']} summarised.")
    print(f"This run read {run['read']} PDFs and rescued {run['promoted']} "
          f"that the headline had buried.")


if __name__ == "__main__":
    main()

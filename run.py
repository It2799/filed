"""
NSE + BSE corporate announcement filter.

  python run.py                 today's important announcements
  python run.py --days 3        last 3 days
  python run.py --min-score 55  only the really big stuff
  python run.py --no-summary    skip Gemini, just filter (free and instant)

Writes dashboard.html next to this file and opens it.
"""

import argparse
import concurrent.futures as cf
import datetime
import json
import os
import sys
import threading
import webbrowser

import dashboard
import providers
import rules
import sources
import summarize

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
CACHE = os.path.join(HERE, "cache.json")
OUT = os.path.join(HERE, "dashboard.html")

_print_lock = threading.Lock()


def say(msg):
    with _print_lock:
        print(msg, flush=True)


def pick_for_summary(items, n):
    """
    Choose which filings get an AI summary.

    Straight top-N by score would hand every slot to whichever tag scores
    highest that day (usually M&A) and leave results and order wins with none.
    So we go round the tags in turn, taking each tag's best remaining filing,
    until we hit the budget.
    """
    buckets = {}
    for a in items:
        buckets.setdefault(a["tag"], []).append(a)

    order = sorted(buckets, key=lambda t: -max(x["score"] for x in buckets[t]))
    chosen, i = [], 0
    while len(chosen) < n and any(buckets.values()):
        tag = order[i % len(order)]
        if buckets[tag]:
            chosen.append(buckets[tag].pop(0))
        i += 1
        if i > len(order) * (n + 5):
            break
    return chosen


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    cfg = load_json(CONFIG, {})
    if not cfg:
        sys.exit("config.json is missing or invalid.")

    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=cfg.get("days_back", 0),
                   help="how many days back to include (0 = today only)")
    p.add_argument("--min-score", type=int, default=cfg.get("min_score", 45))
    p.add_argument("--max-summaries", type=int, default=cfg.get("max_summaries", 40))
    p.add_argument("--workers", type=int, default=cfg.get("workers", 4))
    p.add_argument("--no-summary", action="store_true", help="skip the AI step")
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args()

    today = datetime.date.today()
    start = today - datetime.timedelta(days=max(0, args.days))

    label = today.strftime("%d %b %Y") if start == today else \
        f"{start.strftime('%d %b')} to {today.strftime('%d %b %Y')}"
    print(f"Announcements for {label}\n")

    # 1. fetch -------------------------------------------------------------
    print("Fetching BSE...")
    bse = sources.fetch_bse(start, today, log=say)
    print("Fetching NSE...")
    nse = sources.fetch_nse(start, today, log=say)

    raw = bse + nse
    print(f"\nTotal filings pulled: {len(raw)}")
    if not raw:
        print("Nothing came back. Markets may be shut, or the sites are blocking us.")

    # 2. score and filter --------------------------------------------------
    kept = []
    for a in raw:
        s, tag = rules.score(a["category"], a["headline"], a.get("critical"))
        a["score"], a["tag"] = s, tag
        if s >= args.min_score:
            kept.append(a)

    kept = sources.merge(kept)

    def sort_key(a):
        d = sources.parse_dt(a["dt"])
        return (-a["score"], -(d.timestamp() if d else 0))

    kept.sort(key=sort_key)
    print(f"Important after filtering: {len(kept)}")

    for a in kept:
        d = sources.parse_dt(a["dt"])
        a["time"] = d.strftime("%d %b, %H:%M") if d else ""

    # 3. summarise ---------------------------------------------------------
    provider_list = [p for p in cfg.get("providers", []) if p.get("key")]
    todo = pick_for_summary(kept, args.max_summaries)

    if args.no_summary or not provider_list:
        if not provider_list and not args.no_summary:
            print("No AI providers configured in config.json - skipping summaries.")
        todo = []
    elif len(kept) > len(todo):
        print(f"Summarising {len(todo)} of them, spread across categories "
              f"(raise max_summaries for more).")

    cache = load_json(CACHE, {})
    done = [0]

    def work(a):
        if a["id"] in cache:
            a.update(cache[a["id"]])
            with _print_lock:
                done[0] += 1
                print(f"  [{done[0]}/{len(todo)}] cached  {a['company'][:44]}")
            return
        res = summarize.summarize(a, provider_list)
        if "error" in res:
            a["summary"] = "Could not summarise: " + str(res["error"])[:160]
            a["impact"] = ""
            a["key_numbers"] = []
            a["why_it_matters"] = ""
            note = "FAILED"
        else:
            a["summary"] = res.get("summary", "")
            a["impact"] = res.get("impact", "")
            a["key_numbers"] = res.get("key_numbers", [])
            a["why_it_matters"] = res.get("why_it_matters", "")
            cache[a["id"]] = {k: a[k] for k in
                              ("summary", "impact", "key_numbers", "why_it_matters", "source_used")}
            note = a.get("source_used", "")
        with _print_lock:
            done[0] += 1
            print(f"  [{done[0]}/{len(todo)}] {note:<16} {a['company'][:44]}")

    if todo:
        print(f"\nReading {len(todo)} PDFs and summarising...")
        with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            list(ex.map(work, todo))
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)

        used = providers.report()
        if used:
            print("\nWho did the work:")
            for model, n in sorted(used.items(), key=lambda x: -x[1]):
                print(f"  {n:4d}  {model}")
        if providers.dead():
            print("\nOut of free quota for today: " + ", ".join(providers.dead())
                  + "\nSummaries already made are cached, so re-running is free.")

    # 4. render ------------------------------------------------------------
    fields = ("id", "exchange", "company", "ticker", "category", "headline", "time",
              "score", "tag", "pdf_url", "page_url", "summary", "impact",
              "key_numbers", "why_it_matters")
    rows = [{k: a.get(k, "") for k in fields} for a in kept]

    dashboard.render(OUT, rows, {
        "window": label,
        "total": len(raw),
        "built": datetime.datetime.now().strftime("%d %b %H:%M"),
    })
    print(f"\nDashboard: {OUT}")

    if not args.no_open and cfg.get("open_browser", True):
        webbrowser.open("file:///" + OUT.replace("\\", "/"))


if __name__ == "__main__":
    main()

"""
The scrape-score-summarise pipeline, with no assumptions about where the
result goes.

run.py uses it to build the local HTML dashboard. publish.py uses it to push
the same data to Redis so the website can serve it. Keeping this in one place
means the live site and your local dashboard can never drift apart.
"""

import concurrent.futures as cf
import datetime
import json
import os
import threading

import providers
import rules
import sources
import summarize

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache.json")

_lock = threading.Lock()


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CACHE)


def spread_across_tags(items, n):
    """
    Choose which filings get an AI summary.

    Straight top-N by score hands every slot to whichever tag scores highest
    that day (usually M&A) and leaves results and order wins with none. So we
    go round the tags in turn, taking each tag's best remaining filing.
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


def fetch_and_score(start, end, min_score, log=print):
    """Everything up to but not including the AI step."""
    log("Fetching BSE...")
    bse = sources.fetch_bse(start, end, log=log)
    log("Fetching NSE...")
    nse = sources.fetch_nse(start, end, log=log)

    raw = bse + nse
    log(f"Total filings pulled: {len(raw)}")

    kept = []
    for a in raw:
        s, tag = rules.score(a["category"], a["headline"], a.get("critical"))
        a["score"], a["tag"] = s, tag
        if s >= min_score:
            kept.append(a)

    kept = sources.merge(kept)

    def sort_key(a):
        d = sources.parse_dt(a["dt"])
        return (-a["score"], -(d.timestamp() if d else 0))

    kept.sort(key=sort_key)

    for a in kept:
        d = sources.parse_dt(a["dt"])
        a["time"] = d.strftime("%d %b, %H:%M") if d else ""
        a["date"] = d.strftime("%Y-%m-%d") if d else ""

    log(f"Important after filtering: {len(kept)}")
    return raw, kept


def summarise(kept, provider_list, max_summaries, workers=4, log=print):
    """Read PDFs and summarise a spread of the most important filings."""
    todo = spread_across_tags(kept, max_summaries)
    if not provider_list or not todo:
        return []

    cache = load_cache()
    done = [0]

    def work(a):
        if a["id"] in cache:
            a.update(cache[a["id"]])
            with _lock:
                done[0] += 1
                log(f"  [{done[0]}/{len(todo)}] cached  {a['company'][:42]}")
            return

        res = summarize.summarize(a, provider_list)
        if "error" in res:
            a["summary"] = ""
            a["summary_error"] = str(res["error"])[:160]
            a["impact"] = ""
            a["key_numbers"] = []
            a["why_it_matters"] = ""
            note = "FAILED"
        else:
            a["summary"] = res.get("summary", "")
            a["impact"] = res.get("impact", "")
            a["key_numbers"] = res.get("key_numbers", [])
            a["why_it_matters"] = res.get("why_it_matters", "")
            with _lock:
                cache[a["id"]] = {k: a[k] for k in
                                  ("summary", "impact", "key_numbers",
                                   "why_it_matters", "source_used")}
            note = a.get("source_used", "")
        with _lock:
            done[0] += 1
            log(f"  [{done[0]}/{len(todo)}] {note:<16} {a['company'][:42]}")

    log(f"Reading {len(todo)} PDFs and summarising...")
    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(work, todo))
    save_cache(cache)

    # Correct labels now the PDFs have actually been read. A "Receipt of Order"
    # filing that turns out to be a tax demand should not sit under Order Win.
    fixed = 0
    for a in todo:
        better = rules.retag(
            (a.get("summary") or "") + " " + " ".join(a.get("key_numbers") or []))
        if better and better != a["tag"]:
            log(f"  relabelled: {a['company'][:36]}  {a['tag']} -> {better}")
            a["tag"] = better
            fixed += 1
    if fixed:
        log(f"  ({fixed} corrected after reading the document)")

    return todo


FIELDS = ("id", "exchange", "company", "ticker", "category", "headline", "time",
          "date", "score", "tag", "pdf_url", "page_url", "summary", "impact",
          "key_numbers", "why_it_matters", "mcap", "also_filed", "also_tags")


def to_rows(kept):
    """Trim to the fields the dashboard and the Excel export actually use."""
    return [{k: a.get(k, "") for k in FIELDS} for a in kept]


def run(days, min_score, max_summaries, provider_list, workers=4, log=print):
    """Full pipeline. Returns (rows, stats)."""
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    today = datetime.datetime.now(ist).date()
    start = today - datetime.timedelta(days=max(0, days))

    raw, kept = fetch_and_score(start, today, min_score, log=log)
    summarise(kept, provider_list, max_summaries, workers=workers, log=log)

    stats = {
        "scanned": len(raw),
        "important": len(kept),
        "summarised": sum(1 for a in kept if a.get("summary")),
        "from": start.isoformat(),
        "to": today.isoformat(),
    }
    return to_rows(kept), stats

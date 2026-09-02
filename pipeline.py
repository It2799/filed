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
import numfmt
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
    # Everything worth reading gets a summary. There is no second tier - if a
    # filing is good enough to show, it is good enough to explain. The spread
    # only decides the ORDER when a cap is in force; with no cap it is the
    # whole list, best first.
    if not max_summaries or max_summaries >= len(kept):
        todo = sorted(kept, key=lambda a: -a.get("score", 0))
    else:
        todo = spread_across_tags(kept, max_summaries)
    if not provider_list or not todo:
        return []

    cache = load_cache()
    done = [0]
    fail_reason = [""]        # the last error, for the log line at the end

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
            fail_reason[0] = a["summary_error"]
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

    # A rate limit or a timeout is not a verdict on the filing, so anything
    # still without a summary goes round again. Two extra passes is enough to
    # clear a transient failure without grinding on a PDF that cannot be read.
    #
    # But only while there is something left to ask. Once every model has hit
    # its daily cap, a retry cannot succeed, and three passes over a few
    # hundred filings is how one run spent 2h17m on a single day and held the
    # schedule for five and a half hours. The run carries on either way and
    # publishes what it has - a missing summary is not a reason to fail.
    for attempt in (1, 2):
        missing = [a for a in todo if not a.get("summary")]
        if not missing:
            break
        left = providers.alive(provider_list)
        if not left:
            log(f"Retry {attempt}: skipped - every model has used up its quota "
                f"for today ({len(missing)} filings left unsummarised)")
            break
        log(f"Retry {attempt}: {len(missing)} filings still need a summary "
            f"({len(left)} models still available)")
        done[0] = 0
        with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            list(ex.map(work, missing))

    still = [a for a in todo if not a.get("summary")]
    if still:
        log(f"  {len(still)} could not be summarised. Last reason: "
            f"{fail_reason[0] or 'unknown'}")
        gone = providers.dead_models()
        if gone:
            log(f"  models out of quota for today: {', '.join(gone)}")
    save_cache(cache)

    # ---------------------------------------------------------------------
    # The category comes from the SUMMARY, not the document.
    #
    # A filing's PDF is not one statement. It is a document containing many
    # sentences about many things, and scoring 4,000 characters of it means
    # any topic word anywhere decides the label. Every wrong category on the
    # site came from a phrase that belonged to a different sentence: an
    # auditor's list of services ("Merger & Acquisition"), a blank SAST form's
    # own options ("rights issue / preferential allotment"), the other side's
    # name in a lawsuit ("Joint Venture of OHL"), a trading-window paragraph,
    # a website breadcrumb. There is no end to that supply, and patching them
    # one at a time never finishes.
    #
    # The summary is two sentences saying what the filing IS, with none of
    # that in it. Measured over the 1,199 filings live on 1 September: 146
    # carried a category their own summary contradicted; scoring the summary
    # instead leaves 5.
    #
    # The score is NOT changed. Importance was already decided, by the rules
    # and the document, and a filing that earned its place keeps it - this
    # only settles what to call it. Filings without a summary keep the tag the
    # rules gave them, which is the only thing available for them anyway.
    # ---------------------------------------------------------------------
    fixed = 0
    for a in todo:
        blob = " ".join([
            a.get("summary") or "",
            " ".join(a.get("key_numbers") or []),
            a.get("why_it_matters") or "",
        ]).strip()
        if not blob:
            continue

        # Two things the summary must not be allowed to decide.
        #
        # The three meeting kinds are settled from the category and headline,
        # and they are already right - Investor Meet is 1% wrong, Concall 0%.
        # Their summaries describe what was DISCUSSED on the call, which is
        # usually the quarter's results, so scoring them moved 17 concalls and
        # investor meets into Results.
        if a.get("tag") in rules._MEETING_TAGS:
            continue

        pts, from_summary = rules.score_text(blob, floor=0)

        # And it must not push a filing below the bar. Importance was decided
        # already; a dividend whose summary mentions the AGM that will approve
        # it is still a dividend, and 14 of them were being relabelled
        # "Meeting" - a tag worth 22, which would have dropped them off the
        # page entirely.
        if pts < 55:
            from_summary = None

        # retag() still has the last word. It exists for the cases where the
        # words are right but the meaning is inverted - a tax demand and an
        # order win are both "receipt of order".
        better = rules.retag(blob) or from_summary

        if better and better != a["tag"]:
            log(f"  relabelled: {a['company'][:36]:<38} "
                f"{a['tag']} -> {better}")
            a["tag"] = better
            fixed += 1
    if fixed:
        log(f"  ({fixed} categories taken from the summary rather than the document)")

    return todo


FIELDS = ("id", "exchange", "company", "ticker", "category", "headline", "time",
          "date", "score", "tag", "pdf_url", "page_url", "summary", "impact",
          "key_numbers", "why_it_matters", "mcap", "also_filed", "also_tags")


def to_rows(kept):
    """Trim to the fields the dashboard and the Excel export actually use."""
    # Figures get tidied on the way out rather than at summarising time, so a
    # summary that has been sitting in the cache since before this existed is
    # corrected too, without paying to generate it again.
    return [numfmt.fix_all({k: a.get(k, "") for k in FIELDS}) for a in kept]


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

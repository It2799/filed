"""
Read every filing's PDF before deciding whether it matters.

Exchange headlines routinely say nothing. "Announcement under Regulation 30
(LODR)-Press Release / Media Release" is what a company files for a Rs 260
crore acquisition; "Disclosure Under Regulation 30" is what a bank files when
its chief executive retires; "General Updates" is what a company files when it
opens a new plant. Judged on the headline, all three score 18 and disappear.

So nothing is judged on its headline any more. Every filing we hold gets its
PDF downloaded and its text scored, and whatever turns out to be substantive is
promoted. It costs no AI - a download and a regex - and results are cached by
filing id, so a filing is only ever read once no matter how many times the
scraper runs over the same day.

The one thing a document cannot do is promote itself out of the hard-junk
categories. A newspaper clipping of a buyback notice is still a clipping; the
buyback itself is filed separately and gets found on its own.
"""

import concurrent.futures as cf
import json
import os
import threading

import rules
import summarize

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "triage.json")

_lock = threading.Lock()

# These categories are duplicates or compliance boilerplate by definition. We
# still read them, but reading cannot rescue them.
NEVER_PROMOTE = rules.JUNK


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, CACHE)


def _blocked(rec):
    import re
    blob = f"{rec.get('category','')} || {rec.get('headline','')}"
    return any(re.search(p, blob, re.I) for p in NEVER_PROMOTE)


def triage(records, important_at=55, workers=8, log=print):
    """Read every filing that hasn't already cleared the bar. Mutates records."""
    cache = load_cache()

    todo, from_cache = [], 0
    for r in records:
        if r.get("score", 0) >= important_at:
            continue                       # already in, no need to re-read
        if not r.get("pdf_url"):
            continue
        hit = cache.get(r["id"])
        if hit is not None:
            from_cache += 1
            if hit:                        # {} means "read it, nothing there"
                r["score"], r["tag"] = hit["s"], hit["t"]
                r["promoted"] = True
            continue
        todo.append(r)

    log(f"Triage: {len(todo)} filings to read "
        f"({from_cache} already read in an earlier run)")

    if not todo:
        return records

    promoted, done = [0], [0]

    def look(rec):
        try:
            blob = summarize.fetch_pdf(rec)
            text = summarize.pdf_text(blob) if blob else ""
        except Exception:
            text = ""

        result = {}
        if len(text) >= 200 and not _blocked(rec):
            score, tag = rules.score_text(text, floor=important_at)
            if score:
                result = {"s": score, "t": tag}

        with _lock:
            done[0] += 1
            # Only cache a definite answer. An empty read may be a scan or a
            # network blip, and caching that would bury the filing for good.
            if text:
                cache[rec["id"]] = result
            if result:
                promoted[0] += 1
                log(f"  promoted: {rec['company'][:34]:<36} "
                    f"{rec['tag']}({rec['score']}) -> {result['t']}({result['s']})")
            if done[0] % 250 == 0:
                log(f"  ...read {done[0]}/{len(todo)}")

        if result:
            rec["score"], rec["tag"] = result["s"], result["t"]
            rec["promoted"] = True

    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(look, todo))

    save_cache(cache)
    log(f"Triage: read {done[0]}, promoted {promoted[0]} that the headline had buried")
    return records

"""
Read the PDF before deciding whether a filing matters.

Exchange headlines routinely say nothing. "Announcement under Regulation 30
(LODR)-Press Release / Media Release" is what a company files for a Rs 260
crore acquisition, and "Disclosure Under Regulation 30" is what a bank files
when its chief executive is retiring. Scoring those on the headline alone puts
them below the line and they never reach the dashboard.

So: for every filing that did NOT clear the bar on its headline, download the
PDF, pull the text out, and score that instead. Anything that turns out to be
substantive gets promoted.

This costs nothing but time - it is a download and a regex, no AI - and it runs
before the summarising step, so a promoted filing gets summarised like any
other.
"""

import concurrent.futures as cf
import threading

import rules
import summarize

_lock = threading.Lock()

# Categories whose headline is worth distrusting. These are the buckets the
# exchanges use when a company has not said what the filing is about.
WORTH_A_LOOK_FROM = 15          # below this it is genuine paperwork


def triage(records, important_at=55, workers=8, log=print):
    """
    Promote filings whose PDF turns out to matter. Mutates and returns records.
    """
    candidates = [
        r for r in records
        if WORTH_A_LOOK_FROM <= r.get("score", 0) < important_at and r.get("pdf_url")
    ]

    if not candidates:
        log("Triage: nothing to re-read")
        return records

    log(f"Triage: re-reading {len(candidates)} filings whose headline said little")

    promoted = [0]
    done = [0]

    def look(rec):
        try:
            blob = summarize.fetch_pdf(rec)
            text = summarize.pdf_text(blob) if blob else ""
        except Exception:
            text = ""

        with _lock:
            done[0] += 1
            if done[0] % 200 == 0:
                log(f"  ...{done[0]}/{len(candidates)}")

        if len(text) < 200:
            return                      # scanned or empty; leave it where it is

        score, tag = rules.score_text(text, floor=important_at)
        if not score:
            return

        with _lock:
            promoted[0] += 1
            log(f"  promoted: {rec['company'][:34]:<36} "
                f"{rec['tag']}({rec['score']}) -> {tag}({score})")
        rec["score"] = score
        rec["tag"] = tag
        rec["promoted"] = True

    with cf.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        list(ex.map(look, candidates))

    log(f"Triage: {promoted[0]} filings promoted after reading the document")
    return records

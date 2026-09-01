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
import hashlib
import json
import os
import threading

import rules
import summarize

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "triage.json")

_lock = threading.Lock()

# What the last run did, so the dashboard can report it.
last_stats = {"read": 0, "promoted": 0}

# Read everything. The only filings a document cannot rescue are the ones that
# are duplicates of another filing, or pure register-keeping - a newspaper
# clipping of a buyback notice is a clipping, and the buyback itself is filed
# separately and gets found on its own. Everything else is judged on what the
# PDF actually says, whatever the headline claimed.
NEVER_PROMOTE = [
    r"newspaper (publication|advertisement|clipping)|copy of newspaper|publication in newspaper",
    r"trading window|closure of trading",
    r"loss of (share )?certificate|duplicate (share )?certificate|issue of duplicate",
    r"reconciliation of share capital",
    r"shareholding pattern",
    r"investor complaint|grievance redressal",
    r"\biepf\b|unclaimed (dividend|share)",

    # A scrutinizer's report quotes every resolution it counted votes on, so
    # reading one finds whatever the meeting decided and promotes the report
    # rather than the decision. The AGM and annual-report cases that used to
    # sit here have moved to NEVER_PROMOTE_CATEGORY below - matched against
    # the category only, because on the headline they caught real news that
    # merely mentioned a meeting.
    r"scrutinizer|voting result",
]

# Matched against the CATEGORY ALONE, never the headline.
#
# These are categories that already say exactly what the filing is. Reading the
# document cannot improve on them and routinely makes them worse, because the
# attachment carries material that has nothing to do with the event: an
# auditor's appointment letter includes the firm's profile, and one of those
# listed "Merger & Acquisition" among its service lines - enough to publish a
# statutory auditor's appointment as a Rs 45 crore company's acquisition.
#
# Category only, because the headline is not evidence of the same thing. On the
# first attempt these were matched against both, and "Updation of Order from
# NCLT for AGM" - a court order, which is news - was blocked for containing the
# letters AGM. Twenty-five vague-category filings were caught that way.
#
# Vague categories are deliberately absent. "Outcome of Board Meeting" still
# gets read: that is the entire point of triage, and the document is the only
# thing that can say what happened.
NEVER_PROMOTE_CATEGORY = [
    r"annual general meeting|\bagm\b|\begm\b|shareholders meeting|postal ballot",
    r"annual report",
    r"appointment of (statutory|internal|secretarial|cost) auditor|"
    r"statutory auditor|secretarial auditor|cost auditor",
    r"change in director|resignation of|appointment of (director|"
    r"company secretary|chief|additional director|independent director)",
    # Record date and book closure are NOT here. They name a corporate action
    # without saying which one, and the document is the only thing that says
    # whether it is a dividend, a bonus or a split - rules.py treats them as
    # vague for exactly that reason. Blocking them would have silenced 98
    # filings that triage exists to read.
]


def rules_fingerprint():
    """A short hash of the scoring rules, so the cache knows when they change.

    A cached {} means "read this PDF, found nothing worth promoting" - an
    answer that is only true for the rules that produced it. Keyed on the
    filing id alone, editing rules.py changed nothing: every filing already
    read stayed buried under the old verdict for ever. The promotions are
    still valid whatever the rules say, so only the negatives are reconsidered.
    """
    blob = repr([rules.JUNK, rules.VAGUE, rules.TOPICS,
                 rules.DOWNGRADE, rules.RETAG])
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def load_cache(log=print):
    try:
        with open(CACHE, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}

    entries = raw.get("e", raw) if isinstance(raw, dict) else {}
    if raw.get("v") == rules_fingerprint():
        return entries

    # The rules changed, so some cached verdicts are stale. The PROMOTIONS are
    # the ones to doubt: every wrong category on the site got there by this
    # function deciding a document was an acquisition, and a rules change is
    # usually a change to what counts as one. The negatives - "read it, found
    # nothing" - stay, because they are four times as numerous and far likelier
    # to still be true. Re-reading 1,500 documents is fifteen minutes; re-reading
    # all 7,000 is over an hour, and the schedule cannot afford it.
    kept = {k: v for k, v in entries.items() if not v}
    dropped = len(entries) - len(kept)
    if dropped:
        log(f"Triage: the scoring rules changed - {dropped} promotions will be "
            f"re-read and re-judged ({len(kept)} 'nothing there' verdicts kept)")
    return kept


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"v": rules_fingerprint(), "e": cache}, f,
                  ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, CACHE)


def _blocked(rec):
    import re
    cat = rec.get("category", "") or ""
    blob = f"{cat} || {rec.get('headline','')}"
    if any(re.search(p, cat, re.I) for p in NEVER_PROMOTE_CATEGORY):
        return True
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
        if _blocked(r):
            continue                       # its category already says what it is

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

    stats = {"read": from_cache, "promoted": 0}
    if not todo:
        globals()['last_stats'] = stats
        return records

    promoted, done = [0], [0]

    def look(rec):
        try:
            blob = summarize.fetch_pdf(rec)
            text = summarize.pdf_text(blob) if blob else ""
        except Exception:
            text = ""

        readable = len(text) >= 200
        result = {}
        if readable and not _blocked(rec):
            score, tag = rules.score_text(text, floor=important_at)
            if score:
                result = {"s": score, "t": tag}

        with _lock:
            done[0] += 1
            # Only cache a definite answer, and "definite" means we actually
            # scored the text - not merely that some text came back. The gate
            # here used to be `if text`, one character's worth of difference
            # from the `>= 200` above: a scan with a 40-character text layer
            # was never scored, yet was written down as "nothing here" and so
            # never read again. That is the outcome this comment warns about.
            if readable:
                cache[rec["id"]] = result
            # Flush periodically. An hour of reading was lost once because the
            # cache was only written at the end and the job was cancelled.
            if done[0] % 100 == 0:
                try:
                    save_cache(cache)
                except Exception:
                    pass
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
    stats["read"] = from_cache + done[0]
    stats["promoted"] = promoted[0]
    globals()['last_stats'] = stats
    log(f"Triage: read {done[0]}, promoted {promoted[0]} that the headline had buried")
    return records

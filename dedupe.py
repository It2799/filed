"""
Collapse the same event filed several times into one entry.

The genuine duplicate is a quarterly result. It arrives the same day as the
board-meeting outcome, a press release, an investor presentation and a concall
intimation - four filings, one piece of news - and again on the second
exchange. Left alone it fills the dashboard and the AI summarises it four times.

Everything else only merges with its own kind. An earlier version lumped QIPs,
preferential issues, warrants and fund raising into one bucket, which meant a
company doing a QIP and a preferential allotment on the same day had one of
them silently deleted. Two different money-raising events are two pieces of
news, and the same goes for two orders or two acquisitions.
"""

import re

# The one case where different filing types really are the same event.
RESULTS_FAMILY = {"Results", "Outcome", "Concall", "Presentation", "Board Meeting"}

# Tags where a same-day repeat is a genuine duplicate worth folding - usually
# the same document filed on both exchanges, or filed twice.
MERGE_SAME_TAG = {
    "Results", "Outcome", "Concall", "Presentation", "Board Meeting",
    "Dividend", "Buyback", "Bonus", "Split", "Rights Issue",
    "Scheme Of Arrangement", "Open Offer", "Ratings Update",
    "Annual Report", "Meeting", "Esop", "Corp Action",
    "Qip", "Qip Allotment", "Pref", "Warrants", "Fund Raising",
    "Change In Management", "Resignation",
}
# Deliberately absent: Order, Acquisition, Nclt, Legal/Reg, Capacity Increase,
# Business Update, Operations, Unusual, Fii, Bulk And Block. Two orders on one
# day are two orders.


def norm_company(name):
    n = (name or "").lower()
    n = re.sub(r"\b(limited|ltd|private|pvt|the|and|company|co|corporation|corp|"
               r"india|indian|inc)\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


# Words that appear in almost every headline and so tell two filings apart from
# each other not at all.
_NOISE = re.compile(
    r"(announcement|announcements|under|regulation|reg|lodr|sebi|listing|"
    r"obligations|disclosure|requirements|intimation|intimating|pursuant|"
    r"regarding|company|limited|ltd|the|of|to|for|and|in|on|by|with|is|are|"
    r"submission|submitted|please|find|attached|enclosed|herewith|copy|dated|"
    r"date|update|updates|general|other|information|letter|read|clause|"
    r"provisions|thereof|act|2015|2013)", re.I)


def headline_sig(text):
    """The words in a headline that actually identify the event."""
    t = _NOISE.sub(" ", (text or "").lower())
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2}


def _overlap(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def fold_cross_exchange(rows, log=print):
    """
    One document filed on both exchanges is one piece of news.

    Tags like Order and Acquisition are kept out of the tag-level merge above,
    because two orders won on the same day are two orders. But the same order,
    filed once with NSE and once with BSE, is not - and that is what was
    showing up twice on the dashboard.

    So within one company, one day and one tag, filings whose headlines
    describe the same thing are folded together. Two different orders name
    different customers and different amounts, so their headlines diverge and
    they stay apart. A generic headline that says nothing either way is treated
    as a duplicate, which is what it almost always is - and the other exchange's
    PDF is still linked from the entry that survives.
    """
    groups = {}
    for r in rows:
        groups.setdefault(
            (norm_company(r.get("company")), r.get("date"), r.get("tag")), []
        ).append(r)

    out, folded = [], 0
    for rows_in_group in groups.values():
        if len(rows_in_group) == 1:
            out.append(rows_in_group[0])
            continue

        clusters = []
        for r in sorted(rows_in_group,
                        key=lambda x: (-(x.get("score") or 0), x.get("time") or "")):
            sig = headline_sig(r.get("headline") or r.get("category"))
            for c in clusters:
                # A headline with nothing distinctive in it cannot argue that
                # this is a different event, so it joins the first cluster.
                if not sig or not c["sig"] or _overlap(sig, c["sig"]) >= 0.6:
                    c["rows"].append(r)
                    break
            else:
                clusters.append({"sig": sig, "rows": [r]})

        for c in clusters:
            rs = c["rows"]
            best = dict(rs[0])
            if len(rs) > 1:
                others = rs[1:]
                best["also_filed"] = (best.get("also_filed") or 0) + len(others)
                best["also_pdfs"] = ([o["pdf_url"] for o in others if o.get("pdf_url")]
                                     + list(best.get("also_pdfs") or []))[:4]
                folded += len(others)
            out.append(best)

    if folded:
        log(f"Cross-exchange: folded {folded} repeats of a filing already shown")
    return out


def bucket_for(tag):
    """What this filing should be grouped under, or None to leave it alone."""
    if tag in RESULTS_FAMILY:
        return "results"
    if tag in MERGE_SAME_TAG:
        return tag              # only ever merges with an identical tag
    return None


def collapse(records, log=print):
    groups, singles = {}, []

    for r in records:
        b = bucket_for(r.get("tag"))
        if not b:
            singles.append(r)
            continue
        groups.setdefault((norm_company(r.get("company")), r.get("date"), b), []).append(r)

    merged, folded = [], 0
    for rows in groups.values():
        if len(rows) == 1:
            merged.append(rows[0])
            continue

        # Keep the filing that actually carries the content: one that was
        # summarised, then the highest score, then the most recent.
        rows.sort(key=lambda x: (bool(x.get("summary")), x.get("score", 0),
                                 x.get("time", "")), reverse=True)
        best = dict(rows[0])
        others = rows[1:]
        best["also_filed"] = len(others)
        best["also_tags"] = sorted({o.get("tag") for o in others
                                    if o.get("tag") and o.get("tag") != best.get("tag")})
        best["also_pdfs"] = [o["pdf_url"] for o in others if o.get("pdf_url")][:4]
        folded += len(others)
        merged.append(best)

    out = fold_cross_exchange(merged + singles, log=log)
    out.sort(key=lambda x: (-(x.get("score") or 0), x.get("time") or ""))
    log(f"Deduplicated: {len(records)} filings -> {len(out)} events "
        f"({len(records) - len(out)} folded in)")
    return out

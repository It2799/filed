"""
Collapse the same event filed several times into one entry.

The genuine duplicate is a quarterly result. It arrives the same day as the
board-meeting outcome and a prior intimation of the meeting - three filings,
one piece of news - and again on the second exchange. Left alone it fills the
dashboard and the AI summarises it three times.

The concall, the investor meet and the investor presentation that arrive
alongside are NOT folded in. They are separate events a reader plans around,
and each is its own category on the dashboard.

Everything else only merges with its own kind. An earlier version lumped QIPs,
preferential issues, warrants and fund raising into one bucket, which meant a
company doing a QIP and a preferential allotment on the same day had one of
them silently deleted. Two different money-raising events are two pieces of
news, and the same goes for two orders or two acquisitions.
"""

import re

# The same results announcement filed under variant headings. Concall,
# Investor Meet and Investor Presentation are deliberately NOT here any
# more: they are their own categories now, and folding them into the
# result would make them unfilterable again.
RESULTS_FAMILY = {"Results", "Outcome", "Board Meeting"}

# Tags where a same-day repeat is a genuine duplicate worth folding - usually
# the same document filed on both exchanges, or filed twice.
MERGE_SAME_TAG = {
    "Results", "Outcome", "Board Meeting",
    "Concall", "Investor Meet", "Investor Presentation", "Press Release",
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


def bucket_for(tag):
    """What this filing should be grouped under, or None to leave it alone."""
    if tag in RESULTS_FAMILY:
        return "results"
    if tag in MERGE_SAME_TAG:
        return tag              # only ever merges with an identical tag
    return None


def fold_cross_exchange(rows, log=print):
    """
    One company, one day, one kind of news - one entry.

    An earlier version tried to tell duplicates apart by comparing headlines,
    and it did not work, because the two exchanges do not describe the same
    document the same way. NSE prefixes everything with "X Limited has informed
    the Exchange regarding..."; BSE quotes the covering letter. The same board
    change came through as "Cessation of Independent Director" on one and
    "completion of term of Independent Director" on the other - one event, no
    words in common. No amount of tuning a similarity threshold fixes that.

    So the rule is now the blunt one, and it holds: the same company filing the
    same kind of news on the same day is one piece of news. The cost is that a
    company announcing two separate orders on one day shows as one entry - rare,
    and the second document is still linked from the entry that survives. The
    benefit is that the constant case, the same filing arriving from both NSE
    and BSE, never shows twice again.
    """
    groups = {}
    for r in rows:
        groups.setdefault(
            (norm_company(r.get("company")), r.get("date"), r.get("tag")), []
        ).append(r)

    out, folded = [], 0
    for rs in groups.values():
        if len(rs) == 1:
            out.append(rs[0])
            continue

        # Keep the one carrying the most: summarised first, then best score,
        # then whichever has the longest headline - the more descriptive filing.
        rs.sort(key=lambda x: (bool(x.get("summary")), x.get("score") or 0,
                               len(x.get("headline") or "")), reverse=True)
        best, others = dict(rs[0]), rs[1:]
        best["also_filed"] = (best.get("also_filed") or 0) + len(others)
        best["also_pdfs"] = (list(best.get("also_pdfs") or [])
                             + [o["pdf_url"] for o in others if o.get("pdf_url")])[:4]
        folded += len(others)
        out.append(best)

    if folded:
        log(f"Cross-exchange: folded {folded} repeats of a filing already shown")
    return out


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

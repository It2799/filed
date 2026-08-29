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

    out = merged + singles
    out.sort(key=lambda x: (-(x.get("score") or 0), x.get("time") or ""))
    log(f"Deduplicated: {len(records)} filings -> {len(out)} events ({folded} folded in)")
    return out

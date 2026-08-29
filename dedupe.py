"""
Collapse the same event filed several times into one entry.

A single quarterly result typically arrives as four separate filings on the
same day: the board-meeting outcome, a press release, an investor presentation,
and a concall intimation. Sometimes twice more because the company files on
both exchanges. Left alone, one company's result fills half a screen and the
AI summarises the same news four times over.

We group by company + day + what kind of event it is, keep the single best
filing, and record how many others it stood in for. The dropped ones' PDF links
are kept, so nothing becomes unreachable.
"""

import re

# Filing types that are really the same underlying event when they land on the
# same day for the same company. Order wins and acquisitions are deliberately
# NOT in here: two different orders on one day are two different pieces of news.
SAME_EVENT = {
    "Results": "results",
    "Outcome": "results",
    "Concall": "results",
    "Presentation": "results",
    "Board Meeting": "results",
    "Dividend": "dividend",
    "Corp Action": "dividend",
    "Buyback": "buyback",
    "Bonus": "bonus",
    "Split": "split",
    "Rights Issue": "rights",
    "Scheme Of Arrangement": "scheme",
    "Qip": "raise",
    "Qip Allotment": "raise",
    "Pref": "raise",
    "Warrants": "raise",
    "Fund Raising": "raise",
    "Ratings Update": "rating",
    "Change In Management": "people",
    "Resignation": "people",
    "Annual Report": "ar",
    "Meeting": "meeting",
    "Esop": "esop",
}


def norm_company(name):
    n = (name or "").lower()
    n = re.sub(r"\b(limited|ltd|private|pvt|the|and|company|co|corporation|corp|"
               r"india|indian|inc)\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


def collapse(records, log=print):
    """Return a de-duplicated list, newest/most important kept."""
    groups = {}
    singles = []

    for r in records:
        bucket = SAME_EVENT.get(r.get("tag"))
        if not bucket:
            singles.append(r)            # nothing to merge it with
            continue
        key = (norm_company(r.get("company")), r.get("date"), bucket)
        groups.setdefault(key, []).append(r)

    merged = []
    collapsed_count = 0

    for key, rows in groups.items():
        if len(rows) == 1:
            merged.append(rows[0])
            continue

        # Prefer one that was actually summarised, then the highest score,
        # then the most recent - that is the filing with the real content.
        rows.sort(key=lambda x: (bool(x.get("summary")), x.get("score", 0),
                                 x.get("time", "")), reverse=True)
        best = dict(rows[0])
        others = rows[1:]

        best["also_filed"] = len(others)
        best["also_tags"] = sorted({o.get("tag") for o in others if o.get("tag")})
        best["also_pdfs"] = [o["pdf_url"] for o in others if o.get("pdf_url")][:4]
        collapsed_count += len(others)
        merged.append(best)

    out = merged + singles
    out.sort(key=lambda x: (-(x.get("score") or 0), x.get("time") or ""), reverse=False)
    log(f"Deduplicated: {len(records)} filings -> {len(out)} events "
        f"({collapsed_count} folded in)")
    return out

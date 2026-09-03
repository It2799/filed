"""
Ask every category to justify itself.

The scoring rules have been fixed one category at a time, each time because a
reader spotted something absurd sitting in the wrong place - an AGM notice
under Pref, a chief executive's appointment under Acquisition, a daily buyback
ledger crowding out the buyback. Fixing them one at a time is how the next one
gets found by the reader rather than by us.

So this asks the question for all of them at once, and it asks it of the LIVE
site rather than of the rules: every filing tagged "Order" should contain a
word that has something to do with orders, and if it does not, either the
filing is in the wrong place or the evidence below is too narrow. Both are
worth knowing.

It is deliberately not a test. Evidence is a blunt instrument and a healthy
category still shows a few percent of filings whose wording it does not
recognise - a summary that says "bagged a mandate" is a real order win and
matches nothing here. What matters is the SHAPE: a category running at 3%
unexplained is fine, one running at 40% has something structurally wrong, and
that is visible at a glance in the output.

    python tools/audit_categories.py                 # the live site
    python tools/audit_categories.py --show Order    # every flagged filing
    python tools/audit_categories.py --file x.json   # a saved copy
"""

import argparse
import json
import re
import sys
import urllib.request

API = "https://filed-omega.vercel.app/api/announcements?days=7"

# What a filing in this category ought to say somewhere. Written loosely: the
# point is to catch a filing that has NOTHING to do with its category, not to
# police wording.
EVIDENCE = {
    "Acquisition": r"acquisition|acquir|merger|amalgamat|slump sale|divest|"
                   r"stake sale|joint venture|takeover|buy.{0,15}stake|"
                   r"sale of (the )?(subsidiary|business|undertaking|division)",
    "Order": r"order|contract|letter of award|letter of intent|\bloi\b|tender|"
             r"bagg|bags\b|\bwon\b|\bwins\b|secured|award|work order|"
             r"purchase order|mandate",
    "Dividend": r"dividend",
    "Results": r"result|earning|profit|revenue|turnover|quarter|half.year|"
               r"financial statement|ebitda|\bpat\b|standalone|consolidated",
    "Pref": r"preferential",
    "Qip": r"\bqip\b|qualified institution",
    "Qip Allotment": r"\bqip\b|qualified institution",
    "Fund Raising": r"fund.?rais|raising of (fund|capital)|rais\w+ (of )?(fund|capital)|"
                    r"\bncd\b|debenture|\bbond\b|commercial paper|private placement|"
                    r"capital raising|\bfpo\b|further public offer|borrow",
    "Warrants": r"warrant",
    "Rights Issue": r"rights issue|right issue|rights entitlement|letter of offer",
    "Buyback": r"buy.?back",
    "Split": r"split|sub.?division|face value",
    "Bonus": r"bonus",
    "Open Offer": r"open offer|detailed public statement|public announcement|"
                  r"manager to the offer|offer advertisement|letter of offer|"
                  r"regulation 3\(1\)|takeover",
    "Delisting": r"delist",
    "Promoter Buy/Sell": r"promoter|encumbr|pledg|inter.se transfer",
    "Stake Change": r"\bsast\b|substantial acquisition|regulation 29|reg\.? ?29|"
                    r"shareholding|stake",
    "Scheme Of Arrangement": r"scheme|amalgamat|demerger|de.merger|merger|\bnclt\b|"
                             r"arrangement",
    "Nclt": r"\bnclt\b|tribunal|insolvency|resolution plan|\bcirp\b|liquidat|"
            r"moratorium|\bibc\b|corporate insolvency",
    "Capacity Increase": r"capacity|plant|greenfield|brownfield|capex|expansion|"
                         r"commission|production|facility|debottleneck|"
                         r"capital expenditure|\bunit\b",
    "Business Update": r"business update|guidance|outlook|operational update|"
                       r"monthly|sales|volume|performance|update on",
    "Change In Management": r"appoint|resign|cessation|director|\bkmp\b|chief|"
                            r"officer|managing director|\bceo\b|\bcfo\b|"
                            r"company secretary|elevat|designat",
    "Resignation": r"resign|cessation|steps down|relinquish",
    "Ratings Update": r"rating|\bicra\b|crisil|\bcare\b|india ratings|brickwork|"
                      r"acuite|infomerics|outlook",
    "Legal/Reg": r"order|penalt|\bsebi\b|court|tribunal|notice|demand|litigat|"
                 r"\bfine\b|show cause|adjudicat|appeal|writ|prosecution|"
                 r"compound|search|survey|raid|\bgst\b|income tax|arbitrat",
    "Concall": r"conference call|earnings call|con.?call|analyst call",
    "Investor Meet": r"investor|analyst|institutional|meet|conference|roadshow",
    "Investor Presentation": r"presentation|investor",
    "Meeting": r"meeting|\bagm\b|\begm\b|postal ballot|general meeting|"
               r"record date|book closure",
    "Esop": r"esop|employee stock|stock option|\bsar\b|share.based",
    "Corp Action": r"record date|book closure|corporate action|dividend|bonus|split",
    "Fii": r"\bfii\b|foreign|\bfpi\b",
    "Article Of Association": r"article|memorandum|\bmoa\b|\baoa\b",
    "Board Meeting": r"board meeting|board of directors",
    "Annual Report": r"annual report",
}

# Categories that make no claim, so nothing to check.
NO_CLAIM = {"Other", "Routine", "Outcome", "Press Release", "Operations"}


def text_of(a):
    return " ".join(
        str(a.get(k) or "")
        for k in ("category", "headline", "summary", "why_it_matters", "impact")
    )


def load(path):
    if path:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        with urllib.request.urlopen(API) as r:
            data = json.load(r)
    if isinstance(data, dict):
        return data.get("items") or data.get("announcements") or []
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="a saved copy of the API response")
    p.add_argument("--show", help="print every flagged filing in this category")
    p.add_argument("--worst", type=int, default=3,
                   help="how many examples to print per category (default 3)")
    args = p.parse_args()

    items = load(args.file)
    if not items:
        print("No filings came back.")
        return 1

    by_tag = {}
    for a in items:
        by_tag.setdefault(a.get("tag") or "?", []).append(a)

    print(f"{len(items)} filings live, {len(by_tag)} categories\n")
    print(f"{'category':<24}{'n':>5}{'unexplained':>13}   examples")
    print("-" * 78)

    rows = []
    for tag, group in sorted(by_tag.items(), key=lambda kv: -len(kv[1])):
        if tag in NO_CLAIM:
            continue
        pattern = EVIDENCE.get(tag)
        if not pattern:
            rows.append((tag, len(group), None, []))
            continue
        rx = re.compile(pattern, re.I)
        bad = [a for a in group if not rx.search(text_of(a))]
        rows.append((tag, len(group), len(bad) / len(group), bad))

    for tag, n, share, bad in rows:
        if share is None:
            print(f"{tag:<24}{n:>5}{'no evidence rule':>13}")
            continue
        flag = "  <-- look" if share >= 0.15 and n >= 5 else ""
        print(f"{tag:<24}{n:>5}{len(bad):>6} ({share:4.0%}){flag}")
        for a in bad[: args.worst]:
            print(f"{'':<24}      {(a.get('company') or '')[:22]:<24}"
                  f"{(a.get('headline') or '')[:44]}")

    if args.show:
        rx = re.compile(EVIDENCE.get(args.show, "$^"), re.I)
        print(f"\n\nEverything flagged under {args.show!r}:\n" + "-" * 78)
        for a in by_tag.get(args.show, []):
            if not rx.search(text_of(a)):
                print(f"  {(a.get('company') or '')[:28]:<30}"
                      f"{(a.get('headline') or '')[:70]}")
                s = (a.get("summary") or "")[:150]
                if s:
                    print(f"  {'':<30}{s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

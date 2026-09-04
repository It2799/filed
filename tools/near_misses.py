"""
Find the filings a category ALMOST caught.

Every silly mistake in the scoring rules has the same shape: a pattern written
from one remembered example, when the exchanges word the same thing six ways.

    written          the filings actually say       result
    award of         "Awarding of order(s)"         every order category missed
    \\bncd\\b          "NCDs"                         the plural broke it
    received of      "received an order"            order wins scored nothing
    40 characters    a real headline used 51        AGM notice missed

None of those needed cleverness to find. They needed somebody to look at how
the filings are worded before writing the pattern, which is what this does.

For each topic it takes a loose set of words a human would use for that kind of
news, finds every filing whose text contains them, and lists the ones that did
NOT end up in that category. Most of the output is correct - a dividend
mentions "record date", a results filing mentions "revenue" - so this is a
reading tool, not a test. What it is for is spotting a wording the rules have
never seen, before a reader does.

    python tools/near_misses.py                  # everything
    python tools/near_misses.py --topic Order    # one
    python tools/near_misses.py --file x.json    # a saved corpus
"""

import argparse
import json
import re
import sys
import urllib.request

API = ("https://filed-omega.vercel.app/api/announcements?days=7&scope=all")

# Words a person would use, not the pattern the rules use. The point is to
# disagree with the rules, so these must be written independently of them.
LOOSE = {
    "Order": [
        r"\border\b", r"\bcontract\b", r"letter of (award|intent|acceptance)",
        r"\bbagg?ed\b", r"\bwon\b", r"work order", r"purchase order",
        r"\btender\b", r"\bloa\b", r"received.{0,20}order",
    ],
    "Acquisition": [
        r"acquisition", r"acquir", r"\bmerger\b", r"amalgamat",
        r"divest", r"stake sale", r"slump sale", r"share purchase agreement",
        r"controlling (stake|interest)",
    ],
    "Dividend": [r"dividend"],
    "Fund Raising": [
        r"fund.?rais", r"raising of (funds|capital)", r"\bncds?\b",
        r"debenture", r"commercial paper", r"private placement",
        r"preferential allotment",
    ],
    "Results": [
        r"quarterly results", r"unaudited.{0,20}results",
        r"financial results", r"\bebitda\b",
    ],
    "Buyback": [r"buy.?back", r"bought back"],
    "Bonus": [r"bonus (issue|share)"],
    "Split": [r"stock split", r"sub.?division of.{0,20}share", r"face value"],
    "Rights Issue": [r"rights issue", r"rights entitlement"],
    "Capacity Increase": [
        r"commercial production", r"new plant", r"greenfield", r"brownfield",
        r"capacity (expansion|addition)", r"commissioning",
    ],
    "Product Approval": [
        r"\busfda\b", r"\bfda\b approval", r"\bcdsco\b", r"\banda\b",
        r"marketing authoris", r"drug approval",
    ],
    "Clinical Trial": [
        r"phase (i|ii|iii|1|2|3)\b", r"clinical trial", r"topline",
        r"primary endpoint",
    ],
    "Delisting": [r"delist"],
    "Open Offer": [
        r"open offer", r"detailed public statement", r"manager to the offer",
    ],
    "Scheme Of Arrangement": [
        r"scheme of (arrangement|amalgamation|merger|demerger)", r"de-?merger",
    ],
}


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
        with urllib.request.urlopen(API, timeout=90) as r:
            data = json.load(r)
    if isinstance(data, dict):
        return data.get("items") or data.get("announcements") or []
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file")
    p.add_argument("--topic", help="just this one")
    p.add_argument("--show", type=int, default=6,
                   help="filings to print per topic (default 6)")
    args = p.parse_args()

    items = load(args.file)
    if not items:
        print("no filings")
        return 1
    print(f"{len(items)} filings\n")

    topics = {args.topic: LOOSE[args.topic]} if args.topic else LOOSE
    for topic, words in topics.items():
        rx = re.compile("|".join(words), re.I)
        hits = [a for a in items if rx.search(text_of(a))]
        elsewhere = [a for a in hits if a.get("tag") != topic]
        if not hits:
            continue
        share = len(elsewhere) / len(hits) * 100
        print(f"{topic}: {len(hits)} filings use these words, "
              f"{len(elsewhere)} are filed elsewhere ({share:.0f}%)")

        # The interesting ones are the filings NOBODY claimed - below the line
        # with a vague tag. A dividend filed under Corp Action is a judgement
        # call; a Rs 500 crore order sitting on Other is a miss.
        buried = [a for a in elsewhere
                  if (a.get("score") or 0) < 55
                  or a.get("tag") in ("Other", "Routine", "Press Release",
                                      "Outcome", "Corp Action")]
        print(f"   of those, {len(buried)} are below the line or uncategorised:")
        for a in buried[: args.show]:
            print(f"     [{a.get('tag')}/{a.get('score')}] "
                  f"{(a.get('company') or '')[:24]:<26}"
                  f"{(a.get('headline') or '')[:52]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Builds web/app/samples.json from real announcement records.

Why this exists: the landing page samples were originally typed out by hand,
and the company name, category and timestamp on several of them were wrong.
Summaries were real but the labels around them were not. Generating the file
from the actual data makes that mistake impossible to repeat.

Run it after any dashboard run:

    python make_samples.py

It reads dashboard.html (which carries the real records) and cache.json (which
carries the AI summaries), joins them, picks a spread across categories, and
writes the JSON the website imports.
"""

import json
import os
import re


def same_company(name):
    """'SKY GOLD AND DIAMONDS LIMITED' and 'Sky Gold And Diamonds Ltd' are one
    company filing on both exchanges, so collapse them to one key."""
    n = (name or "").lower()
    n = re.sub(r"\b(limited|ltd|private|pvt|the|and|&|india|-\$)\b", "", n)
    return re.sub(r"[^a-z0-9]", "", n)

HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.join(HERE, "dashboard.html")
CACHE = os.path.join(HERE, "cache.json")
OUT = os.path.join(HERE, "web", "app", "samples.json")

HOW_MANY = 7

# Prefer a spread over these, in this order, so the page isn't all of one kind.
# These must match the tag names in rules.py TOPICS.
PREFERRED_TAGS = ["Results", "Order", "Dividend", "Buyback", "Bonus", "Split",
                  "Acquisition", "Scheme Of Arrangement", "Fund Raising", "Qip",
                  "Legal/Reg", "Nclt", "Ratings Update", "Capacity Increase",
                  "Business Update", "Open Offer", "Rights Issue"]


def load_records():
    html = open(DASHBOARD, encoding="utf-8").read()
    m = re.search(r"const DATA = (\[.*?\]);\nconst META", html, re.S)
    if not m:
        raise SystemExit("Couldn't find the data in dashboard.html. Run run.py first.")
    return json.loads(m.group(1))


def main():
    records = load_records()
    cache = json.load(open(CACHE, encoding="utf-8"))

    # Only records that have both a real summary and a PDF to link to.
    usable = []
    for r in records:
        c = cache.get(r["id"])
        if not c or not c.get("summary") or not r.get("pdf_url"):
            continue
        if c["summary"].startswith("Could not summarise"):
            continue
        usable.append({
            "company": r["company"],
            "exchange": r["exchange"],
            "category": r["category"],
            "time": r["time"],
            "tag": r["tag"],
            "impact": c.get("impact") or "Neutral",
            "summary": c["summary"],
            "numbers": c.get("key_numbers", [])[:4],
            "why": c.get("why_it_matters", ""),
            "pdf": r["pdf_url"],
        })

    print(f"{len(usable)} records have a summary and a PDF")

    by_tag = {}
    for u in usable:
        by_tag.setdefault(u["tag"], []).append(u)

    # One per tag, and within a tag prefer whichever impact we've shown least.
    # Otherwise every card ends up green and the page reads like a sales pitch
    # rather than a tool that will also tell you when something is wrong.
    chosen, companies = [], set()
    impact_count = {"Positive": 0, "Negative": 0, "Neutral": 0, "Unclear": 0}
    tag_count = {}
    MAX_PER_TAG = 2          # never let one category take over the page

    def pick_from(candidates):
        ok = [c for c in candidates
              if same_company(c["company"]) not in companies
              and len(c["numbers"]) >= 2
              and tag_count.get(c["tag"], 0) < MAX_PER_TAG]
        if not ok:
            return None
        return min(ok, key=lambda c: impact_count.get(c["impact"], 0))

    def take(u):
        chosen.append(u)
        companies.add(same_company(u["company"]))
        impact_count[u["impact"]] = impact_count.get(u["impact"], 0) + 1
        tag_count[u["tag"]] = tag_count.get(u["tag"], 0) + 1

    for tag in PREFERRED_TAGS:
        if len(chosen) >= HOW_MANY:
            break
        u = pick_from(by_tag.get(tag, []))
        if u:
            take(u)

    while len(chosen) < HOW_MANY:         # top up if some tags were missing
        u = pick_from(usable)
        if not u:
            break
        take(u)

    if len(chosen) < HOW_MANY:
        print(f"  note: only {len(chosen)} distinct samples available - "
              f"run run.py over more days for a wider spread")

    # Make sure at least one card is bad news. A page of seven green badges
    # reads as marketing; the point of the product is that it tells you when
    # something is wrong too.
    if chosen and not any(c["impact"] == "Negative" for c in chosen):
        taken = {same_company(c["company"]) for c in chosen}
        negatives = [u for u in usable
                     if u["impact"] == "Negative"
                     and same_company(u["company"]) not in taken
                     and len(u["numbers"]) >= 2]
        if negatives:
            for i in range(len(chosen) - 1, -1, -1):
                if chosen[i]["impact"] == "Positive":
                    print(f"  swapped in a Negative example: "
                          f"{negatives[0]['company']} ({negatives[0]['tag']})")
                    chosen[i] = negatives[0]
                    break

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(chosen, f, ensure_ascii=False, indent=1)

    print(f"\nwrote {len(chosen)} samples to {OUT}\n")
    for c in chosen:
        print(f"  {c['tag']:<12} {c['impact']:<9} {c['company'][:42]:<44} {c['time']}")


if __name__ == "__main__":
    main()

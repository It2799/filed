"""
Checks for the insider-trading reader.

Run:  python tests/test_insider.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import insider                                             # noqa: E402

CHECKS = [0]
FAILURES = []


def check(ok, what, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(f"{what}\n      {detail}" if detail else what)


# ---------------------------------------------------------------------------
# 1. What Ishan asked to be left out
#
# ESOP, inter-se transfers and company welfare trusts. None of the three says
# anything about what an insider thinks the shares are worth, which is the only
# reason to read this at all.
# ---------------------------------------------------------------------------

LEAVE_OUT = [
    # Welfare trusts, punctuated every possible way. "Eclerx Employee Welfare
    # (Trust)" went straight through a pattern that expected "welfare trust" as
    # two plain words, which is why the name is stripped to letters first.
    ("Eclerx Employee Welfare (Trust)", "Market Purchase"),
    ("JSW Steel Employees Welfare Trust ?  ESOP Plan 2016   A/c", "Market Purchase"),
    ("Dr. Lal PathLabs Employees Welfare Trust", "Market Sale"),
    ("Jaro Education Welfare Trust", "Market Purchase"),
    ("ABC Employees' Trust", "Market Purchase"),
    ("XYZ Staff Welfare Fund Trust", "Market Sale"),
    # An employee exercising options is being paid, not taking a view.
    ("Ravi Kumar", "ESOP"),
    ("Anita Desai", "esop"),
    # Shares moving inside the promoter family. Written three ways in the wild.
    ("Someone", "Inter-se-Transfer"),
    ("Someone", "Inter se Transfer"),
    ("Someone", "Interse Transfer"),
]
for who, mode in LEAVE_OUT:
    check(insider.skip_reason({"who": who, "mode": mode}) is not None,
          "this should be left out", f"{who[:46]!r} / {mode!r}")

KEEP = [
    # A family trust is somebody's own money taking a view. Not a welfare trust.
    ("Adivam Family Trust", "Market Sale"),
    ("The Sharma Family Private Trust", "Market Purchase"),
    ("Sanjay Purohit", "Market Sale"),
    ("Kakatiya Industries Pvt.Ltd", "Market Purchase"),
    ("Navin Agarwal", "Market Sale"),
    ("Pankaj Vasudeva", "Allotment"),
    ("Someone", "Off Market"),
    ("Someone", "Gift"),
    ("Someone", "Pledge Creation"),
    ("Someone", "Preferential Offer"),
]
for who, mode in KEEP:
    check(insider.skip_reason({"who": who, "mode": mode}) is None,
          "this should be kept", f"{who[:46]!r} / {mode!r}")


# ---------------------------------------------------------------------------
# 2. One filing, several people
#
# XBRL keeps them apart with contextRef - the company's fields on "MainI" and
# each person on "Disclosure1", "Disclosure2". Reading the values in document
# order instead would pair the first person's name with the third person's
# share count.
# ---------------------------------------------------------------------------

THREE_PEOPLE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:c="http://www.bseindia.com/xbrl/co/2017-09-15/in-bse-co">
  <c:NameOfTheCompany contextRef="MainI">NCL INDUSTRIES LIMITED</c:NameOfTheCompany>
  <c:Symbol contextRef="MainI">NCLIND</c:Symbol>
  <c:ScripCode contextRef="MainI">502168</c:ScripCode>
  <c:DateOfFiling contextRef="MainI">2026-09-11</c:DateOfFiling>
  <c:DisclosureUnderRegulation contextRef="MainI">Regulation 7 (2)</c:DisclosureUnderRegulation>
  <c:NameOfThePerson contextRef="Disclosure1">Kalidindi Ravi</c:NameOfThePerson>
  <c:CategoryOfPerson contextRef="Disclosure1">Promoter and Director</c:CategoryOfPerson>
  <c:SecuritiesAcquiredOrDisposedNumberOfSecurity contextRef="Disclosure1">800</c:SecuritiesAcquiredOrDisposedNumberOfSecurity>
  <c:SecuritiesAcquiredOrDisposedValueOfSecurity contextRef="Disclosure1">141200</c:SecuritiesAcquiredOrDisposedValueOfSecurity>
  <c:SecuritiesAcquiredOrDisposedTransactionType contextRef="Disclosure1">Buy</c:SecuritiesAcquiredOrDisposedTransactionType>
  <c:ModeOfAcquisitionOrDisposal contextRef="Disclosure1">Market Purchase</c:ModeOfAcquisitionOrDisposal>
  <c:NameOfThePerson contextRef="Disclosure2">Kakatiya Industries Pvt.Ltd</c:NameOfThePerson>
  <c:CategoryOfPerson contextRef="Disclosure2">Promoter Group</c:CategoryOfPerson>
  <c:SecuritiesAcquiredOrDisposedNumberOfSecurity contextRef="Disclosure2">830</c:SecuritiesAcquiredOrDisposedNumberOfSecurity>
  <c:SecuritiesAcquiredOrDisposedTransactionType contextRef="Disclosure2">Buy</c:SecuritiesAcquiredOrDisposedTransactionType>
  <c:ModeOfAcquisitionOrDisposal contextRef="Disclosure2">ESOP</c:ModeOfAcquisitionOrDisposal>
  <c:NameOfThePerson contextRef="Disclosure3">VIKRAM CHEMICALS PRIVATE LIMITED</c:NameOfThePerson>
  <c:SecuritiesAcquiredOrDisposedNumberOfSecurity contextRef="Disclosure3">260</c:SecuritiesAcquiredOrDisposedNumberOfSecurity>
  <c:SecuritiesAcquiredOrDisposedTransactionType contextRef="Disclosure3">Sell</c:SecuritiesAcquiredOrDisposedTransactionType>
  <c:ModeOfAcquisitionOrDisposal contextRef="Disclosure3">Market Sale</c:ModeOfAcquisitionOrDisposal>
</xbrli:xbrl>"""

main, people = insider.parse_xbrl(THREE_PEOPLE)
check(main.get("company") == "NCL INDUSTRIES LIMITED",
      "the company name was not read", repr(main.get("company")))
check(main.get("symbol") == "NCLIND", "the symbol was not read")
check(len(people) == 3, "one filing's three people were not kept apart",
      f"got {len(people)}")

# Each person keeps their OWN numbers. This is the check that catches reading
# the values in document order.
check(people[0]["who"] == "Kalidindi Ravi" and people[0]["shares"] == "800",
      "the first person has the wrong share count", repr(people[0]))
check(people[1]["who"] == "Kakatiya Industries Pvt.Ltd"
      and people[1]["shares"] == "830",
      "the second person has the wrong share count", repr(people[1]))
check(people[2]["shares"] == "260" and people[2]["side"] == "Sell",
      "the third person has the wrong trade", repr(people[2]))

# ...and the ESOP row among them is dropped while its neighbours stay.
kept = [p for p in people if not insider.skip_reason(p)]
check(len(kept) == 2, "the ESOP row was not dropped from a mixed filing",
      f"{len(kept)} kept of 3")


# ---------------------------------------------------------------------------
# 3. The feed repeats itself
#
# 91 items on 11 September were 39 filings. South West Pinnacle's appeared
# fourteen times, and fetching each copy turned two people's trades into
# twenty-eight rows on the page.
# ---------------------------------------------------------------------------

REPEATING_FEED = """<rss version="2.0"><channel>
 <item><title>A LTD</title><link>https://x/IT_1.xml</link>
  <description>AAA|A LTD|Original|Regulation 7 (2)|IT_1.xml|IT_1.html|1|2|-</description>
  <pubDate>11-Sep-2026 21:03:30</pubDate></item>
 <item><title>A LTD</title><link>https://x/IT_1.xml</link>
  <description>AAA|A LTD|Original|Regulation 7 (2)|IT_1.xml|IT_1.html|1|2|-</description>
  <pubDate>11-Sep-2026 21:03:30</pubDate></item>
 <item><title>B LTD</title><link>https://x/IT_2.xml</link>
  <description>BBB|B LTD|Original|Regulation 7 (2)|IT_2.xml|IT_2.html|1|2|-</description>
  <pubDate>11-Sep-2026 19:24:37</pubDate></item>
 <item><title>C LTD</title><link>https://x/IT_3.html</link>
  <description>CCC|C LTD|Original|Regulation 7 (2)|IT_3.xml|IT_3.html|1|2|-</description>
  <pubDate>11-Sep-2026 18:00:00</pubDate></item>
</channel></rss>"""

items = insider.feed_items(REPEATING_FEED)
check(len(items) == 2, "the feed's repeats were not collapsed",
      f"got {len(items)}, wanted 2")
check({i["url"] for i in items} == {"https://x/IT_1.xml", "https://x/IT_2.xml"},
      "the wrong filings survived deduplication",
      repr([i["url"] for i in items]))
check(items[0]["symbol"] == "AAA", "the symbol was not read from the feed")

# A malformed feed returns nothing rather than raising - an exchange serving
# broken XML must not stop the run.
check(insider.feed_items("<rss><channel><item>", log=lambda *a: None) == [],
      "a broken feed raised instead of returning nothing")


# ---------------------------------------------------------------------------
# 4. The sentence a reader sees
# ---------------------------------------------------------------------------

line = insider.headline({
    "who": "Kalidindi Ravi", "category": "Promoter and Director", "side": "Buy",
    "shares": 800, "value": 141200, "mode": "Market Purchase",
    "after_pct": "0.0722"})
for bit in ("Kalidindi Ravi", "Promoter and Director", "bought", "800 shares",
            "141,200", "market purchase", "0.0722%"):
    check(bit in line, f"the headline is missing {bit!r}", line)

sold = insider.headline({"who": "X", "category": "", "side": "Sell",
                         "shares": 0, "value": 0, "mode": "", "after_pct": ""})
check("sold" in sold, "a sale does not read as sold", sold)

# Numbers arrive as '6,900', '-', '' and None.
for raw, want in [("6,900", 6900), ("-", 0), ("", 0), (None, 0), ("141200", 141200)]:
    check(insider._num(raw) == want, f"_num({raw!r}) should be {want}",
          repr(insider._num(raw)))


# ---------------------------------------------------------------------------
# 5. Two shapes of row, and what makes each one distinct
#
# A row read from the XBRL filing has a named person, a share count, a value
# and a mode. A row read from the document has none of them - just a company
# and a sentence. The key that decides whether two rows are the same trade was
# built from the first shape's fields, so every row of the second shape
# collapsed to the same key: a day of sixty-eight filings stored as one, and
# the page showed three rows for four days.
# ---------------------------------------------------------------------------

import publish_insider as pi                                # noqa: E402

STRUCTURED_A = {"symbol": "ABC", "who": "Ravi", "shares": 100, "value": 1000,
                "mode": "Market Purchase", "traded_on": "2026-09-11"}
STRUCTURED_B = {"symbol": "ABC", "who": "Anita", "shares": 200, "value": 2000,
                "mode": "Market Sale", "traded_on": "2026-09-11"}
check(pi.trade_key(STRUCTURED_A) != pi.trade_key(STRUCTURED_B),
      "two different structured trades share a key")
check(pi.trade_key(STRUCTURED_A) == pi.trade_key(dict(STRUCTURED_A)),
      "the same structured trade gets two keys")

BLANK = {"symbol": "", "who": "", "shares": 0, "value": 0, "mode": "",
         "traded_on": ""}
FILING_A = dict(BLANK, company="BLB Ltd", filed_on="2026-09-11",
                headline="Promoter Brij Rattan Bagri bought 90,503 shares")
FILING_B = dict(BLANK, company="Usha Martin", filed_on="2026-09-11",
                headline="Peterhouse Investments sold 150,000 shares")
FILING_C = dict(BLANK, company="BLB Ltd", filed_on="2026-09-11",
                headline="Promoter Brij Rattan Bagri sold 1,000 shares")

check(pi.trade_key(FILING_A) != pi.trade_key(FILING_B),
      "two filings from different companies collapsed to one key",
      pi.trade_key(FILING_A))
check(pi.trade_key(FILING_A) != pi.trade_key(FILING_C),
      "two different filings from the SAME company collapsed to one key")
check(pi.trade_key(FILING_A) == pi.trade_key(dict(FILING_A)),
      "the same filing gets two keys, so it would show twice")

rows, added = pi.merge([], [FILING_A, FILING_B, FILING_C, dict(FILING_A)])
check(len(rows) == 3 and added == 3,
      "merging three distinct filings and one repeat should give three",
      f"{len(rows)} rows, {added} added")

# A structured row and a filing row never share a key, whatever else matches.
check(pi.trade_key(STRUCTURED_A) != pi.trade_key(FILING_A),
      "a structured trade and a document row share a key")


# ---------------------------------------------------------------------------

print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")

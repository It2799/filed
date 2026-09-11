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
#
# It used to be the form's own words in the form's own order:
#
#     Eclerx Employee Welfare (Trust) bought 16,900 shares worth
#     Rs 32,071,369 by market purchase - now holds 0.0238%
#
# Rs 32,071,369 is a figure nobody reads at a glance, "by market purchase" is
# a form field rather than English, and 0.0238% claims four decimals of
# precision the number does not have. The price per share - the one figure
# you can hold against what the share trades at today - was missing entirely.
# ---------------------------------------------------------------------------

line = insider.headline({
    "who": "Kalidindi Ravi", "category": "Promoter and Director", "side": "Buy",
    "shares": 800, "value": 141200, "mode": "Market Purchase",
    "after_pct": "0.0722"})
for bit in ("Kalidindi Ravi", "a promoter and director", "bought",
            "800 shares", "Rs 176.50 each", "Rs 1.41 lakh in all",
            "on the open market", "Holding after: 0.07%"):
    check(bit in line, f"the headline is missing {bit!r}", line)

# The price is worked out, because the filing never states it.
check(insider._price(141200, 800) == 176.5,
      "the price per share is wrong", str(insider._price(141200, 800)))
check(insider._price(0, 800) == 0 and insider._price(141200, 0) == 0,
      "a missing value or share count did not give a price of nothing")

# Lakhs and crores, not a nine-digit number.
check(insider._rupees(141200) == "Rs 1.41 lakh",
      "a lakh was not written as a lakh", insider._rupees(141200))
check(insider._rupees(474522751) == "Rs 47.45 crore",
      "a crore was not written as a crore", insider._rupees(474522751))
check(insider._rupees(4120) == "Rs 4,120",
      "a small figure was inflated into lakhs", insider._rupees(4120))

# Indian digit grouping. 620000 is six lakh twenty thousand, and it is written
# 6,20,000 by everybody who will read this.
check(insider._indian(620000) == "6,20,000",
      "digits are not grouped the Indian way", insider._indian(620000))
check(insider._indian(1234567) == "12,34,567",
      "digits are not grouped the Indian way", insider._indian(1234567))
check(insider._indian(800) == "800" and insider._indian(0) == "0",
      "a short number was mangled by the grouping")

# Paise where they matter and nowhere else.
check(insider._each(872.5) == "Rs 872.50",
      "a block price lost its paise", insider._each(872.5))
check(insider._each(2651) == "Rs 2,651",
      "a four-figure price kept pointless paise", insider._each(2651))
check(insider._each(0) == "", "a missing price printed something")

# A stake of 0.0238% is not four decimals of precision.
check(insider._stake("0.0722") == "0.07%",
      "the stake was not rounded", insider._stake("0.0722"))
check(insider._stake("0.004") == "under 0.01%",
      "a tiny stake was printed as 0.00%", insider._stake("0.004"))
check(insider._stake("") == "" and insider._stake("0") == "",
      "an absent stake printed something")

# A pledge is not a purchase. Nobody paid a price per share to pledge shares
# they already own, so quoting one would be a lie.
pledged = insider.headline({
    "who": "Sunil Agarwal", "category": "Promoter", "side": "Pledge Revoke",
    "shares": 2775000, "value": 195304500, "mode": "Pledge Release",
    "after_pct": "12.3"})
check("released a pledge on" in pledged,
      "a pledge release did not read as one", pledged)
check("each" not in pledged, "a pledge was given a price per share", pledged)
check("Rs 19.53 crore" in pledged, "the pledge lost its value", pledged)

sold = insider.headline({"who": "X", "category": "", "side": "Sell",
                         "shares": 0, "value": 0, "mode": "", "after_pct": ""})
check("sold" in sold, "a sale does not read as sold", sold)

# An empty row must still produce a sentence rather than a crash.
blank = insider.headline({})
check(blank and blank.endswith("."), "an empty row did not give a sentence",
      repr(blank))

# Numbers arrive as '6,900', '-', '' and None.
for raw, want in [("6,900", 6900), ("-", 0), ("", 0), (None, 0), ("141200", 141200)]:
    check(insider._num(raw) == want, f"_num({raw!r}) should be {want}",
          repr(insider._num(raw)))


# ---------------------------------------------------------------------------
# 4b. The employee schemes that were on the page anyway
#
# Ishan asked twice. The first rule matched on the word TRUST, and the trusts
# do not always carry it in the name: "Eclerx Employee Welfare" is the NAME
# and "Trust" is the CATEGORY, in a different field, so the letters the rule
# read were "eclerxemployeewelfare" and nothing matched. Ten of its trades
# were live. "Firstsource Employee Benefit Trust" missed by one letter, the
# rule wanting "employeesbenefittrust" with an s. And the mode rule demanded
# the word be exactly "esop", so "ESOS" - the same scheme, one letter apart -
# walked through.
# ---------------------------------------------------------------------------

MUST_GO = [
    ("Eclerx Employee Welfare", "Trust", "Market Purchase"),
    ("Eclerx Employee Welfare (Trust)", "Trust", "Off Market"),
    ("Firstsource Employee Benefit Trust", "Trust", "Off Market"),
    ("JSW Steel Employees Welfare Trust - ESOP Plan 2016 A/c", "Trust", "Market Sale"),
    ("Some Company Staff Welfare Fund", "Trust", "Market Purchase"),
    ("Anybody At All", "Promoter", "ESOP"),
    ("Anybody At All", "Promoter", "ESOS"),
    ("Anybody At All", "Promoter", "Employee Stock Option"),
    ("Anybody At All", "Promoter", "Inter-se Transfer"),
    # The backstop: category says Trust, name says staff, spelled any way.
    ("ABC Employees Group", "Trust", "Off Market"),
]
for name, category, mode in MUST_GO:
    check(insider.skip_reason({"who": name, "category": category,
                               "mode": mode}) is not None,
          "an employee scheme or an inter-se transfer is still on the page",
          f"{name!r} / {category!r} / {mode!r}")

# A family trust is NOT one of these. "Adivam Family Trust" is somebody's own
# money taking a view, which is the whole point of reading this - so the
# category alone must never be enough.
MUST_STAY = [
    ("Adivam Family Trust", "Trust", "Market Purchase"),
    ("Sulabhya Paramita Private Trust", "Promoter Group", "Pledge Release"),
    ("Kalidindi Ravi", "Promoter and Director", "Market Purchase"),
    ("Shalinee Gurtu", "Promoter Group", "Inheritance"),
    ("Sanjay Purohit", "Director", "Market Sale"),
    ("JSL Overseas Holding Limited", "Promoter Group", "Market Purchase"),
]
for name, category, mode in MUST_STAY:
    check(insider.skip_reason({"who": name, "category": category,
                               "mode": mode}) is None,
          "a real insider trade was thrown away with the employee schemes",
          f"{name!r} / {category!r} / {mode!r}")


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

rows, added, dropped = pi.merge(
    [], [FILING_A, FILING_B, FILING_C, dict(FILING_A)])
check(len(rows) == 3 and added == 3,
      "merging three distinct filings and one repeat should give three",
      f"{len(rows)} rows, {added} added")

# A structured row and a filing row never share a key, whatever else matches.
check(pi.trade_key(STRUCTURED_A) != pi.trade_key(FILING_A),
      "a structured trade and a document row share a key")


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 6. A summary that admits it found nothing
#
# Lloyds Metals' Regulation 31 disclosure was summarised as "The company
# disclosed a financing-related arrangement, but the filing provides no
# material business or financial update", and it sat on the insider page
# between two real promoter purchases. Nobody can tell from it who traded what.
#
# The line this must not cross: a real promoter sale often ends by saying the
# sale has no material IMPACT on the business. That sentence is about the
# company, not about whether the filing said anything.
# ---------------------------------------------------------------------------

import publish_insider                                     # noqa: E402

NOTHING = [
    "The company disclosed a financing-related arrangement, but the filing "
    "provides no material business or financial update.",
    "The filing does not disclose the number of shares traded.",
    "No specific details were provided in this disclosure.",
]
for text in NOTHING:
    check(bool(publish_insider._NOTHING_TO_SAY.search(text)),
          "an empty summary was kept as an insider trade", text[:60])

SOMETHING = [
    "Promoter Brij Rattan Bagri bought 90,503 BLB Ltd shares on 10 Sept 2026.",
    "Granules India disclosed that promoter Chigurupati sold 1.72 crore "
    "shares, with no material impact on operations.",
    "Peterhouse Investments sold 150,000 equity shares in the open market. "
    "The company said there is no change in its board.",
]
for text in SOMETHING:
    check(not publish_insider._NOTHING_TO_SAY.search(text),
          "a real trade was thrown away as an empty summary", text[:60])


# ---------------------------------------------------------------------------
# 7. Tightening a rule has to clean what a looser rule already wrote
#
# Ten Eclerx Employee Welfare trades survived TWO widenings of the exclusion,
# because a day is written under the rules of the day it was written and then
# sits there for a week. Nothing ever asked the stored rows the question
# again. merge() asks now, on the way past, so the next pass over a day is
# also a sweep of it.
# ---------------------------------------------------------------------------

STORED_UNDER_OLD_RULES = [
    {"symbol": "ECLERX", "who": "Eclerx Employee Welfare", "category": "Trust",
     "shares": 16900, "value": 32071369, "mode": "Market Purchase",
     "traded_on": "2026-09-09", "headline": "..."},
    {"symbol": "FSL", "who": "Firstsource Employee Benefit Trust",
     "category": "Trust", "shares": 65898, "value": 658980,
     "mode": "Off Market", "traded_on": "2026-09-09", "headline": "..."},
    {"symbol": "NCLIND", "who": "Kalidindi Ravi",
     "category": "Promoter and Director", "shares": 800, "value": 141200,
     "mode": "Market Purchase", "traded_on": "2026-09-11", "headline": "..."},
]
rows, added, dropped = pi.merge(STORED_UNDER_OLD_RULES, [])
check(dropped == 2, "stored employee-trust rows were not swept out",
      f"{dropped} dropped of 3")
check(len(rows) == 1 and rows[0]["who"] == "Kalidindi Ravi",
      "the sweep took a real trade with it", str([r["who"] for r in rows]))

# It must never take a row out for being small or dull - only for being
# something Ishan said should not be on the page at all.
SMALL_BUT_REAL = [{"symbol": "TIRUPATI", "who": "Kalpesh B Kothari",
                   "category": "Promoter Group", "shares": 18, "value": 900,
                   "mode": "Market Sale", "traded_on": "2026-09-10",
                   "headline": "..."}]
rows, added, dropped = pi.merge(SMALL_BUT_REAL, [])
check(dropped == 0 and len(rows) == 1,
      "an eighteen-share promoter sale was swept out as noise")

# A prose row has no fields to judge, so it is judged on its sentence.
PROSE = [
    {"company": "Some Ltd", "filed_on": "2026-09-11", "who": "",
     "headline": "The company allotted shares under its ESOP scheme to 40 "
                 "employees."},
    {"company": "Other Ltd", "filed_on": "2026-09-11", "who": "",
     "headline": "Promoter Brij Rattan Bagri bought 90,503 shares on the "
                 "open market."},
]
rows, added, dropped = pi.merge(PROSE, [])
check(dropped == 1, "an ESOP allotment described in prose was kept",
      f"{dropped} dropped of 2")
check(len(rows) == 1 and "Bagri" in rows[0]["headline"],
      "the prose sweep took the real one", str(rows))


print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")

"""Guards on the scoring rules, so the same kind of mistake cannot come back.

Every case here is a real bug that reached the live site. The pattern is always
the same: a word that reads unambiguously in a short exchange headline turns out
to be ordinary English, and score_text() runs the same patterns over four
thousand characters of a PDF where ordinary English is everywhere.

    python tests/test_rules.py

Exits non-zero on the first failure, and the scrape workflow runs it before
publishing anything, so a rule that would mislabel filings never reaches the
dashboard.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rules                                            # noqa: E402

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(f"{label}\n      {detail}")


# ---------------------------------------------------------------------------
# 1. Prose that must never be promoted.
#
# These are sentences of the kind that appear inside real filings - most of
# them lifted from documents that were actually mislabelled. None describes a
# corporate action, so none may reach the 55 that puts a filing on the front
# page.
# ---------------------------------------------------------------------------
INNOCUOUS = [
    # matched "capex" - a filing announcing a new President of Manufacturing
    "Mr Alvi will oversee manufacturing operations and capex for the plants",
    # matched "guidance" - a chief general manager's resignation
    "The Company follows SEBI guidance on related party transactions",
    "He resigned to pursue better career prospects and sought guidance from the board",
    # matched "warrants" the verb
    "The Board is of the view that the matter warrants disclosure under Regulation 30",
    "Search warrant issued by the Income Tax Department at the registered office",
    "the development warrants an intimation to the exchange under Regulation 30",
    # matched "SAST" - the name of the regulations, not an event
    "Disclosure under Regulation 29(2) of the SEBI (SAST) Regulations, 2011",
    # matched "scheduled to be held on" at the top level of a downgrade rule
    "The next board meeting is scheduled to be held on 30 September 2026",
    # ordinary board minutes, one routine item among many
    "The Board took note of the appointment of the Internal Auditor for FY 2026-27",
    "Appointment of Cost Auditor for the financial year ending 31 March 2027",
    # an AGM notice, which carries the whole year's accounts as an annexure
    "Notice of the 102nd Annual General Meeting of the Bank",
    "Notice is hereby given that the 30th Annual General Meeting will be held via VC",
    # routine compliance
    "Certificate under Regulation 74(5) of the SEBI (Depositories) Regulations",
    "Intimation of the record date for the purpose of the annual general meeting",
    # "acquired" as plain English - caught while widening Acquisition to cover
    # the future tense, which briefly scored all four of these at 65
    "The auditor acquired an understanding of the internal controls",
    "knowledge acquired through years of operating experience in the sector",
    "The land was acquired long ago and is recorded at historical cost",
]

for text in INNOCUOUS:
    for label, got in (("headline", rules.score("General Updates", text)),
                       ("document", rules.score_text(text * 3, floor=55))):
        check(got[0] < 55,
              f"prose scored as important ({label})",
              f"{got} <- {text[:70]!r}")


# ---------------------------------------------------------------------------
# 2. Real filings that must keep working.
#
# The other half of every fix: tightening a pattern is only correct if it
# still catches the thing it was written for.
# ---------------------------------------------------------------------------
REAL = [
    ("Receipt of Order",                                          "Order"),
    ("Receipt of order worth Rs 500 crore from NHAI",             "Order"),
    ("Bagging of order pursuant to Regulation 30",                "Order"),
    ("Allotment of 60,82,000 convertible warrants to promoters",  "Warrants"),
    ("Issue of warrants on preferential basis",                   "Warrants"),
    ("Capex plan of Rs 1,200 crore for the new facility",         "Capacity Increase"),
    ("Commissioning of the new plant at Dahej",                   "Capacity Increase"),
    ("Monthly business update for August 2026",                   "Business Update"),
    ("Revenue guidance raised to Rs 500 crore",                   "Business Update"),
    ("Buyback of equity shares through the tender offer route",   "Buyback"),
    ("Unaudited Financial Results for the quarter ended June 2025", "Results"),
    ("Audited Financial Results for the quarter ended 30.6.2025",  "Results"),
    ("Open Offer to the public shareholders of Alpha Limited",     "Open Offer"),
    ("Scheme of Amalgamation between Alpha and Beta",              "Scheme Of Arrangement"),
    ("Completed acquisition of 100% of Alpha Private Limited",     "Acquisition"),
    # the future tense, which is how a deal is announced on the day it is news
    ("The Company will acquire a 51% stake in Alpha Limited",       "Acquisition"),
    ("Agreed to acquire the packaging business of Beta Ltd",        "Acquisition"),
    ("Company is acquiring control of Gamma LLP",                   "Acquisition"),
]

for text, want in REAL:
    pts, tag = rules.score("General Updates", text)
    check(tag == want and pts >= 55,
          "a real filing stopped being recognised",
          f"wanted {want}, got {(pts, tag)} <- {text[:60]!r}")


# ---------------------------------------------------------------------------
# 2b. A promoter dealing in shares is not the company acquiring anything.
#
# Both are written with the same verbs, so points alone cannot separate them -
# Acquisition scores 65 and always beat Promoter Buy/Sell at 58. 52 of 216
# filings under Acquisition were a promoter buying or selling shares in his own
# company. What separates them is the actor, not the wording.
# ---------------------------------------------------------------------------
PROMOTER = [
    "Mr Halwasiya, a promoter of the Company, has acquired 8,60,688 equity shares",
    "Promoter entity Epsilon Bidco Pte Ltd has sold its entire stake in the Company",
    "Internal transfer of shares between members of the promoter group",
    "Inter-se transfer of equity shares among members of the promoter group",
    "A promoter group entity has pledged 15,00,000 equity shares with the lender",
    "Promoters plan to sell up to 2% of their stake in the open market",
    "Creation of encumbrance over shares held by the promoter group",
]
for text in PROMOTER:
    for label, got in (("headline", rules.score("General Updates", text)),
                       ("document", rules.score_text(text * 3, floor=55))):
        check(got[1] == "Promoter Buy/Sell",
              f"promoter share dealing filed as something else ({label})",
              f"{got} <- {text[:66]!r}")

# ...and the other half: a real corporate deal must not be dragged into it,
# even when a promoter is named in the same document.
CORPORATE = [
    ("The Board approved the acquisition of 100% of Alpha Private Limited",
     "Acquisition"),
    ("ITC subsidiary will acquire a 22.1% stake in Happiest Minds Limited",
     "Acquisition"),
    ("Promoter-led company completes acquisition of Beta Limited as a "
     "wholly-owned subsidiary", "Acquisition"),
    ("Scheme of Amalgamation between Alpha and Beta approved by the promoters",
     "Scheme Of Arrangement"),
    ("Buyback of equity shares approved by the promoters and the board",
     "Buyback"),
]
for text, want in CORPORATE:
    pts, tag = rules.score("General Updates", text)
    check(tag == want,
          "a corporate deal was mistaken for promoter share dealing",
          f"wanted {want}, got {(pts, tag)} <- {text[:60]!r}")


# ---------------------------------------------------------------------------
# 3. The rule behind all of it: no topic may be reached by one ordinary word.
#
# Tested by behaviour rather than by reading the patterns. An earlier version
# of this split each pattern on "|" and complained about the pieces, which
# reported "offer" as a branch of Open Offer when the real pattern reads
# "public announcement.{0,25}(acquisition|offer)" - the word only counts when
# it follows a public announcement. Splitting a regex on a metacharacter does
# not give you its alternatives; running it does.
# ---------------------------------------------------------------------------
ORDINARY = [
    "guidance", "capex", "warrant", "warrants", "order", "orders", "update",
    "meeting", "issue", "notice", "report", "change", "approval", "scheme",
    "plan", "record", "action", "offer", "result", "capital", "shares",
    "acquired", "acquire",
    "board", "director", "auditor", "letter", "statement", "disclosure",
]

# Sentences that mention the word and describe nothing at all.
FRAMES = [
    "The company received a routine {} from the registrar this morning.",
    "Please refer to our earlier {} in this regard for further particulars.",
    "The secretary confirmed that the {} had been placed on the website.",
]

for word in ORDINARY:
    for frame in FRAMES:
        sentence = frame.format(word)
        pts, tag = rules.score("General Updates", sentence)
        check(pts < 55,
              "one ordinary word was enough to reach the front page",
              f"{(pts, tag)} <- {sentence!r}")
        pts, tag = rules.score_text(sentence * 4, floor=55)
        check(pts < 55,
              "one ordinary word was enough to promote a document",
              f"{(pts, tag)} <- {word!r} in prose")


# ---------------------------------------------------------------------------
# 4. A cached promotion must obey the same block a fresh read does.
#
# triage checked NEVER_PROMOTE only when reading a document for the first time.
# Anything promoted before a category joined that list kept its wrong tag for
# ever, because the cached verdict was applied without asking. 161 filings were
# in that state - a statutory auditor's appointment published as an Acquisition
# among them - and no number of re-runs would have cleared them.
# ---------------------------------------------------------------------------
import triage                                            # noqa: E402

BLOCKED_CATEGORIES = [
    "Company Update / Appointment of Statutory Auditor/s",
    "Company Update / Change in Directorate",
    "Company Update / Resignation of Director",
    "AGM/EGM / AGM",
    "Shareholders meeting",
    "Others / Reg. 34 (1) Annual Report",
]
for cat in BLOCKED_CATEGORIES:
    check(triage._blocked({"category": cat, "headline": "anything at all"}),
          "a category that should never be promoted from its document is not blocked",
          repr(cat))

# ...and the categories that MUST still be read, because only the document can
# say what the filing is.
READ_THESE = [
    "General Updates",
    "Company Update / General",
    "Outcome of Board Meeting",
    "Board Meeting / Outcome of Board Meeting",
    "Corp. Action / Record Date",
    "Corp. Action / Book Closure",
    "Company Update / General",
]
for cat in READ_THESE:
    check(not triage._blocked({"category": cat, "headline": "Press release"}),
          "a vague category was blocked from being read",
          repr(cat))

# The headline must not be able to trigger a category block on its own: a court
# order that merely mentions an AGM is still a court order.
check(not triage._blocked({"category": "Company Update / General",
                           "headline": "Updation of Order from NCLT for AGM"}),
      "a headline mentioning a meeting blocked a real filing",
      "NCLT order blocked by the letters AGM")


# ---------------------------------------------------------------------------
# 5. A stake disclosure is never scored off the form's own list of options.
#
# Every SAST filing arrives on a SEBI template printing the line
#   "Mode of sale (e.g. open market / public issue / rights issue /
#    preferential allotment / inter-se transfer / encumbrance, etc.)"
# which, read as prose, matches Rights Issue 68, Acquisition 65, Warrants 61
# and Pref 60. A mutual fund buying 43,780 shares was published as a rights
# issue. The category already says these are stake disclosures, so the document
# is asked one question only: whose stake moved.
# ---------------------------------------------------------------------------
STAKE_CATS = [
    "Insider Trading / SAST / Disclosures under Reg. 29(2) of SEBI (SAST) Regulations, 2011",
    "Insider Trading / SAST / Disclosure under SEBI (SAST) Regulations",
    "Disclosure under SEBI Takeover Regulations",
    "Insider Trading / SAST / Disclosures under Reg. 10(6) of SEBI (SAST)",
]
for cat in STAKE_CATS:
    check(triage._is_stake({"category": cat}),
          "a stake-disclosure category was not recognised as one", repr(cat))

for cat in ("General Updates", "Outcome of Board Meeting", "Company Update / Acquisition"):
    check(not triage._is_stake({"category": cat}),
          "an ordinary category was treated as a stake disclosure", repr(cat))

# The form's own option list must decide nothing.
FORM_BOILERPLATE = (
    "Mode of sale (e.g. open market / public issue / rights issue / "
    "preferential allotment / inter-se transfer / encumbrance, etc.) "
    "Salient features of the securities acquired 27,64,510 7.0672"
)
check(triage.stake_verdict(FORM_BOILERPLATE) == {},
      "the blank form's option list still promotes a stake disclosure",
      repr(triage.stake_verdict(FORM_BOILERPLATE)))

# ...but a promoter in the same document still counts.
check(triage.stake_verdict(
        "Mr Halwasiya, a promoter of the Company, has acquired 8,60,688 shares "
        + FORM_BOILERPLATE).get("t") == "Promoter Buy/Sell",
      "a promoter's own dealing was lost when stake scoring was tightened")


# ---------------------------------------------------------------------------

print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")
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
import pipeline                                         # noqa: E402

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
# Shares moving inside the promoter family. Filed on the same SAST forms as a
# real acquisition and worded identically - "acquired 40.94 lakh shares" - but
# no money changes hands and nobody has bought or sold anything, so it carries
# neither of the signals Promoter Buy/Sell exists to show. SEBI exempts it from
# the open offer rules for the same reason.
#
# These were being published as Open Offer, which is its literal opposite: the
# summary explains the exemption, and the words are in the sentence. Jeyyam
# Global Foods and two Sanghvi Movers filings, 3 September.
INTERSE = [
    "Internal transfer of shares between members of the promoter group",
    "Inter-se transfer of equity shares among members of the promoter group",
    "Siddharrth Mehta acquired 40.94 lakh shares from Shrreyans Mehta via a "
    "gift deed. The transfer is exempt from an open offer under SEBI rules.",
    "Transferring 1,05,53,614 shares from Mr Rishi Sanghvi to his spouse "
    "Mrs Maithili Rishi Sanghvi as a gift. No consideration is payable.",
    "Disclosure under Regulation 10(6) in respect of an acquisition made "
    "under Regulation 10(1)(a) of the SEBI Takeover Regulations",
]
for text in INTERSE:
    pts, tag = rules.score_text(text, floor=0)
    check(tag in ("Inter-se Transfer", None) and pts < 55,
          "a gift inside the promoter family is being sold as an event",
          f"{(pts, tag)} <- {text[:62]!r}")
    check(not rules.promoter_deal(text),
          "an inter-se transfer is being counted as promoter buying or selling",
          f"{text[:62]!r}")

# A real open offer is the opposite case and must survive all of that.
for text in [
    "Detailed Public Statement in respect of the open offer to public shareholders",
    "Axis Capital Limited, Manager to the Offer, has submitted the post offer "
    "advertisement",
    "Public announcement for the acquisition of 26% of the equity share capital",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Open Offer",
          "a real open offer stopped being recognised",
          f"{(pts, tag)} <- {text[:62]!r}")


PROMOTER = [
    "Mr Halwasiya, a promoter of the Company, has acquired 8,60,688 equity shares",
    "Promoter entity Epsilon Bidco Pte Ltd has sold its entire stake in the Company",
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
    # The first version of this list spelled out exact wordings and missed the
    # commonest ones. These five cover 48 filings between them, and a letter
    # about a person carries their CV: Deepak Fertilizers appointing a
    # President of Manufacturing was published as a Capacity Increase because
    # his remit mentioned capex.
    "Company Update / Change in Management",
    "Change in Management",
    "Appointment",
    "Cessation",
    "Company Update / Cessation",
    "Change in Auditors",
    "Resignation",
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
# 6. Words that belong to something else in the document.
#
# Every one of these was live on the site. None is about the thing it was
# filed under; in each case the phrase belongs to a different sentence
# entirely - a party's name, a trading-window paragraph, a website breadcrumb.
# ---------------------------------------------------------------------------
BORROWED = [
    # "Joint Venture of OHL International" is the name of the other side in a
    # lawsuit. Voltas was filed as an Acquisition.
    ("legal matter relating to the claim and counter claim filed by the Company "
     "and Joint Venture of OHL International, Spain, and Contrack Cyprus",
     "Acquisition"),
    # The trading-window paragraph in every board-meeting notice mentions the
    # results that are coming. Natural Capsules was filed as Results.
    ("The trading window shall remain closed till 48 hours after declaration of "
     "the outcome of this Board Meeting regarding the financial results for the "
     "quarter ended June 30 2026", "Results"),
    # A navigation path printed inside an AGM notice. Physicswallah was filed
    # as Results.
    ("Notice of the 6th Annual General Meeting. The annual report is at "
     "Path: www.pw.live/investor-relations > Financial Results > Annual Report",
     "Results"),
]
for text, must_not_be in BORROWED:
    pts, tag = rules.score_text(text * 3, floor=55)
    check(tag != must_not_be and pts < 55,
          f"a borrowed phrase still promotes a filing to {must_not_be}",
          f"{(pts, tag)} <- {text[:64]!r}")

# The same words, genuinely used, must still work.
GENUINE = [
    ("The Company has entered into a joint venture with Beta Limited to build "
     "a plant at Dahej", "Acquisition"),
    ("Unaudited Financial Results for the quarter ended June 2026 were approved. "
     "Revenue Rs 412 crore, profit after tax Rs 38 crore", "Results"),
]
for text, want in GENUINE:
    pts, tag = rules.score_text(text * 3, floor=55)
    check(tag == want,
          "tightening a pattern lost the thing it was written for",
          f"wanted {want}, got {(pts, tag)} <- {text[:56]!r}")


# ---------------------------------------------------------------------------
# 7. The two things the summary must not be allowed to decide.
#
# The category is taken from the AI summary rather than the raw PDF, because a
# document contains many sentences about many things and only one of them is
# what the filing is. But the summary describes CONTENT, and that misleads in
# two specific ways.
# ---------------------------------------------------------------------------

# A concall summary describes what was discussed, which is the quarter's
# results. Scoring it moved 17 concalls and investor meets into Results.
CONCALL_SUMMARY = ("Juniper Green Energy reported its first quarterly results "
                   "as a listed company, with revenue of Rs 412 crore and "
                   "profit after tax up 30 per cent")
_, would_be = rules.score_text(CONCALL_SUMMARY, floor=0)
check(would_be == "Results",
      "the test case no longer demonstrates the problem it guards",
      f"expected a concall summary to score Results, got {would_be}")
check("Concall" in rules._MEETING_TAGS and "Investor Meet" in rules._MEETING_TAGS,
      "the meeting tags are no longer protected from summary re-tagging")

# A dividend whose summary mentions the meeting that will approve it is still a
# dividend. Fourteen were being relabelled "Meeting", which scores 22 and would
# have dropped them off the page.
DIVIDEND_SUMMARY = ("The Board recommended a final dividend of Rs 5 per equity "
                    "share, subject to approval of the members at the ensuing "
                    "Annual General Meeting")
pts, tag = rules.score_text(DIVIDEND_SUMMARY, floor=0)
# The guard in pipeline.py refuses any summary verdict scoring under 55, so
# what matters is that a below-bar tag can never be adopted. Assert the tag
# this summary yields is either the right one, or one the guard will reject.
check(tag == "Dividend" or pts < 55,
      "a dividend summary yields an above-bar tag that is not Dividend",
      f"{(pts, tag)} - the pipeline guard would adopt this")


# ---------------------------------------------------------------------------
# 8. A general meeting notice is one thing, wherever it arrives.
#
# An AGM notice carries the whole year with it - the accounts, the dividend
# resolution, the reappointment of auditors, the enabling resolution for a
# preferential issue or a QIP. Scored on any of that, one document was landing
# under a dozen headings at once: Pref, Qip, Warrants, Acquisition, Business
# Update, Nclt. The notice now wins outright.
# ---------------------------------------------------------------------------
NOTICES = [
    ("AGM/EGM / AGM", "Notice of the 102nd Annual General Meeting"),
    ("General Updates",
     "Physicswallah has announced the schedule for its 6th Annual General Meeting"),
    ("Company Update / Preferential Issue",
     "Notice of the 27th AGM including the enabling resolution for a preferential issue"),
    ("Shareholders meeting", "Intimation of AGM and e-voting details"),
    ("Company Update / General",
     "Convening of the Extraordinary General Meeting on 20 September"),
    ("Updates", "The 41st AGM of the company is scheduled to be held on Friday"),
]
for cat, head in NOTICES:
    pts, tag = rules.score(cat, head)
    check(tag == "Meeting",
          "a general meeting notice was filed under something else",
          f"{(pts, tag)} <- {head[:60]!r}")

# The other half, and the more dangerous one. A dividend declared subject to
# approval at the AGM is a dividend - 152 filings say so - and demoting those
# would be a worse mistake than the one being fixed.
MENTIONS_ONLY = [
    ("Corp. Action / Dividend",
     "Board recommended a final dividend of Rs 5, subject to approval at the ensuing AGM",
     "Dividend"),
    ("Company Update / General",
     "Board declared an interim dividend; the AGM will be held later", "Dividend"),
    ("Board Meeting / Outcome",
     "Approved unaudited results for Q1 and noted the AGM date", "Results"),
]
for cat, head, want in MENTIONS_ONLY:
    pts, tag = rules.score(cat, head)
    check(tag == want,
          "a filing that merely mentions a meeting was demoted to Meeting",
          f"wanted {want}, got {(pts, tag)} <- {head[:56]!r}")


# ---------------------------------------------------------------------------
# 9. No pattern may contain a control character.
#
# Writing these files through shell heredocs has repeatedly turned the two
# characters backslash and b into a single 0x08 backspace, silently. The pattern still
# compiles and still matches most things, so nothing fails loudly - it just
# quietly stops respecting word boundaries. Fifteen of them went in at once on
# 2 September and were only noticed by printing a pattern by hand.
# ---------------------------------------------------------------------------
for name in dir(rules):
    obj = getattr(rules, name)
    pat = getattr(obj, "pattern", None)
    if not isinstance(pat, str):
        continue
    bad = [hex(ord(ch)) for ch in pat if ord(ch) < 32 and ch not in (chr(10) + chr(9))]
    check(not bad,
          f"rules.{name} contains a control character - a mangled escape",
          f"found {bad[:4]} in {pat[:60]!r}")

for tag, pts, rx in rules._TOPIC_RE:
    bad = [hex(ord(ch)) for ch in rx.pattern if ord(ch) < 32 and ch not in (chr(10) + chr(9))]
    check(not bad,
          f"the {tag!r} pattern contains a control character",
          f"found {bad[:4]}")

# The two checks above only see COMPILED patterns in rules.py. triage.py keeps
# its lists as plain strings and compiles them where they are used, so nothing
# looked at them - and a mangled "a word-boundary escape around 'sast'" sat there for a day, unnoticed,
# with the alternatives on either side of it masking the damage. The category
# BSE uses is "Insider Trading / SAST", which still matched on "insider
# trading"; a category naming only SAST did not, and got scored as prose.
#
# So the real check is on the bytes of the files themselves. Nothing to keep
# in step, and it sees comments and plain strings too.
for fname in ("rules.py", "triage.py", "pipeline.py", "tests/test_rules.py",
              "tools/audit_categories.py", "newsletter.py", "summarize.py"):
    raw = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), fname), "rb").read()
    found = sorted({b for b in raw if b < 9 or 11 <= b <= 12 or 14 <= b <= 31})
    check(not found,
          f"{fname} contains a control character - a shell-mangled escape",
          f"found bytes {[hex(b) for b in found]}")


# ---------------------------------------------------------------------------
# 10. Nothing but a deal goes in Acquisition.
#
# Taken verbatim from filings that were sitting under Acquisition on the live
# site on 2 September. None is a deal. Acquisition is the category a reader
# looks at first, so anything wrong there is the most visible mistake the
# product can make.
# ---------------------------------------------------------------------------
NOT_ACQUISITIONS = [
    ("Shareholders meeting",
     "Mold-Tek Technologies has announced its 42nd Annual General Meeting"),
    ("Corp. Action / Book Closure",
     "Haryana Leather Chemicals has announced the closure of its share transfer "
     "books for the annual general meeting"),
    ("Company Update / Press Release / Media Release",
     "Hexaware Technologies has appointed Vivek Jetley as its new CEO"),
    ("Company Update / General",
     "NHPC has appointed various firms of Cost Accountants to conduct cost audits"),
    ("Corp Action / Daily Buy Back of equity shares",
     "SIS Ltd reported its daily share buy-back, purchasing 10,000 shares"),
    ("Amendment to AOA/MOA",
     "Shareholders approved an amendment to the Memorandum of Association"),
    ("Company Update / Change in Management",
     "Deepak Fertilizers has appointed Amir Alvi as President of Manufacturing "
     "Operations, whose remit includes capex"),
    ("Company Update / Appointment of Statutory Auditor/s",
     "Approved the appointment of M/s Shah Karia & Associates as Statutory "
     "Auditor. The firm's services include Merger & Acquisition advisory"),
]

# The same, judged from a summary rather than a headline - which is the path
# that actually decides a category now. These were left under Acquisition
# because the pattern wanted the noun "appointment" and a summary writes the
# verb: "has appointed Vivek Jetley as its new CEO".
MANAGEMENT_SUMMARIES = [
    "Hexaware Technologies has appointed Vivek Jetley as its new CEO",
    "NHPC has appointed various firms of Cost Accountants to conduct cost audits",
    "Ms Kundu was appointed an Additional Independent Woman Director",
    "The company appointed Mr Sheth as a Non-Executive Nominee Director",
    "Deepak Fertilisers appointed Amir Alvi as President-Manufacturing",
]
for text in MANAGEMENT_SUMMARIES:
    pts, tag = rules.score_text(text, floor=0)
    check(tag in ("Change In Management", "Resignation"),
          "a management change was not recognised from its summary",
          f"{(pts, tag)} <- {text[:60]!r}")
for cat, head in NOT_ACQUISITIONS:
    pts, tag = rules.score(cat, head)
    check(tag != "Acquisition",
          "something that is not a deal was filed under Acquisition",
          f"{(pts, tag)} <- {cat[:34]!r} / {head[:48]!r}")

# And the deals themselves must survive all of that.
REAL_DEALS = [
    ("Company Update / Acquisition",
     "Fine Organic Industries has agreed to buy 80% of Oleofine Organics"),
    ("Company Update / General",
     "ITC subsidiary will acquire a 22.1% stake in Happiest Minds Limited"),
    ("General Updates",
     "Completed the acquisition of 100% of Alpha Private Limited for Rs 260 crore"),
    ("Company Update / General",
     "The Company has entered into a joint venture with Beta Limited"),
]
for cat, head in REAL_DEALS:
    pts, tag = rules.score(cat, head)
    check(tag in ("Acquisition", "Scheme Of Arrangement") and pts >= 55,
          "a real deal stopped being recognised as one",
          f"{(pts, tag)} <- {head[:60]!r}")


# ---------------------------------------------------------------------------
# 11. An order from a government is not an order from a customer.
#
# The exchanges file both under "Award of Order / Receipt of Order", so the
# heading cannot tell them apart. MOIL's demand notice for unpaid water tax was
# published as an order win, and Darjeeling Industries' government approval to
# shift its registered office as another. Who the order came FROM settles it: a
# customer places one, a registrar or a tribunal issues one.
# ---------------------------------------------------------------------------
GOVERNMENT_ORDERS = [
    ("Company Update / Award of Order",
     "MOIL has received a demand notice from the Wainganga Division for unpaid water tax"),
    ("Company Update / General",
     "Receipt of Order: government approval to shift the registered office"),
    ("Award of Order / Receipt of Order",
     "Receipt of order from the Registrar of Companies sanctioning the shift"),
    ("General Updates", "Recovery notice received from the tax department"),
    ("Award of Order / Receipt of Order", "Order issued by the Commissioner of Customs"),
]
for cat, head in GOVERNMENT_ORDERS:
    pts, tag = rules.score(cat, head)
    check(tag != "Order",
          "a government order was published as an order win",
          f"{(pts, tag)} <- {head[:60]!r}")

CUSTOMER_ORDERS = [
    ("Award of Order / Receipt of Order", "Receipt of order worth Rs 500 crore from NHAI"),
    ("General Updates", "Bagging of order for supply of transformers worth Rs 87 crore"),
    ("Company Update / General", "Letter of Award received from Indian Railways"),
    ("General Updates",
     "Time Technoplast secures order of Rs 87.53 crore for supply of cylinders"),
    ("Award of Order / Receipt of Order", "Receipt of work order from Tata Projects Limited"),
]
for cat, head in CUSTOMER_ORDERS:
    pts, tag = rules.score(cat, head)
    check(tag == "Order" and pts >= 55,
          "a real order win stopped being recognised",
          f"{(pts, tag)} <- {head[:60]!r}")


# ---------------------------------------------------------------------------
# 12. A notice of a meeting is a Meeting, whichever door it comes in by
#
# A general meeting notice lists every resolution to be put to the vote, so
# read as prose it looks like whatever the meeting will decide: an AGM notice
# carrying an enabling resolution for a preferential issue scored 60 and was
# published as Pref. Eight of the twenty-three filings under Pref on 3
# September were meeting notices.
#
# There are three doors into a category and the fix had to be at all three.
# It was first put only on score(), which reads the headline; score_text(),
# which reads the PDF and the AI summary, went on tagging them Pref. And
# score_text() returns early when no topic matches at all - a notice matches
# no topic, being an invitation rather than an event - so the answer had to
# come before that return, not after it.
# ---------------------------------------------------------------------------

# The decision is pipeline.category_from_summary(category, headline, blob) -
# the real one, called here rather than reimplemented, because a copy of it in
# the tests is what let the last regression through.
#
# Each entry is (category, headline, summary).
MEETING_NOTICES = [
    ("General Updates",
     "Texmo Pipes has issued a corrigendum to its 18th Annual General Meeting notice",
     "The corrigendum revises the enabling resolution for a preferential issue "
     "of up to 25 lakh equity shares to be placed before the members."),
    ("Company Update",
     "Alstone Textiles - intimation of Annual General Meeting",
     "Alstone Textiles has scheduled its 41st Annual General Meeting for "
     "September 24, 2026."),
    ("Shareholders meeting",
     "Notice of the 27th AGM",
     "The notice includes an enabling resolution for a preferential issue of "
     "equity shares and warrants."),
    ("General Updates",
     "Ind-Swift Laboratories will hold its Extraordinary General Meeting on October 3",
     "The EGM will consider approval for raising funds by way of a qualified "
     "institutional placement."),
    ("Others",
     "Notice of postal ballot",
     "The postal ballot seeks approval for the issue of convertible warrants "
     "on a preferential basis."),
]
for cat, head, summ in MEETING_NOTICES:
    got = pipeline.category_from_summary(cat, head, head + " " + summ)
    check(got == "Meeting",
          "a meeting notice is being filed as the thing the meeting will decide",
          f"got {got!r} <- {head[:58]!r}")

# The other half, and the one the first attempt at this broke. Every summary
# below mentions the meeting; in none of them is the meeting the news. These
# are verbatim from filings that were renamed "Meeting" on 3 September.
MEETING_IS_ONLY_CONTEXT = [
    ("Corp. Action / Record Date",
     "Sunteck Realty Limited has informed the Exchange that Record date for "
     "the purpose of Dividend is 17-Sep-2026.",
     "Sunteck Realty has announced that the record date for its upcoming "
     "dividend is September 17, 2026. The company also scheduled its 43rd "
     "Annual General Meeting for September 22.",
     "Dividend"),
    ("Announcement under Regulation 30",
     "Pursuant to Regulation 30 of the SEBI LODR Regulations, we enclose the "
     "voting outcome",
     "Foseco Crucible (India) Ltd announced that shareholders have approved a "
     "final dividend at its 41st Annual General Meeting. The dividend payout "
     "is set at Rs. 12.50 per equity share.",
     "Dividend"),
    ("Company Update",
     "Outcome of board meeting",
     "The board approved a preferential issue of 10 lakh equity shares at "
     "Rs 161 each. The issue will be placed before members at the annual "
     "general meeting.",
     "Pref"),
    ("General Updates",
     "Receipt of order from NHAI",
     "The company received an order worth Rs 500 crore from NHAI. The order "
     "was noted at the board meeting held before the annual general meeting.",
     "Order"),
]
for cat, head, summ, want in MEETING_IS_ONLY_CONTEXT:
    got = pipeline.category_from_summary(cat, head, head + " " + summ)
    check(got in (want, None),
          "a real event was renamed Meeting because its summary mentions the AGM",
          f"got {got!r}, wanted {want!r} or no change <- {head[:52]!r}")

# score_text on its own must NOT answer "Meeting" when the text names an event.
# That was the too-strong version: it beat the dividend it was sitting next to.
for _, _, summ, want in MEETING_IS_ONLY_CONTEXT:
    pts, tag = rules.score_text(summ, floor=0)
    check(tag != "Meeting" or want is None,
          "score_text lets a mentioned meeting outrank the event itself",
          f"{(pts, tag)} <- {summ[:58]!r}")


# ---------------------------------------------------------------------------
# 13. The paperwork that follows an event is not the event
#
# Every one of these recites, in full, the thing it is reporting on - which is
# why each was published as that thing. A buyback's daily purchase report is
# filed once per trading day for the length of the programme; a monitoring
# agency report says how an issue's proceeds are being spent; an amended set
# of articles lists every class of share the company may ever issue.
# ---------------------------------------------------------------------------

FOLLOW_UP_PAPERWORK = [
    ("Buy-back of Securities",
     "Daily Report pursuant to Regulation 18(i) of the Buyback Regulations "
     "regarding the equity shares bought back on September 2"),
    ("Buy-back of Securities",
     "Pursuant to Regulation 18(i) of the Buyback Regulations regarding the "
     "equity shares bought back"),
    ("General Updates", "Monitoring Agency Report for the quarter"),
    ("Rights Issue",
     "Reminder Notice to pay Call Money pursuant to Rights Issue partly paid"),
    ("General Updates", "Date of connectivity informed by CDSL"),
]
for cat, head in FOLLOW_UP_PAPERWORK:
    pts, tag = rules.score(cat, head)
    check(pts < 55,
          "a follow-up report is being published as the event it reports on",
          f"{(pts, tag)} <- {head[:64]!r}")

# ...and triage must not put back what the headline rules just took out. The
# document says everything the headline was junked for saying.
for cat, head in FOLLOW_UP_PAPERWORK[:3]:
    check(triage._blocked({"category": cat, "headline": head}),
          "triage will read this document and promote it back",
          f"{cat!r} / {head[:52]!r}")

# The articles of association, blocked on the CATEGORY alone. The document is
# a warrant announcement, a preference share announcement and a debenture
# announcement all at once, because it lists the whole authorised capital.
for cat in ["Amendments to Memorandum & Articles of Association",
            "Alteration of MOA", "Adoption of new AOA"]:
    check(triage._blocked({"category": cat, "headline": "Outcome of board meeting"}),
          "an amended memorandum will be read as an issue of securities",
          f"category {cat!r} is not blocked")

# The real buyback still gets through. It is the announcement, not the ledger.
REAL_BUYBACKS = [
    ("Buy-back of Securities",
     "Board Resolution approving buy-back of equity shares up to Rs 400 crore"),
    ("General Updates", "Public Announcement for Buy-back of equity shares"),
]
for cat, head in REAL_BUYBACKS:
    pts, tag = rules.score(cat, head)
    check(tag == "Buyback" and pts >= 55,
          "the buyback announcement itself stopped being recognised",
          f"{(pts, tag)} <- {head[:64]!r}")


# ---------------------------------------------------------------------------
# 14. Everything tools/audit_categories.py found on 3 September
#
# The audit asks each category to justify itself: every filing tagged "Order"
# should say something about orders somewhere, and the ones that do not are
# either misfiled or wording the rules have never seen. Run against the 1,185
# filings live that morning it flagged eight categories, and these are the
# real faults among them. Verbatim, so none can come back.
# ---------------------------------------------------------------------------

AUDIT_MISFILED = [
    # Marketing words, read as deals. A commercial agreement to sell software
    # together is not an acquisition, and "Strategic Investment Unit" was the
    # NAME of the subsidiary whose name was being changed.
    ("Press Release",
     "Coforge expands strategic partnership with Pega to accelerate "
     "enterprise AI transformation", None),
    ("General Updates",
     "Change in Name of Geomysore Services India Pvt Ltd, Strategic "
     "Investment Unit of Lloyds Enterprises Limited", None),
    # The role first, the event second - how a two-word headline is written.
    ("Company Update / General", "CFO Appointment", "Change In Management"),
    ("Company Update / General", "Company Secretary Resignation",
     "Change In Management"),
    # BSE calls its own order category "Awarding of order(s)/contract(s)",
    # and the rules said "award of", which does not match it. Nor was "letter
    # of acceptance" listed, which is what the railways actually send.
    ("Awarding of order(s)/contract(s)",
     "Intimation for Receipt of Letter of Acceptance from Rail Vikas Nigam "
     "Limited", "Order"),
    ("General Updates", "Receipt of Letter of Acceptance for a highway project",
     "Order"),
    # Routine paperwork that recites something bigger than itself.
    ("Company Update / General",
     "Letter to shareholders pursuant to Regulation 30 and 36(1)(b) of "
     "SEBI LODR 2015", None),
    ("Company Update / General",
     "Letter Sent to Members Pursuant to Regulation 36(1) (b) of SEBI "
     "Listing Regulations", None),
    ("Company Update / General",
     "Certificate of Payment of Interest of Non-Convertible Debentures", None),
    ("Company Update / General", "BRSR for FY25-26", None),
    ("Company Update / General",
     "Reminder letter for KYC updation by shareholders", None),
    ("Company Update / General",
     "Intimation under regulation 30 wrt weblink of the Annual Report", None),
]
for cat, head, want in AUDIT_MISFILED:
    pts, tag = rules.score(cat, head)
    if want is None:
        check(pts < 55,
              "routine paperwork is back above the important line",
              f"{(pts, tag)} <- {head[:58]!r}")
    else:
        check(tag == want,
              f"this should be {want}",
              f"{(pts, tag)} <- {head[:58]!r}")

# The same documents must not be promoted back by triage after reading the PDF,
# which is how they got their categories in the first place - the annual-report
# letter's attachment contains the AGM notice and the dividend resolution.
for cat, head in [
    ("Company Update / General",
     "Letter to shareholders pursuant to Regulation 36(1)(b)"),
    ("Company Update / General", "BRSR for FY25-26"),
    ("Company Update / General",
     "Certificate of Payment of Interest of Non-Convertible Debentures"),
]:
    check(triage._blocked({"category": cat, "headline": head}),
          "triage will read this and promote it back",
          f"{head[:56]!r} is not blocked")

# And the genuine articles are untouched. A strategic investment that says how
# much, or how much of, is a deal and stays one.
AUDIT_CONTROLS = [
    ("General Updates",
     "The company made a strategic investment acquiring a 26% stake in ABC "
     "Limited", "Acquisition"),
    ("General Updates",
     "Strategic investment of Rs 120 crore in a renewable energy platform",
     "Acquisition"),
    ("General Updates",
     "Acquisition of 100% shareholding in XYZ Private Limited", "Acquisition"),
    ("Board Meeting", "Appointment of Mr X as Chief Financial Officer",
     "Change In Management"),
    ("Corp. Action", "Board recommended a final dividend of Rs 5 per share",
     "Dividend"),
    ("General Updates", "Receipt of order worth Rs 500 crore from NHAI",
     "Order"),
    ("General Updates",
     "Allotment of 30,000 non-convertible debentures aggregating Rs 300 crore",
     "Fund Raising"),
]
# A headline that names a change of personnel settles it, even when the
# exchange category is vague and the score is below the promotion bar. This is
# the second half of the "CFO Appointment" fault: reading the headline right
# was not enough, because 51 is under 55 and the PDF was read anyway.
for cat, head in [
    ("Company Update / General", "CFO Appointment"),
    ("Company Update / General", "Company Secretary Resignation"),
    ("General Updates", "Appointment of Mr X as Chief Financial Officer"),
    ("Updates", "Change in Management"),
]:
    check(triage._blocked({"category": cat, "headline": head}),
          "a personnel change can still be overridden by its own PDF",
          f"{head[:50]!r} under {cat!r} is not blocked")

# ...and a vague headline is still read. That is what triage is for, and
# blocking it would silence the filings the whole thing exists to find.
for cat, head in [
    ("Company Update / General", "Outcome of Board Meeting"),
    ("General Updates", "Press Release"),
    ("Updates", "Intimation under Regulation 30"),
]:
    check(not triage._blocked({"category": cat, "headline": head}),
          "triage has stopped reading the vague filings it exists to read",
          f"{head[:50]!r} under {cat!r} is blocked")


for cat, head, want in AUDIT_CONTROLS:
    pts, tag = rules.score(cat, head)
    check(tag == want,
          f"a real {want} stopped being recognised",
          f"{(pts, tag)} <- {head[:58]!r}")


# ---------------------------------------------------------------------------
# 15. Filings that were being missed altogether
#
# Reported on 3 September: Autoline, Titan Biotech, Suven. None was missing
# from the database - all three were fetched, scored and stored. They were
# missing from IMPORTANT, which is the only list most readers look at, because
# the scoring did not recognise what they said.
#
# Two different faults, and the first is the more embarrassing.
# ---------------------------------------------------------------------------

# One adjective. Autoline's press release read "Secures PRESTIGIOUS Order
# Worth Rs 100 Crores from Tata Motors Passenger Vehicles" and the pattern
# wanted the verb next to its object, with at most an "a" between. A Rs 100
# crore Tata Motors order scored 44 and stayed off the front page.
#
# Companies write these lines to be read, so they are full of adjectives.
ORDER_WINS = [
    "Autoline Industries Secures Prestigious Order Worth Rs 100 Crores from "
    "Tata Motors Passenger Vehicles limited for SUV Components - Sanand",
    "Business Order from Tata Motors Passenger Vehicles Limited.",
    "Company has bagged its largest-ever order for supply of transformers",
    "Received a significant repeat order from Indian Railways",
    "Secured a maiden export order from a European customer",
    "Won a prestigious contract for the Mumbai coastal road project",
]
for head in ORDER_WINS:
    pts, tag = rules.score("Press Release", head)
    check(tag == "Order" and pts >= 55,
          "an order win is not reaching the front page",
          f"{(pts, tag)} <- {head[:58]!r}")
    pts, tag = rules.score_text(head, floor=0)
    check(tag == "Order",
          "an order win in the PDF is not recognised",
          f"score_text {(pts, tag)} <- {head[:58]!r}")

# Pharma had no category at all, so a whole class of material news scored
# nothing. Suven Life Sciences announced completion of patient enrollment in a
# global Phase-3 study of Masupirdine for Alzheimer's agitation - the sort of
# thing a small pharma company exists to do - and it scored 0.
PHARMA = [
    ("Suven Life Sciences Announces Completion of Patient Enrollment in "
     "Global Phase-3 Study of Masupirdine (SUVN-502) for Agitation Associated "
     "with Alzheimers Dementia", "Clinical Trial"),
    ("Company announces topline data from its pivotal Phase 3 trial",
     "Clinical Trial"),
    ("The company has received final approval from USFDA for its generic "
     "tablet", "Product Approval"),
    ("ANDA approval received for a generic injection", "Product Approval"),
    ("Marketing authorisation granted for the injectable formulation",
     "Product Approval"),
    # A Form 483 mentions the regulator and the product both, and it is bad
    # news. Scored above Product Approval on purpose - naming a regulator is
    # not the same as being granted something by one.
    ("USFDA inspection of the Hyderabad facility concluded with zero "
     "observations", "Plant Inspection"),
    ("Receipt of Form 483 with five observations following the USFDA audit",
     "Plant Inspection"),
    ("Warning letter received from the US Food and Drug Administration",
     "Plant Inspection"),
]
for head, want in PHARMA:
    pts, tag = rules.score_text(head, floor=0)
    check(tag == want and pts >= 55,
          f"this should be {want} and important",
          f"{(pts, tag)} <- {head[:58]!r}")

# "Phase" is an ordinary English word and "approval" is the commonest word in
# the whole feed. Neither may drag a filing into pharma.
NOT_PHARMA = [
    ("Phase 2 of the plant expansion has been commissioned", "Capacity Increase"),
    ("The board approved a final dividend of Rs 5 per share", "Dividend"),
    ("Approval of shareholders was obtained for the preferential issue", "Pref"),
    ("Receipt of order worth Rs 500 crore from NHAI", "Order"),
]
for head, want in NOT_PHARMA:
    pts, tag = rules.score_text(head, floor=0)
    check(tag == want,
          "an ordinary word dragged a filing into a pharma category",
          f"{(pts, tag)}, wanted {want} <- {head[:58]!r}")

# A plant that "has been commissioned" - the pattern only had "commissioning
# of", so the finished thing scored nothing while the announcement of it
# scored 57.
for head in ["The new unit at Sanand has been commissioned",
             "Commissioning of the 50 MW solar plant",
             "Phase 2 of the plant expansion has been commissioned"]:
    pts, tag = rules.score_text(head, floor=0)
    check(tag == "Capacity Increase",
          "a commissioned plant is not recognised",
          f"{(pts, tag)} <- {head[:58]!r}")


# ---------------------------------------------------------------------------
# 15. "Nothing else" means no EVENT, not no tag
#
# The meeting-notice override only fires when the filing names no other event.
# That test asked whether score_text returned anything at all - and the tags on
# the refuse list are returned all the time. They are the ones that mean "we
# could not tell": Annual Report, Corp Action, Outcome, Press Release.
#
# So an AGM notice whose summary scored (28, Annual Report) looked like it
# named an event, the notice branch was skipped, Annual Report was then refused
# as too weak, and the filing kept whatever tag its PDF had given it. Seven
# filings under Dividend on 3 September arrived that way, with more under Pref
# and Warrants. Verbatim below.
# ---------------------------------------------------------------------------

WEAK_TAG_NOTICES = [
    ("General Updates",
     "Tega Industries Limited has informed the Exchange about General Updates",
     "Tega Industries has announced that its 50th Annual General Meeting is "
     "scheduled for September 24, 2026, via video conferencing. The company "
     "has also shared the annual report."),
    ("Company Update / General", "As per enclosed letter",
     "National Plastic Industries has scheduled its 39th Annual General "
     "Meeting for September 23, 2026, at 4:00 PM via video conferencing."),
    ("Corp. Action / Book Closure", "Due to Clerical error revised for Member register close",
     "Artefact Projects Limited has announced the book closure dates for its "
     "38th Annual General Meeting. The Register of Members will remain closed."),
    ("Others / Outcome without intimation",
     "Outcome of Board Meeting held on Monday i.e. August 31, 2026",
     "Vipul Organics held a board meeting to approve the Annual Report and "
     "schedule its 54th Annual General Meeting."),
    ("Company Update / Meeting Updates",
     "Intimation under regulation 30 wrt to weblink for forthcoming AGM",
     "United Interactive Ltd has shared the web link for its Annual Report "
     "with shareholders whose email addresses are not registered."),
]
for cat, head, summ in WEAK_TAG_NOTICES:
    got = pipeline.category_from_summary(cat, head, head + " " + summ)
    check(got == "Meeting",
          "a meeting notice is keeping the tag its PDF gave it",
          f"got {got!r} <- {summ[:56]!r}")

# The guard that made this necessary still holds: a summary naming a real
# event keeps it, however much it talks about the meeting that will approve it.
for cat, head, summ, want in [
    ("Corp. Action / Record Date",
     "Record date for the purpose of Dividend is 17-Sep-2026",
     "Sunteck Realty has announced the record date for its dividend. The "
     "company also scheduled its 43rd Annual General Meeting.", "Dividend"),
    ("Board Meeting / Outcome of Board Meeting", "Outcome of board meeting",
     "The board approved a private placement of up to 15 million equity "
     "shares at Rs 16 each, raising up to Rs 24 crore, subject to approval "
     "of members at the ensuing general meeting.", "Fund Raising"),
    ("Company Update", "Outcome of board meeting",
     "The board approved a preferential issue of 10 lakh equity shares at "
     "Rs 161 each, to be placed before the annual general meeting.", "Pref"),
]:
    got = pipeline.category_from_summary(cat, head, head + " " + summ)
    check(got in (want, None),
          "a real event was renamed Meeting because its summary mentions the AGM",
          f"got {got!r}, wanted {want!r} <- {summ[:52]!r}")


# ---------------------------------------------------------------------------
# 16. Two more reported by name, 3 September
# ---------------------------------------------------------------------------

# A book closure states its own purpose, and that is what decides it. Rashtriya
# Chemicals closed its register "for the purpose of AGM" and was published as a
# Dividend, because the same notice sets the dividend record date and the
# summary said so.
RCF = ("Rashtriya Chemicals and Fertilizers Limited has informed the Exchange "
       "regarding '2. The Register of Members and Share Transfer Books of the "
       "Company will remain closed from Saturday, September 19, 2026, to "
       "Friday, September 25, 2026 for taking record of the Members of the "
       "Company for the purpose of AGM.'.")
check(pipeline.category_from_summary("Updates", RCF, RCF) == "Meeting",
      "a book closure for the AGM is being published as a dividend",
      repr(pipeline.category_from_summary("Updates", RCF, RCF)))

# ...and one that states a different purpose is not a meeting notice.
for head, summ, want in [
    ("Record date for the purpose of Dividend is 17-Sep-2026",
     "Sunteck Realty has announced the record date for its dividend. It also "
     "scheduled its 43rd Annual General Meeting.", "Dividend"),
    ("The Register of Members will remain closed from 12 to 18 September for "
     "the purpose of payment of the final Dividend",
     "The company has fixed the book closure for its final dividend of Rs 5.",
     "Dividend"),
]:
    got = pipeline.category_from_summary("Corp. Action", head, head + " " + summ)
    check(got == want,
          "a book closure for a dividend was taken for a meeting notice",
          f"got {got!r}, wanted {want!r}")

# A director with no adjective. "Intimation for appointment of Director" named
# no KIND of director, matched nothing, scored 18/Other, and SATYA
# MicroCapital's new nominee director was published as a Delisting once triage
# had read the PDF.
# A departure has its own tag, and that is the right answer for one - the
# check below accepts either, because what matters is that the filing is
# recognised as being about a person at all.
for head in [
    "Intimation for appointment of Director",
    "Appointment of Director",
    "Intimation regarding resignation of Director",
]:
    pts, tag = rules.score("Company Update / General", head)
    check(tag in ("Change In Management", "Resignation"),
          "a plain director appointment is not being recognised",
          f"{(pts, tag)} <- {head!r}")
    check(triage._blocked({"category": "Company Update / General",
                           "headline": head}),
          "its PDF can still rename a director appointment",
          f"{head!r} is not blocked")


# ---------------------------------------------------------------------------
# 17. Debt servicing and mutual fund paperwork
#
# Sixteen of the twenty-nine filings under Buyback on 3 September were a
# company paying the interest on its debentures or redeeming them on the due
# date. A redemption is the borrower handing the money back, which reads like
# a company buying its own securities in - and there is one per instrument per
# due date, so since NSE's debt list started being fetched there are dozens
# every day. REC, Power Finance, Exim Bank, L&T Finance, National Housing
# Bank, and a Vadodara Municipal Corporation green bond coupon.
#
# A mutual fund's portfolio statement is the other one. It lists every
# instrument the fund holds - several hundred company names and every kind of
# security there is - so reading one finds whatever scores highest. Choice
# Gold ETF's fortnightly portfolio was published as a Rights Issue.
# ---------------------------------------------------------------------------

TREASURY_PAPERWORK = [
    "The Company has made payment towards interest and prinicipal amount to "
    "the debenture holders",
    "Confirmation of Redemption and Interest Payment of Bonds",
    "Certificate of Interest and Principal Redemption",
    "Intimation for repayment of Commercial Paper",
    "GREEN BOND - INTEREST PAYMENT - 5TH COUPON PAYMENT - SEP 2026",
    "Intimation of payment of interest on NCDs pursuant to SEBI LODR",
    "Confirmation of Redemption of 9.45% Tax-Free Bond Series 77-B",
    "Fortnightly Portfolio for the Scheme of Choice Mutual Fund as on August 31",
    "NAV as of September 02, 2026",
    "Current Expense Ratio as on 02/09/2026",
]
for head in TREASURY_PAPERWORK:
    pts, tag = rules.score("Company Update / General", head)
    check(pts < 55,
          "treasury or fund paperwork is above the important line",
          f"{(pts, tag)} <- {head[:58]!r}")
    check(triage._blocked({"category": "Company Update / General",
                           "headline": head}),
          "its PDF can still promote it - a bank confirmation quotes the "
          "instrument, its coupon and its face value",
          f"{head[:56]!r} is not blocked")

# The real corporate actions these are mistaken for.
for cat, head, want in [
    ("General Updates",
     "Board Resolution approving buy-back of equity shares up to Rs 400 crore",
     "Buyback"),
    ("General Updates", "Public Announcement for Buy-back of equity shares",
     "Buyback"),
    ("General Updates",
     "Scheme of Arrangement between the Company and its wholly owned subsidiary",
     "Scheme Of Arrangement"),
    ("General Updates",
     "Composite Scheme of Amalgamation approved by the Board",
     "Scheme Of Arrangement"),
    ("General Updates",
     "Allotment of 30,000 non-convertible debentures aggregating Rs 300 crore",
     "Fund Raising"),
]:
    pts, tag = rules.score(cat, head)
    check(tag == want,
          f"a real {want} stopped being recognised",
          f"{(pts, tag)} <- {head[:58]!r}")


# ---------------------------------------------------------------------------

print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")
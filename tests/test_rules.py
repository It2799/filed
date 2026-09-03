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
for fname in ("rules.py", "triage.py", "pipeline.py", "tests/test_rules.py"):
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

print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")
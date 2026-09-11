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
import sources                                          # noqa: E402

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(f"{label}\n      {detail}")


# Exchange APIs use placeholders when a notice has no PDF. These must never
# become clickable relative links such as the dashboard's local /- route.
for raw in ("-", "N/A", "#", "", None, "/relative/document.pdf"):
    check(sources._external_url(raw) == "", "invalid filing URL was accepted", repr(raw))
check(sources._external_url("https://nsearchives.nseindia.com/corporate/a.pdf") != "",
      "a genuine NSE filing URL was rejected")
check(sources._attachment_name("-") == "", "BSE placeholder filename was accepted")
check(sources._attachment_name("notice.pdf") == "notice.pdf",
      "a genuine BSE attachment filename was rejected")

check(rules.retag("The company filed an appeal in a legal dispute before the court")
      == "Legal/Reg", "a court case is still classified as a customer order")
loi_summary = ("The company signed a letter of intent to purchase aircraft as "
               "part of an acquisition for its intended fleet expansion.")
check(pipeline.category_from_summary("Acquisition", "Aircraft acquisition", loi_summary)
      != "Order", "an acquisition letter of intent was changed into an order")


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
    ("Buy-back of Securities", "Closure of the Buy-back Offer"),
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
for cat, head in FOLLOW_UP_PAPERWORK:
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
    # A partnership is not an acquisition. It is also not nothing, which is
    # what this asserted until 4 September - the wrong answer was removed and
    # no right one was built, so Balaji Telefilms' YouTube deal scored 44 and
    # appeared on neither page. Now it wants "Partnership", not "below 55".
    ("Press Release",
     "Coforge expands strategic partnership with Pega to accelerate "
     "enterprise AI transformation", "Partnership"),
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
# 18. The press releases
#
# A company files a press release under the category "Press Release" with the
# headline "Please refer attached file". That scores 44 - below the 55 needed
# to be shown, and below the 55 needed to be SUMMARISED. So nothing ever asked
# what the release said, and the one thing a company issues BECAUSE it wants
# the news noticed was the one thing never read.
#
# 31 of the 33 press releases filed on 4 September scored under the line.
# Balaji Telefilms filed on both exchanges and appeared on neither page.
#
# The regex cannot help: the headline says nothing. Only the summary can, and
# once it names a real event the filing has to be promoted to what that event
# is worth - which the relabel step refused to do, by design, until now.
# ---------------------------------------------------------------------------

check(rules.is_press_release("Company Update / Press Release / Media"),
      "a press release category is not being recognised")
check(rules.is_press_release("Press Release"),
      "a bare press release category is not being recognised")
check(not rules.is_press_release("Corp. Action / Book Closure"),
      "an ordinary category is being treated as a press release")

# The headline alone is worthless, which is the whole problem.
check(rules.score("Company Update / Press Release / Media",
                  "Please refer attached file.")[0] < 55,
      "the premise has changed - a bare press release headline now scores")

# ...and the summary rescues it, with a score to match.
BURIED_IN_A_PRESS_RELEASE = [
    ("Balaji Telefilms received an order worth Rs 120 crore for a web series "
     "slate.", "Order"),
    ("Lupin has received approval from the USFDA for its generic version of "
     "the drug.", "Product Approval"),
    ("The company commissioned its new 500 MW greenfield plant at Jamnagar.",
     "Capacity Increase"),
    ("The board approved the acquisition of a 74% stake in ABC Private "
     "Limited for Rs 260 crore.", "Acquisition"),
]
for summ, want in BURIED_IN_A_PRESS_RELEASE:
    got = pipeline.category_from_summary(
        "Company Update / Press Release / Media", "Please refer attached file.",
        "Please refer attached file. " + summ)
    check(got == want,
          "real news inside a press release is not being found",
          f"got {got!r}, wanted {want!r} <- {summ[:52]!r}")
    check(rules.SCORE_FOR_TAG.get(got, 0) >= 55,
          "the news was found but the filing stays below the line",
          f"{got!r} is worth {rules.SCORE_FOR_TAG.get(got)}")

# Every tag a summary can produce needs a score, or promoting it does nothing.
for _tag in set(t for t, _, _ in rules.TOPICS):
    check(rules.SCORE_FOR_TAG.get(_tag, 0) > 0,
          f"{_tag!r} has no score, so a summary naming it cannot promote",
          repr(rules.SCORE_FOR_TAG.get(_tag)))

# "of" is optional in an order receipt - both wordings are the same news.
for text in [
    "The company received an order worth Rs 500 crore from NHAI",
    "Receipt of order from Tata Projects Limited",
    "Company has received orders aggregating Rs 45 crore",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Order",
          "an order win is not being recognised",
          f"{(pts, tag)} <- {text[:56]!r}")


# ---------------------------------------------------------------------------
# 19. When neither the headline nor the document says, read the document
#
# Ishan's point, and it is the right one: the judgement should come from inside
# the PDF, not from the headline. Every PDF is already read - but by regex, and
# a regex only finds wordings somebody thought of in advance. When it finds
# nothing the filing keeps a tag that is not an answer at all: Other, Outcome,
# Board Meeting, Corp Action, Unusual. "Outcome of Board Meeting held today
# 04.09.2026" is the shape of it - the board decided something and only the
# attachment says what.
#
# Those now get an AI summary whatever they score, and the summary may promote
# them. About fifteen a day.
# ---------------------------------------------------------------------------

for tag in ["Other", "Outcome", "Press Release", "Board Meeting",
            "Corp Action", "Unusual"]:
    check(rules.undecided(tag),
          f"{tag!r} is an answer now? it means we could not tell",
          repr(tag))

# A real event is decided, and must not be queued for re-reading - that would
# be thousands of AI calls a day rather than fifteen.
for tag in ["Dividend", "Order", "Acquisition", "Results", "Pref", "Buyback",
            "Meeting", "Change In Management", "Routine", "Annual Report"]:
    check(not rules.undecided(tag),
          f"{tag!r} would be sent for an AI re-read though it is already decided",
          repr(tag))

# The two sets overlap but are not the same, and the difference is real.
#
# UNDECIDED picks what to RE-READ. WEAK_FROM_SUMMARY picks what to refuse
# BELIEVING off a summary. A tag can be in the first and not the second: it is
# a poor answer, and still a better one than the wrong answer a filing
# currently has. AGI Infra's board-meeting intimation was filed under Dividend,
# and "Board Meeting" is what corrected it - so refusing that from a summary
# would keep the Dividend.
#
# What has to be in both are the tags that say nothing whatsoever. Adopting one
# of those off a summary means re-reading a filing and handing it back the same
# non-answer for ever.
SAYS_NOTHING = {"Other", "Outcome", "Press Release", "Corp Action"}
for tag in SAYS_NOTHING:
    check(tag in rules.UNDECIDED,
          f"{tag!r} says nothing but is not queued for a re-read", repr(tag))
    check(tag in pipeline.WEAK_FROM_SUMMARY,
          f"{tag!r} can be read off a summary yet says nothing", repr(tag))

# Board Meeting and Unusual are deliberately re-read but still believable.
for tag in ("Board Meeting", "Unusual"):
    check(rules.undecided(tag),
          f"{tag!r} should be re-read - only the document says what happened",
          repr(tag))

# And the thing this is all for: a board outcome whose document names the event.
for summ, want in [
    ("The board approved a preferential issue of 10 lakh shares at Rs 161 each.",
     "Pref"),
    ("The company received an order worth Rs 500 crore from NHAI.", "Order"),
    ("The board recommended a final dividend of Rs 5 per equity share.",
     "Dividend"),
    ("The board approved the acquisition of a 74% stake in ABC Private Limited.",
     "Acquisition"),
]:
    got = pipeline.category_from_summary(
        "Board Meeting / Outcome of Board Meeting",
        "Outcome of Board Meeting held today 04.09.2026",
        "Outcome of Board Meeting held today 04.09.2026 " + summ)
    check(got == want,
          "a board outcome is not being read from its own document",
          f"got {got!r}, wanted {want!r} <- {summ[:50]!r}")
    check(rules.SCORE_FOR_TAG.get(got, 0) >= 55,
          "the event was found but the filing stays below the line",
          f"{got!r} is worth {rules.SCORE_FOR_TAG.get(got)}")


# ---------------------------------------------------------------------------
# 20. Partnerships
#
# Balaji Telefilms announced a partnership with YouTube on 4 September - five
# original shows across 200 episodes, YouTube taking global distribution and
# monetisation, Balaji keeping the IP - and it appeared on neither page.
#
# Not a fetch failure and not a misfiling. Both exchanges' copies were fetched
# and the PDF was read. There was simply nowhere for it to go: "strategic
# partnership" had been taken out of Acquisition the day before, correctly,
# because a reselling agreement is not a takeover. The wrong answer was
# removed and no right one was built.
# ---------------------------------------------------------------------------

PARTNERSHIPS = [
    "Ekta Kapoor's Balaji Telefilms Ltd partners with YouTube to launch 5 "
    "exclusive premium shows",
    "Coforge expands strategic partnership with Pega to accelerate enterprise "
    "AI transformation",
    "The Company has signed a Memorandum of Understanding with the Government "
    "of Gujarat",
    "Kirloskar Oil Engines has entered into a strategic partnership with DEUTZ "
    "to supply engine platforms",
    "The company has entered into a distribution agreement with a European "
    "partner",
]
for text in PARTNERSHIPS:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Partnership" and pts >= 55,
          "a partnership has nowhere to go again",
          f"{(pts, tag)} <- {text[:58]!r}")

# It sits BELOW the deal categories on purpose. A partnership is real news and
# it is not a change of ownership, so anything that moves ownership wins.
OWNERSHIP_WINS = [
    ("Acquisition of 100% shareholding in XYZ Private Limited", "Acquisition"),
    ("Entered into a joint venture agreement with ABC Limited", "Acquisition"),
    ("Scheme of Arrangement between the Company and its subsidiary",
     "Scheme Of Arrangement"),
    ("The company made a strategic investment acquiring a 26% stake in ABC "
     "Limited", "Acquisition"),
]
for text, want in OWNERSHIP_WINS:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want,
          f"a partnership pattern is outranking {want}",
          f"{(pts, tag)} <- {text[:58]!r}")

# And a press release announcing one is found through the whole path - which
# is the case that started this: category "Press Release", headline "Please
# refer attached file", the news three paragraphs into the attachment.
got = pipeline.category_from_summary(
    "Company Update / Press Release / Media",
    "Please refer attached file.",
    "Please refer attached file. Balaji Telefilms and YouTube have come "
    "together in a landmark strategic partnership, launching a slate of five "
    "original shows spanning 200 episodes.")
check(got == "Partnership",
      "a press release announcing a partnership is still lost",
      repr(got))
check(rules.SCORE_FOR_TAG.get(got, 0) >= 55,
      "the partnership was found but the filing stays below the line",
      f"{got!r} is worth {rules.SCORE_FOR_TAG.get(got)}")


# ---------------------------------------------------------------------------
# 21. Pref, Warrants, Promoter Buy/Sell, Dividend, Order, Acquisition
#
# Read end to end on 4 September, all six categories Ishan named. What came out
# was four separate faults, none of which the evidence audit could see, because
# every one of these filings does contain the words its category looks for.
# ---------------------------------------------------------------------------

# (a) A notice that the BOARD will meet, filed as the thing it will consider.
#     The same mistake as the AGM notice, one meeting down. None of these
#     boards had met.
BOARD_NOTICES = [
    "Manba Finance will hold a board meeting on 22 Sep 2026 to consider "
    "increasing its authorised share capital",
    "NHC Foods Ltd announced that its board will meet on September 9, 2026 to "
    "discuss a possible fund raise",
    "Commercial Syn Bags Limited will hold a board meeting on September 5, "
    "2026. The board will discuss a preferential issue",
    "Intimation of Board Meeting to be held on 12 September to consider and "
    "approve the unaudited financial results",
]
for text in BOARD_NOTICES:
    check(rules.board_meeting_notice(text),
          "a notice of a future board meeting is not being recognised",
          f"{text[:60]!r}")
    got = pipeline.category_from_summary("Company Update / General", text, text)
    check(got == "Board Meeting",
          "a board that has not met yet is being credited with the decision",
          f"got {got!r} <- {text[:56]!r}")

# ...and a board that HAS met keeps its decision.
BOARD_DECIDED = [
    ("Outcome of Board Meeting: the board approved a preferential issue of "
     "10 lakh shares", "Pref"),
    ("The board approved a preferential issue of up to 10 lakh equity shares "
     "at Rs 161 each", "Pref"),
    ("Kiri Industries is issuing 60.82 lakh warrants to its promoters at "
     "Rs 475 per warrant", "Warrants"),
    ("Proceedings of the board meeting held on 3 September, at which the "
     "dividend was approved", "Dividend"),
]
for text, want in BOARD_DECIDED:
    check(not rules.board_meeting_notice(text),
          "a completed board decision is being treated as a notice",
          f"{text[:60]!r}")
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want, f"this should still be {want}", f"{(pts, tag)}")

# (b) Registering a new company is not buying one. 15 of the 144 filings under
#     Acquisition were a company incorporating a subsidiary.
NEW_SUBSIDIARIES = [
    "Bondada Engineering has incorporated a new subsidiary, PhotonicGrid "
    "Networks Private Limited",
    "Brigade Enterprises has incorporated two wholly owned subsidiaries to "
    "develop projects",
    "Dhanuka Agritech has incorporated a wholly owned subsidiary in Ireland",
    "TechEra Engineering announced the incorporation of a new subsidiary "
    "named TechEra Aeronautics",
    "Craftsman Automation has set up a step-down subsidiary in Germany",
]
for text in NEW_SUBSIDIARIES:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "New Subsidiary",
          "registering a company is being published as buying one",
          f"{(pts, tag)} <- {text[:56]!r}")

# ...and buying one still is.
for text, want in [
    ("Acquisition of 100% shareholding in XYZ Private Limited", "Acquisition"),
    ("The company acquired a 74% stake in its new subsidiary ABC Ltd",
     "Acquisition"),
    ("Scheme of Arrangement between the Company and its wholly owned "
     "subsidiary", "Scheme Of Arrangement"),
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want, f"a real {want} was lost to New Subsidiary",
          f"{(pts, tag)} <- {text[:56]!r}")

# (c) The promoter verb list. "sold" and "sell" were listed; "sale" and
#     "buying" were not, so a promoter's own dealing matched no verb and its
#     summary relabelled it an Acquisition.
PROMOTER_WORDINGS = [
    "Promoter Kiran B Vadodaria disclosed an open-market sale of 1,000,000 "
    "Nila Spaces shares",
    "Promoter S. Aravindan disclosed buying 9,481 additional shares in the "
    "open market",
    "Promoters Aditi Panandikar and Madhura Kare bought a total of 4,000 "
    "equity shares",
    "Promoter group PRI CAF PVT LTD has released pledged shares",
]
for text in PROMOTER_WORDINGS:
    check(rules.promoter_deal(text),
          "a promoter dealing matches none of the verbs",
          f"{text[:60]!r}")
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Promoter Buy/Sell",
          "a promoter dealing is not being recognised",
          f"{(pts, tag)} <- {text[:56]!r}")

# A buyback must not be swept up by the new "buy" verb.
pts, tag = rules.score_text(
    "Board Resolution approving buy-back of equity shares up to Rs 400 crore "
    "held by promoters and public shareholders", floor=0)
check(tag == "Buyback",
      "the promoter verb list has swallowed a buyback",
      f"{(pts, tag)}")

# (d) Who moved the shares is not something a summary can overturn. These tags
#     come from the stake-disclosure category, which is the authoritative
#     record of WHO; a summary that simply does not repeat the word "promoter"
#     is not evidence against it.
for current in ("Promoter Buy/Sell", "Inter-se Transfer"):
    got = pipeline.category_from_summary(
        "Insider Trading / SAST",
        "The Exchange has received the disclosure under Regulation 29(2)",
        "Innovative Money Matters Pvt Ltd acquired 55,000 shares of Avonmore "
        "Capital & Management Services Ltd, raising its stake from 33.55% to "
        "33.57% via an open market purchase",
        current)
    check(got != "Acquisition",
          f"a summary is overturning {current!r}, which the category settled",
          f"got {got!r}")

# But a genuine corporate acquisition in the same position still wins.
got = pipeline.category_from_summary(
    "Company Update / General", "Outcome of board meeting",
    "The board approved the acquisition of a 74% stake in ABC Private Limited "
    "for Rs 260 crore from its existing shareholders", "Other")
check(got == "Acquisition",
      "a real acquisition is being refused", f"got {got!r}")

# (e) A registrar change is not a warrant issue. The letter recites every
#     class of security the registrar will handle, which is how S&S Power
#     Switchgear's "Change in RTA" reached Warrants at 61.
for head in [
    "Announcement under Regulation 30 (LODR) - Change in RTA",
    "Change in Registrar and Share Transfer Agent from GNSA to KFin",
]:
    pts, tag = rules.score("Company Update / General", head)
    check(pts < 55, "a registrar change is above the important line",
          f"{(pts, tag)} <- {head[:56]!r}")


# ---------------------------------------------------------------------------
# 22. Which purpose is named FIRST
#
# The commonest shape of all, and the one that kept AGM notices in Dividend.
# These filings name the meeting and the dividend in the same breath:
#
#   "close its books from 24 to 30 September for the Annual General Meeting
#    and dividend"                                     -> the AGM is the purpose
#   "record date for the final dividend and scheduled its 41st AGM"
#                                                  -> the dividend is the purpose
#
# The word dividend is in both, so score_text returns Dividend at 60 for both,
# and 60 is substantive - which is why the "notice wins when nothing else is
# named" rule could never settle it. What settles it is which one is named
# first. The closure is FOR the thing it names first; the other rides along.
#
# The first attempt had no such test and turned 60 genuine dividends into
# meetings.
# ---------------------------------------------------------------------------

MEETING_IS_THE_POINT = [
    "Rithwik Facility Management Services Ltd will close its books from 24 to "
    "30 September 2026 for the Annual General Meeting and dividend.",
    "Kiran Vyapar Limited has announced the book closure dates for its "
    "upcoming Annual General Meeting. The company will close its share "
    "transfer books to determine eligibility for the dividend payment.",
    "TANFAC Industries announced that its share register will be closed from "
    "Sep 17-23, with the record date set as Sep 16 for the 52nd AGM and "
    "dividend entitlement.",
    "ABC India Ltd has announced the dates for its upcoming Annual General "
    "Meeting and dividend payment.",
    "Pecos Hotels and Pubs Ltd has scheduled its 21st Annual General Meeting "
    "for September 25. The company has set September 18 as the record date.",
    "Ceinsys Tech Limited has fixed the record date for its upcoming 28th "
    "Annual General Meeting and final dividend payment.",
]
for text in MEETING_IS_THE_POINT:
    check(rules.meeting_is_the_subject(text),
          "the meeting is the subject and is not being read as one",
          f"{text[:64]!r}")

THE_DIVIDEND_IS_THE_POINT = [
    "The board has set 23 September 2026 as the record date for the final "
    "dividend and scheduled its 41st Annual General Meeting.",
    "Odyssey Corporation has set September 23 as the record date for its "
    "upcoming dividend payment. Shareholders on record by this date will be "
    "eligible for the payout, subject to approval at the AGM.",
    "Vintage Coffee and Beverages has set September 23 as the record date for "
    "its final dividend. Shareholders must hold the stock by this date to be "
    "eligible for the payout, pending approval at the AGM.",
    "Sunteck Realty has announced that the record date for its upcoming "
    "dividend is September 17. The company also scheduled its 43rd Annual "
    "General Meeting for September 22.",
    "Foseco Crucible announced that shareholders have approved a final "
    "dividend at its 41st Annual General Meeting. The payout is Rs 12.50.",
]
for text in THE_DIVIDEND_IS_THE_POINT:
    check(not rules.meeting_is_the_subject(text),
          "a dividend is being read as a meeting notice",
          f"{text[:64]!r}")
    got = pipeline.category_from_summary("Corp. Action", "Record date", text,
                                         "Dividend")
    check(got in ("Dividend", None),
          "a real dividend was renamed", f"got {got!r}")

# The meeting APPROVES a dividend; that is not what a record date is FOR.
check(not rules.meeting_is_the_subject(
        "Shareholders on record by this date will be eligible for the payout, "
        "subject to approval at the AGM"),
      "the approving meeting is being read as the purpose")


# ---------------------------------------------------------------------------
# 23. A deal has to be visible in the summary
#
# Acquisition is the category a reader looks at first and the one a PDF puts a
# filing into most often by accident. When the summary of the same filing
# contains no deal language at all, there was no deal.
# ---------------------------------------------------------------------------

NOT_DEALS = [
    "Bodhtree Consulting has posted its long-term Bodhtree 2035 growth "
    "roadmap on its website.",
    "Shadowfax launched a Channel Partner Program to expand its Shadowfax 360 "
    "service.",
    "Mobavenue AI Tech Ltd announced it won four Gold and one Silver awards at "
    "the DATAMATIXX Awards.",
]
for text in NOT_DEALS:
    got = pipeline.category_from_summary("General Updates", "Press Release",
                                         text, "Acquisition")
    check(got != "Acquisition",
          "a filing with no deal in it is staying under Acquisition",
          f"got {got!r} <- {text[:56]!r}")

# ...and these ARE deals, in wordings the first version of that rule missed.
STILL_DEALS = [
    "Capital India Finance is selling its RemitX forex assets to Kanji Forex.",
    "International Gemological Institute will consolidate control over IGI "
    "Botswana, making it a wholly owned subsidiary.",
    "NLC India signed an addendum to transfer about 709 MW of renewable "
    "assets.",
]
for text in STILL_DEALS:
    got = pipeline.category_from_summary("General Updates", "Press Release",
                                         text, "Acquisition")
    check(got != "Other",
          "a real deal is being demoted for wording the evidence does not know",
          f"got {got!r} <- {text[:56]!r}")

# Buying a thing is not buying a company.
for text, want in [
    ("The board gave in-principle approval to buy land for about Rs 50 crore",
     "Capacity Increase"),
    ("In-principle approval for the acquisition of land for about Rs 50 crore",
     "Capacity Increase"),
    ("Purchase of plant and machinery worth Rs 12 crore for the new unit",
     "Capacity Increase"),
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want, f"an asset purchase should be {want}",
          f"{(pts, tag)} <- {text[:56]!r}")

# Registering a company, with the verb last.
pts, tag = rules.score_text(
    "Welspun Corp announced that its associate company Welspun Slagexcel "
    "Private Ltd was incorporated on 2 September", floor=0)
check(tag == "New Subsidiary",
      "a subsidiary incorporation written backwards is not recognised",
      f"{(pts, tag)}")


# ---------------------------------------------------------------------------
# 24. An AGM never belongs in another category
#
# Ishan's rule, stated plainly, after finding one more each time the last was
# fixed. The rules above each settle one shape of it and each left a tail:
# Filatex India's letter to shareholders carrying "web links to the 36th AGM
# notice and annual report, and a reminder to claim any unclaimed dividends"
# was published as a Dividend, on the words unclaimed dividends.
#
# So the backstop is blunt. If the filing is a notice of a general meeting and
# nothing was approved, declared, allotted, received or paid, it is a Meeting -
# whatever money words the text happens to contain.
#
# What keeps the real ones out is that a money filing always says the thing was
# DONE. A dividend filing says the board recommended it, or the record date is
# fixed, or the payout is Rs 12.50. A notice of a meeting says only that a
# meeting will be held.
# ---------------------------------------------------------------------------

NOTICE_ONLY = [
    ("Company Update / General",
     "Please find attached letter for dispatch of weblinks to the shareholders",
     "Filatex India sent a letter to shareholders without registered email "
     "IDs, providing web links to the 36th AGM notice and FY 2025-26 annual "
     "report, and reminding them to update their email and claim any "
     "unclaimed dividends."),
    ("General Updates", "Intimation",
     "The company has scheduled its 41st Annual General Meeting for "
     "September 24, 2026 via video conferencing."),
    ("Company Update", "Notice of AGM",
     "Notice of the 27th Annual General Meeting, which includes an enabling "
     "resolution for a preferential issue of equity shares and warrants."),
    ("Others", "Notice of postal ballot",
     "The postal ballot seeks approval for the issue of convertible warrants "
     "on a preferential basis."),
]
for cat, head, summ in NOTICE_ONLY:
    check(rules.meeting_only(cat, head, summ),
          "a notice with no money event is not being recognised as one",
          f"{summ[:60]!r}")
    got = pipeline.category_from_summary(cat, head, summ, "Dividend")
    check(got == "Meeting",
          "an AGM notice is landing somewhere other than Meeting",
          f"got {got!r} <- {summ[:56]!r}")

# Something HAPPENED, so the meeting is context and the event is the news.
SOMETHING_HAPPENED = [
    ("The board recommended a final dividend of Rs 5 per equity share, to be "
     "approved at the ensuing annual general meeting."),
    ("Sunteck Realty has announced that the record date for its upcoming "
     "dividend is September 17. The company also scheduled its 43rd Annual "
     "General Meeting."),
    ("Prime Focus board approved raising up to INR 3,000 crore through "
     "various securities. AGM scheduled for September 30 to approve this."),
    ("Foseco Crucible announced that shareholders have approved a final "
     "dividend of Rs 12.50 at its 41st Annual General Meeting."),
    ("The board allotted 1.2 crore equity shares on a preferential basis, "
     "as approved by the members at the extraordinary general meeting."),
]
for text in SOMETHING_HAPPENED:
    check(not rules.meeting_only("General Updates", "Outcome", text),
          "a completed money event is being read as a bare meeting notice",
          f"{text[:64]!r}")


# ---------------------------------------------------------------------------
# 25. A record date for interest is debt servicing, not a fund raise
#
# Summit Digitel's "record date for interest payments on its listed
# non-convertible debentures" was published as Fund Raising. Two reasons, and
# the second is the one that bites:
#
#   - The block on interest payments read "payment OF interest on". The filing
#     says "interest PAYMENTS ON", which is the same thing the other way round
#     and matched nothing.
#   - So it was not blocked, triage read the attachment, and an NCD interest
#     notice recites the debenture issue itself - face value, coupon, tenor.
#     "Issue of debentures" is a fund raise.
#
# A record date for a DIVIDEND, bonus or split is a real corporate action and
# is deliberately not caught by any of this.
# ---------------------------------------------------------------------------

# Read from the DOCUMENT, because these headlines say nothing: Summit Digitel's
# is "Record Date Updates" and Hero FinCorp's is "Intimation under Regulation
# 50(1)". Only the attachment says what the filing is about, and the attachment
# for an interest notice recites the debenture issue itself - face value,
# coupon, tenor - so reading it finds "issue of debentures" and scores a fund
# raise at 58.
DOCUMENT_LEVEL_DEBT = [
    "Summit Digitel has announced the record date for interest payments on its "
    "listed non-convertible debentures. The company has set September 16, "
    "2026 as the record date.",
    "Sammaan Capital has successfully made timely interest payments on its "
    "non-convertible debentures. All interest obligations due on September 8 "
    "were settled by September 7.",
    "The company confirms payment of interest on its NCDs due 1 October 2026. "
    "The debentures were issued at a face value of Rs 10 lakh each carrying a "
    "coupon of 8.5%.",
]
for text in DOCUMENT_LEVEL_DEBT:
    check(rules.debt_servicing(text),
          "debt servicing is not being recognised from the document",
          f"{text[:60]!r}")
    got = pipeline.category_from_summary("Record Date Updates",
                                         "Record Date Updates", text,
                                         "Fund Raising")
    check(got == "Routine",
          "a debt payment is staying under a money category",
          f"got {got!r} <- {text[:52]!r}")

# Genuinely new money, in the same words. What separates them is a DECISION to
# raise: approved, resolved, allotted. Every interest notice mentions the
# debentures it is paying interest on, so matching "debenture" would cancel the
# rule on every filing it exists to catch.
NEW_MONEY = [
    ("The borrowing committee approved raising up to INR 1,000 crore by "
     "issuing listed, rated, secured, redeemable non-convertible debentures.",
     "Fund Raising"),
    ("Canara Bank's board has approved raising up to USD 2,000 million "
     "through foreign currency bonds under its Medium Term Note programme.",
     "Fund Raising"),
    ("Allotment of 30,000 non-convertible debentures aggregating Rs 300 crore",
     "Fund Raising"),
    ("Issue of commercial paper of Rs 200 crore", "Fund Raising"),
]
for text, want in NEW_MONEY:
    check(not rules.debt_servicing(text),
          "a real fund raise is being read as debt servicing",
          f"{text[:60]!r}")
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want, f"this should be {want}", f"{(pts, tag)}")

# A notice that a board or a COMMITTEE of it will meet. Hero FinCorp "is
# holding a board committee meeting on September 15 to discuss raising funds
# through the issuance of non-convertible debentures" was published as a Fund
# Raising: the pattern wanted "board meeting" adjacent and the verb "will hold".
for text in [
    "Hero FinCorp is holding a board committee meeting on September 15, 2026. "
    "The purpose is to discuss raising funds through the issuance of "
    "non-convertible debentures.",
    "A meeting of the Board of Directors is scheduled to be held on "
    "12 September to consider the results",
]:
    check(rules.board_meeting_notice(text),
          "a notice that a board or committee will meet is not recognised",
          f"{text[:60]!r}")

# ...and a board that has already decided keeps its decision.
for text in [
    "The borrowing committee approved raising up to INR 1,000 crore by issuing "
    "non-convertible debentures.",
    "Canara Bank's board has approved raising up to USD 2,000 million through "
    "foreign currency bonds.",
]:
    check(not rules.board_meeting_notice(text),
          "a completed decision is being read as a meeting notice",
          f"{text[:60]!r}")


DEBT_SERVICING = [
    ("Corp. Action / Record Date",
     "Summit Digitel Infrastructure Limited has announced the record date for "
     "interest payments on its listed non-convertible debentures"),
    ("Corp. Action / Record Date", "Record date for payment of interest on NCDs"),
    ("Company Update",
     "Intimation of record date for redemption of debentures"),
    ("Company Update", "Interest payment on listed bonds - record date"),
    ("Company Update", "Record date fixed for the coupon payment on Series II"),
]
for cat, head in DEBT_SERVICING:
    pts, tag = rules.score(cat, head)
    check(pts < 55,
          "debt servicing is above the important line",
          f"{(pts, tag)} <- {head[:56]!r}")
    check(triage._blocked({"category": cat, "headline": head}),
          "its attachment can still promote it - an NCD interest notice "
          "recites the debenture issue",
          f"{head[:56]!r} is not blocked")

# The corporate actions that must survive all of that.
for cat, head, want in [
    ("Corp. Action / Bonus", "Recommended the issuance of Bonus Issue", "Bonus"),
    ("General Updates",
     "Allotment of 30,000 non-convertible debentures aggregating Rs 300 crore",
     "Fund Raising"),
    ("General Updates", "Board approved raising of funds up to Rs 500 crore",
     "Fund Raising"),
    ("General Updates", "Issue of commercial paper of Rs 200 crore",
     "Fund Raising"),
]:
    pts, tag = rules.score(cat, head)
    check(tag == want, f"a real {want} was caught by the debt-servicing rule",
          f"{(pts, tag)} <- {head[:56]!r}")

# A dividend record date still reaches Dividend through its summary, which is
# the path that has always settled it - the headline alone says Corp Action.
check(pipeline.category_from_summary(
        "Corp. Action / Record Date",
        "Record date for the purpose of Dividend is 17-Sep-2026",
        "Sunteck Realty has announced that the record date for its upcoming "
        "dividend is September 17, 2026.", "Corp Action") == "Dividend",
      "a dividend record date stopped reaching Dividend")


# ---------------------------------------------------------------------------
# 26. Pref, Fund Raising, Open Offer and Order, read filing by filing
#
# All four categories Ishan named, on the live data of 8 September. Four
# distinct faults, none of which the evidence audit can see, because every one
# of these filings does contain the word its category looks for.
# ---------------------------------------------------------------------------

# (a) The paperwork AFTER an issue, not the issue. Six of the twenty filings
#     under Pref were an exchange approving shares already allotted - a
#     formality that arrives days later and recites the issue it relates to.
LISTING_APPROVALS = [
    "Pakka Ltd. has received trading approvals for 27.20 lakh new equity "
    "shares allotted to non-promoters on a preferential basis",
    "Fonebox Retail Limited has received in-principle approval from the "
    "National Stock Exchange for its preferential issue",
    "Tejassvi Aaharam Ltd got BSE listing approval for 5,11,62,204 equity "
    "shares of Rs 10 each",
    "Vaishali Pharma has received listing approval from NSE for 45,37,865 "
    "equity shares",
    "Scan Steels Ltd got BSE trading approval for 2,144,239 equity shares "
    "issued by converting OCRPS",
    "Porwal Auto Components has received trading approval from the BSE for "
    "17,54,384 new equity shares",
]
for text in LISTING_APPROVALS:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Listing Approval",
          "a listing formality is being published as the issue it describes",
          f"{(pts, tag)} <- {text[:56]!r}")

# ...and the issue itself is untouched. A board deciding today outranks a
# formality, which is what separates the two.
for text in [
    "The board approved a preferential allotment of up to 7.2 lakh equity "
    "shares at Rs 190.37 each",
    "Iris Clothings has approved a preferential issue of 77,08,183 equity "
    "shares at Rs 41.67 each",
    "MIC Electronics board approved the issue of 5,68,73,418 new equity "
    "shares on a preferential basis",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Pref", "a real preferential issue was lost to the formality",
          f"{(pts, tag)} <- {text[:56]!r}")

# (b) Debt servicing in the wordings that were still slipping through.
for text in [
    "Star Health is exercising its call option to fully redeem 4,000 "
    "non-convertible debentures",
    "IIFL Finance has announced the redemption schedule for its Series D32 "
    "non-convertible debentures",
    "TVS Infrastructure Trust has set the record date for coupon and part "
    "redemption of its NCDs",
]:
    check(rules.debt_servicing(text),
          "paying money back is still reading as taking it in",
          f"{text[:60]!r}")

# (c) Every verb a company uses for "a meeting is coming", and a committee of
#     the board counts as the board.
for text in [
    "Niks Technology Ltd has postponed its Board of Directors meeting to "
    "September 8, 2026 to consider issuing NCDs",
    "Axentra Corp Ltd has announced a board meeting on 7 September 2026. "
    "The meeting will consider raising funds",
    "Unifinz Capital India Ltd will hold a committee meeting on September 8 "
    "to consider a debenture issue",
    "Trust Investment Advisors will hold a board meeting on 10 September to "
    "propose issuing NCDs",
    "Alliance Integrated Metaliks has rescheduled its board meeting to "
    "September 12 to consider fund raising",
]:
    check(rules.board_meeting_notice(text),
          "a notice that a board or committee will meet is not recognised",
          f"{text[:60]!r}")

# (d) An Open Offer has to BE one. Shah Foods' preferential issue of warrants
#     says a director "resigned following a change in management post an open
#     offer" - context, and it won at 70.
check(not rules.open_offer_real(
        "Executive Director Manan Rajesh Patel has resigned following a "
        "change in management post an open offer"),
      "a passing mention of an open offer still counts as one")

for text in [
    "Detailed Public Statement in respect of the open offer to public "
    "shareholders",
    "Three individuals are launching an open offer to acquire up to 26% of "
    "the equity shares",
    "Axis Capital, the offer manager, filed a detailed public statement",
    "Devinsu Trading has released the post-offer advertisement for its open "
    "offer",
    "Public announcement for the acquisition of 26% of the equity share "
    "capital",
]:
    check(rules.open_offer_real(text),
          "a real open offer is no longer recognised as one",
          f"{text[:60]!r}")

# An issue CREATES shares; an inter-se transfer MOVES them. Both mention the
# open-offer exemption, which is what that rule keys on.
pts, tag = rules.score_text(
    "Shah Foods has approved a preferential issue of up to 18.9 lakh "
    "convertible warrants to its promoters to raise up to Rs 28.92 crore.",
    floor=0)
check(tag in ("Warrants", "Pref"),
      "a preferential issue of warrants is not landing on the instrument",
      f"{(pts, tag)}")

for text in [
    "Siddharrth Mehta acquired 40.94 lakh shares from Shrreyans Mehta via a "
    "gift deed. The transfer is exempt from an open offer.",
    "Inter-se transfer of equity shares among members of the promoter group",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Inter-se Transfer",
          "a genuine inter-se transfer stopped being recognised",
          f"{(pts, tag)} <- {text[:52]!r}")

# (e) A magistrate does not place orders with caterers.
for text in [
    "Restaurant Brands Asia Ltd received an order from the Additional "
    "District Magistrate in Agra under the Food Safety and Standards Act, "
    "imposing a fine of Rs 1,60,000",
    "The company received an order from the Collector imposing a fine of "
    "Rs 50,000",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Legal/Reg",
          "a court or regulator's order is being published as a customer win",
          f"{(pts, tag)} <- {text[:56]!r}")

for text in [
    "Goldiam International and its subsidiaries have secured purchase orders "
    "worth Rs 6 crore",
    "Solex Energy has secured work orders worth Rs 74.77 crore for solar PV "
    "modules",
    "Sathlokhar Synergys secured a new civil and PEB work contract from Godrej",
    "Jhaveri Credits received a Letter of Award from New and Renewable Energy",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Order", "a real order win stopped being recognised",
          f"{(pts, tag)} <- {text[:56]!r}")


# ---------------------------------------------------------------------------
# 27. A tag that could only have come from the PDF has to be visible in the
#     summary too.
#
# The 8 September audit found the same fault in four categories at once, and
# the shape was identical every time: the headline scored 18/Other, the
# summary named nothing at all, and the tag came from a regex hitting a word
# somewhere in a forty-page attachment. triage reads every attachment, which
# is how real news buried under "General Updates" gets found - and also how a
# passing word decides a category.
#
# The rule is that the summary is written from the same document by a model
# that read all of it. If the document were really about a clinical trial, the
# summary would say so.

triage = __import__("triage")

# (a) Every Clinical Trial live on 8 September was the re-lodgement window:
#     a monthly compliance report on physical share transfer requests, which
#     most companies file to say nobody used it.
RELODGEMENT = [
    "Report on re-lodgment of Transfer Requests of Physical Shares for "
    "August 2026",
    "Report for re-lodgement of physical shares for the month of August 2026",
    "Social Media Post on awareness on transfer of physical shares - special "
    "window for re-lodgement",
    "Intimation of transfer of unclaimed shares to the demat suspense account",
    "Form MR-3 (Secretarial Audit Report for the Financial Year ended "
    "31st March 2026)",
]
_NEVER = [re.compile(p, re.I) for p in triage.NEVER_PROMOTE]
for head in RELODGEMENT:
    pts, tag = rules.score("", head)
    check(pts < 55 and tag not in ("Clinical Trial", "Buyback"),
          "compliance paperwork is scoring as news",
          f"{(pts, tag)} <- {head[:56]!r}")
    check(any(rx.search(head) for rx in _NEVER),
          "compliance paperwork can still be promoted from inside the PDF",
          head[:56])

# (b) And the four filings themselves, with the summaries they actually had.
#     Each one keeps a tag no source but the attachment ever argued for.
PDF_ONLY = [
    ("Clinical Trial",
     "Maral Overseas Limited has informed the Exchange regarding 'Report on "
     "re-lodgment of Transfer Requests'",
     "Maral Overseas Limited submitted a report to the stock exchanges on the "
     "re-lodgment of physical share transfer requests for August 2026 under "
     "the SEBI special-window provision."),
    ("Clinical Trial", "As per the pdf enclosed.",
     "Venus Remedies Ltd has announced a special window for re-lodgement of "
     "transfer requests for physical shares. The company has shared the "
     "details on its social media channels."),
    ("Clinical Trial",
     "Report for re-lodgement of physical shares for August 2026 attached.",
     "Hisar Spinning Mills filed a report on re-lodgement of physical share "
     "transfer requests for August 2026. The registrar confirmed that no "
     "requests were received, processed, approved or rejected."),
    ("Buyback",
     "Form MR-3 (Secretarial Audit Report for the Financial Year ended "
     "31st March 2026",
     "Superior Industrial Enterprises has released its Secretarial Audit "
     "Report for the financial year ended March 31, 2026. The auditors "
     "confirmed that the company has generally complied with all applicable "
     "provisions."),
]
for tag, head, summ in PDF_ONLY:
    got = pipeline.category_from_summary("General Updates", head, summ, tag)
    check(got != tag,
          "a tag the summary does not support is surviving from the PDF",
          f"kept {tag!r} <- {summ[:56]!r}")

# (c) But a tag the HEADLINE states outright is left alone even when the
#     summary is quieter. Two sources are not disagreeing there; one is just
#     saying less. This is the guard that stops (b) from becoming the next
#     over-correction.
check(pipeline.category_from_summary(
          "Board Meeting", "Declaration of interim dividend of Rs 4 per share",
          "The board met on Tuesday and approved a payout to shareholders "
          "of record.", "Dividend") != "Other",
      "a tag the headline states outright is being demoted")

# (d) Promoter dealings are exempt, and have to stay exempt. They are not
#     read off the document at all - they come from the stake-disclosure
#     form, whose whole purpose is to record who moved the shares. Their
#     summaries routinely never use the word "promoter".
for tag in ("Promoter Buy/Sell", "Inter-se Transfer"):
    check(rules.tag_supported(tag, "Innovative Money Matters Pvt Ltd "
                              "acquired 55,000 shares of Avonmore Capital"),
          "a promoter dealing is being asked to corroborate itself",
          tag)

# ---------------------------------------------------------------------------
# 28. Selling is as much a deal as buying.
#
# Only the NOUN "divestment" was in the Acquisition pattern, so three
# divestments on 8 September were tagged by whatever else their summary
# mentioned - and because Scheme Of Arrangement scores 69 against
# Acquisition's 65, nothing could dislodge two of them.
DIVESTMENTS = [
    "ELGI Compressors USA Inc. has divested its entire stake in Gentex Air "
    "Solutions LLC to the joint-venture partner, releasing exclusivity",
    "The board approved an in-principle sale of the stake in Credo Advanced "
    "Chemicals Ltd to Mr Naman Madhav Patel for Rs 37.63 crore",
    "The company sold its entire shareholding in the wholly owned subsidiary "
    "for a consideration of Rs 120 crore",
]
for text in DIVESTMENTS:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Acquisition", "a divestment is not being recognised as one",
          f"{(pts, tag)} <- {text[:56]!r}")

# A sale is not a scheme. One shared evidence regex for all three deal tags
# was satisfied by "sale of", which is how Elgi Equipments, Gujarat Apollo
# and Sanginita all sat under Scheme Of Arrangement.
for summ in DIVESTMENTS + [
    "The board approved the sale of its Gujarat property and related assets "
    "to AAG Capital Holdings Private Limited, a related party, for "
    "Rs 12.54 crore"
]:
    got = pipeline.category_from_summary(
        "General Updates", "informed the Exchange about General Updates",
        summ, "Scheme Of Arrangement")
    check(got != "Scheme Of Arrangement",
          "a sale is being kept as a scheme of arrangement",
          f"{summ[:56]!r}")

# A real scheme is still a scheme.
for summ in [
    "The board approved a scheme of arrangement for the demerger of the "
    "consumer business into a separate listed entity, subject to NCLT",
    "The NCLT has sanctioned the composite scheme of amalgamation between "
    "the company and its wholly owned subsidiary",
]:
    got = pipeline.category_from_summary(
        "Scheme of Arrangement", "Scheme of Arrangement", summ,
        "Scheme Of Arrangement")
    check(got in (None, "Scheme Of Arrangement"),
          "a genuine scheme of arrangement is being demoted", summ[:56])

# And a property sale is not an acquisition either - the same reason buying
# land is not. Consistency here is the point: the land guard was added in
# August for purchases, and a sale has to read the same way.
pts, tag = rules.score_text(
    "The board approved the sale of its Gujarat property and related assets "
    "to AAG Capital Holdings Private Limited for Rs 12.54 crore", floor=0)
check(tag != "Acquisition", "a property sale is being published as a deal",
      f"{(pts, tag)}")


# ---------------------------------------------------------------------------
# 29. A person's honorific ends in a full stop.
#
# Nearly every pattern here is windowed - "(appointed)[^.]{0,70}(director)" -
# and the window keeps a match inside one sentence, which is what stops two
# unrelated events from combining. But [^.] stops dead at the dot in "Mr.",
# and the filings that name a person are exactly the ones about people.
#
# Six filings on 8 September were mis-tagged by this alone. Every one scored
# NOTHING, so whatever word triage found in the attachment decided the
# category: five went to Legal/Reg and one to Investor Meet.
check(rules.soften_stops("re-appointed Ms. Neha B. Chaudhari as Director")
      == "re-appointed Ms Neha B Chaudhari as Director",
      "honorifics and initials are not being softened")

# And "Ltd." is left alone on purpose. It DOES end a sentence, and merging
# two sentences would let a window cross from one event into the next, which
# is the fault the windows exist to prevent.
check("Ltd." in rules.soften_stops(
          "as Director of ABC Ltd. The board declared a dividend."),
      "a full stop that really does end a sentence is being removed")

APPOINTMENTS = [
    ("Change In Management",
     "DJS Stock & Shares Ltd has re-appointed Ms. Neha Kailash Bhageria as "
     "an Independent Non-Executive Woman Director for a second term"),
    # The bare verb. Only the noun and the past participle were listed, so
    # this scored nothing at all.
    ("Change In Management",
     "Real Touch Finance received approval from the Reserve Bank of India to "
     "appoint Mr. Chinnian Mani as Managing Director"),
    # The role. Manager is a statutory position under section 196.
    ("Change In Management",
     "Varun Mercantile announced the re-appointment of Ms. Kirti B. "
     "Chaudhari as the Manager of the company"),
    ("Change In Management",
     "Navi Finserv has appointed Mr. Apoorve Goyal as a Nominee Director, "
     "subject to approval from the Reserve Bank of India"),
    # Role BEFORE the verb, which no windowed pattern could see.
    ("Resignation",
     "Maxvolt Energy said its whole-time director and chairman Vishal Gupta, "
     "who is due to retire by rotation, will be re-appointed"),
]
for want, text in APPOINTMENTS:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want, "an appointment is not being recognised as one",
          f"{(pts, tag)} want {want} <- {text[:52]!r}")


# ---------------------------------------------------------------------------
# 30. A regulator granting what the company asked for is not a legal matter.
#
# retag() has the last word, and its rule for "an order FROM a regulator is
# not a customer order" also covered approvals. Two appointments needing the
# Reserve Bank's consent came out as Legal/Reg - and so would an NCLT
# SANCTIONING a scheme of arrangement, which is the scheme itself.
check(rules.retag("received approval from the Reserve Bank of India to "
                  "appoint Mr Mani as Managing Director") is None,
      "a regulator's consent is being read as a legal matter")

pts, tag = rules.score_text(
    "The NCLT has sanctioned the composite scheme of amalgamation between "
    "the company and its wholly owned subsidiary", floor=0)
check(tag == "Scheme Of Arrangement",
      "an NCLT sanction of a scheme is being read as litigation", f"{(pts, tag)}")

# A regulator acting AGAINST the company still is one.
for text in [
    "The company received a GST demand order from the Commissioner of "
    "Central Tax imposing a penalty of Rs 2 crore",
    "Restaurant Brands Asia received an order from the Additional District "
    "Magistrate in Agra imposing a fine of Rs 1,60,000",
]:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Legal/Reg", "an adverse regulatory order stopped being one",
          f"{(pts, tag)} <- {text[:52]!r}")

# There must be ONE retag. There were two copies of its loop, and they had
# drifted: the consent guard was added to the function while score_text kept
# its own inline copy, so the half of the pipeline that reads the PDF went on
# calling an RBI-approved appointment a legal matter.
import inspect                                          # noqa: E402
_body = inspect.getsource(rules.score_text)
check("_RETAG_RE" not in _body,
      "score_text has its own copy of the retag loop again")


# ---------------------------------------------------------------------------
# 31. Where a Promoter Buy/Sell tag came from decides whether it may be
#     overruled.
#
# Filed under SAST or Regulation 29, the form's whole purpose is to record
# who moved the shares, and no summary can overrule it. Arrived from a regex
# in an attachment, it has no such standing: every SAST form prints
# "promoter and promoter group" in its table headings whether or not the
# acquirer is one.
check(rules.stake_category("Insider Trading / SAST / Disclosures under "
                           "Reg. 29(1) of SEBI (SAST) Regulations, 2011"),
      "a real stake disclosure is not being recognised")
check(not rules.stake_category("Corp. Action / Record Date"),
      "a record date is being treated as a stake disclosure")

# Filed under Record Date, tagged Promoter Buy/Sell by the attachment, and
# its summary says outright that it is an acquisition.
check(pipeline.category_from_summary(
          "Corp. Action / Record Date",
          "The Board of Directors fixed September 25, 2026 as the cut-off date",
          "Systematic Industries is acquiring 100% of Wire Brigade Industries "
          "to make it a wholly-owned subsidiary.",
          "Promoter Buy/Sell") == "Acquisition",
      "a promoter tag from the PDF is blocking a stated acquisition")

# And the genuine article is still untouchable, exactly as before.
check(pipeline.category_from_summary(
          "Insider Trading / SAST / Disclosures under Reg. 29(2) of SEBI "
          "(SAST) Regulations, 2011",
          "The Exchange has received the disclosure under Regulation 29(2)",
          "Innovative Money Matters Pvt Ltd acquired 55,000 shares of "
          "Avonmore Capital, raising its stake to 12.4%.",
          "Promoter Buy/Sell") in (None, "Promoter Buy/Sell"),
      "a real Regulation 29 disclosure is being relabelled an acquisition")

# There must be one copy of the stake-category list, too.
check(triage.STAKE_CATEGORY is rules.STAKE_CATEGORY,
      "triage has its own copy of the stake-category list again")


# ---------------------------------------------------------------------------
# 32. Paperwork that arrives once a day, and a bond being called.
#
# Great Eastern Shipping's "daily report for the equity shares bought back"
# was published as a Buyback: the pattern knew "buy back" and not "bought
# back", and the exchange had already said "Daily Buy Back" in the category
# field, which nothing was reading.
for cat, head in [
    ("Corp Action / Daily Buy Back of equity shares",
     "We enclose herewith the daily report for the equity shares bought back"),
    ("Corp Action", "Daily buy-back disclosure for September 7 2026"),
]:
    pts, tag = rules.score(cat, head)
    check(pts < 55 and tag != "Buyback",
          "a daily buyback report is crowding out the buyback",
          f"{(pts, tag)} <- {head[:52]!r}")

pts, tag = rules.score("Corp Action",
                       "Board approved a buy-back of equity shares up to "
                       "Rs 400 crore")
check(tag == "Buyback", "a real buyback stopped being recognised", f"{(pts, tag)}")

# Canara Bank filed twice about "exercising the call option" on its Basel III
# Additional Tier I bonds. Neither said "redeem", so neither read as debt
# servicing, and both were published as Ratings Updates because the exchange
# had filed them under Credit Rating.
pts, tag = rules.score_text(
    "Canara Bank has decided to exercise the call option on specific "
    "Basel III Compliant Additional Tier I Bonds", floor=0)
check(tag == "Routine", "calling a bond is not being read as repaying one",
      f"{(pts, tag)}")


# ---------------------------------------------------------------------------
# 33. A decimal point is not the end of a sentence.
#
# The same fault as the honorific, in the place it does the most damage. The
# rule that recognises a dividend record date is
# "record date[^.]{0,60}(dividend)", and in
#
#   "set a record date for a Rs 0.60 dividend"
#
# there is a full stop between the two words, so it saw nothing, so no money
# event was found, so Aristo Bio-Tech's dividend was published as a Meeting.
# That is the mistake that turned sixty real dividends into meetings in
# August, arriving by a different route.
check(rules.soften_stops("a record date for a Rs 0.60 dividend")
      == "a record date for a Rs 060 dividend",
      "a decimal point is still being read as the end of a sentence")

check(rules._MONEY_HAPPENED.search(rules.soften_stops(
          "The board approved the re-appointment of two directors, appointed "
          "a cost auditor, set a record date for a Rs 0.60 dividend, and "
          "scheduled the 21st AGM for 30 Sep 2026")) is not None,
      "a dividend behind a decimal point is invisible to the money test")


# ---------------------------------------------------------------------------
# 34. A record date is a dividend when it is a record date FOR the dividend.
#
# All 32 of these read the same way and every one was a Meeting, because the
# meeting is named first and that is the discriminator. Two things outrank
# word order: the exchange filed them under Record Date, and a payout is
# what the date decides.
DIVIDEND_RECORD_DATES = [
    ("Record Date",
     "Everest Kanto Cylinder Limited has scheduled its 47th Annual General "
     "Meeting for September 29, 2026. The company has set September 18, "
     "2026, as the record date to determine shareholder eligibility for the "
     "proposed dividend."),
    ("Corp. Action / Record Date",
     "BEML Limited has scheduled its 62nd Annual General Meeting for "
     "September 29, 2026, to be held via video conferencing. The company has "
     "set September 22, 2026, as the record date to determine shareholder "
     "eligibility for the final dividend."),
    ("Record Date",
     "Aristo Bio-Tech has scheduled its 21st Annual General Meeting for "
     "September 30, 2026. The company also declared a final dividend of "
     "Rs 0.60 per share and set September 23, 2026, as the record date for "
     "eligibility."),
    ("Corp. Action / Book Closure",
     "One Global Service Provider Ltd announced the record date and book "
     "closure period for its 34th AGM and dividend payment."),
]
for cat, summ in DIVIDEND_RECORD_DATES:
    got = pipeline.category_from_summary(
        cat, "has informed the Exchange that Record date for the", summ,
        "Meeting")
    check(got == "Dividend",
          "a dividend record date is being published as a meeting",
          f"got {got!r} <- {summ[:56]!r}")

# And a record date fixed only to decide who may VOTE is the meeting. This is
# the line that keeps the rule above from becoming the next over-correction,
# and it is the user's standing rule: an AGM belongs in no other category.
AGM_ONLY_RECORD_DATES = [
    ("Record Date",
     "The company has set September 22, 2026, as the record date to "
     "determine which shareholders may vote at the 41st Annual General "
     "Meeting, to be held on September 30, 2026."),
    ("Corp. Action / Record Date",
     "Filatex India sent a letter to shareholders without registered email "
     "IDs, providing web links to the 36th AGM notice and the annual report, "
     "and reminding them to claim any unclaimed dividends."),
]
for cat, summ in AGM_ONLY_RECORD_DATES:
    got = pipeline.category_from_summary(
        cat, "Record date and e-voting details", summ, "Meeting")
    check(got != "Dividend",
          "an AGM-only record date is being published as a dividend",
          f"got {got!r} <- {summ[:56]!r}")


# ---------------------------------------------------------------------------
# 35. What makes an order a legal matter is that it TAKES something.
#
# Not who signed it, and not which way round the sentence runs. Adding the
# reversed form - "an IRDAI order" rather than "an order from IRDAI" - swept
# up four real mergers whose schemes had just been sanctioned, because those
# say "NCLT order" too.
ADVERSE = [
    "ICICI Lombard got an IRDAI order on Sep 7 2026 imposing a Rs 1 crore "
    "penalty for breaches in outsourcing regulations",
    "Carraro India received an Order-in-original from Customs demanding a "
    "differential IGST of about Rs 15.24 crore and a penalty of Rs 5 crore",
    "The company received a GST demand order from the Commissioner imposing "
    "a penalty of Rs 2 crore",
]
for text in ADVERSE:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Legal/Reg",
          "a regulator's penalty is being published as a customer order win",
          f"{(pts, tag)} <- {text[:56]!r}")

FRIENDLY = [
    "Share India Securities has received the NCLT order approving its merger "
    "with Silverleaf Capital Services",
    "Lactose India Ltd announced that the amalgamation with Vitanosh "
    "Ingredients Private Ltd has become effective from September 5 2026, "
    "following the NCLT order dated August 20 2026",
    "The Board of GB Global Limited has formally acknowledged the NCLT order "
    "sanctioning its merger with Dev Land & Housing Private Limited",
    "Real Touch Finance received approval from the Reserve Bank of India to "
    "appoint Mr. Chinnian Mani as Managing Director",
]
for text in FRIENDLY:
    pts, tag = rules.score_text(text, floor=0)
    check(tag != "Legal/Reg",
          "an order granting what the company asked for reads as litigation",
          f"{(pts, tag)} <- {text[:56]!r}")


# ---------------------------------------------------------------------------
# 36. Two more categories that were reading their own filings as nothing.
#
# A Committee of Creditors meeting is a thing only a company in insolvency
# files, and the Nclt evidence knew none of those words - so Vas
# Infrastructure and JCT were demoted out of the category they belonged in.
for summ in [
    "Vas Infrastructure Ltd has notified that its 28th Committee of "
    "Creditors meeting will take place on 9 September 2026",
    "JCT Ltd announced that its 16th Committee of Creditors meeting will be "
    "held on 7 September 2026 via video conference",
]:
    check(rules.tag_supported("Nclt", summ),
          "an insolvency filing cannot corroborate its own category",
          summ[:56])

# And when the exchange says the filing IS the results, it is. Maruti
# Interior's Q1 filing "also noted the completion of a Rs 45.30 crore Rights
# Issue", and Rights Issue scores 72 against Results' 64, so a completed
# issue from an earlier month became the news.
check(pipeline.category_from_summary(
          "Result / Financial Results",
          "Financial result of the company for the quarter ended 30th June",
          "Maruti Interior Products reported its financial results for the "
          "quarter ended June 30, 2026. The company also noted the "
          "completion of a Rs 45.30 crore Rights Issue and the acquisition "
          "of the remaining 70% stake in Arrowin Metaltech.",
          "Results") == "Results",
      "a results filing is being renamed after something it mentions")


# ---------------------------------------------------------------------------
# 37. One vocabulary for "something happened".
#
# meeting_is_the_subject knew four events - dividend, bonus, split, buyback -
# while meeting_only used _MONEY_HAPPENED, which knows fifteen. So a board
# that approved a preferential issue of 2.5 million convertible warrants
# counted as having done nothing, and KCK Industries was published as a
# Meeting because the same sentence went on to schedule the AGM that would
# approve it.
check(pipeline.category_from_summary(
          "Outcome of Board Meeting",
          "Kck Industries Limited has informed the Exchange regarding "
          "Outcome of Board Meeting held on September 5",
          "The board approved the FY 2025-26 Director's Report, planned a "
          "preferential issue of up to 2.5 million convertible warrants "
          "(worth Rs 50 cr) at Rs 20 each, moved its registered offices "
          "within Chandigarh, scheduled an AGM to seek shareholder approval, "
          "and appointed a scrutinizer for e-voting.",
          "Warrants") in (None, "Warrants"),
      "a board that approved a warrant issue is being called a meeting")


# ---------------------------------------------------------------------------
# 38. A sentence saying nothing happened counts for nothing.
#
# Four filings under Investor Meet were relabelled Results by their own
# disclaimer: "No specific financial results or business developments were
# disclosed in this filing" scores 64 as Results, because the words
# "financial results" are in it.
check(rules.drop_denials(
          "The company met analysts. No specific financial results or "
          "business developments were disclosed in this filing.").strip()
      == "The company met analysts.",
      "a sentence stating that nothing happened is still being scored")

# But only sentences with no number in them. "not less than Rs 100 crore was
# approved" is a real event that happens to contain the word not.
check("100 crore" in rules.drop_denials(
          "The board approved not less than Rs 100 crore of capital "
          "expenditure."),
      "a real event is being dropped for containing a negative word")

pts, tag = rules.score_text(
    "Action Construction Equipment has announced a schedule for upcoming "
    "meetings with analysts and institutional investors. No specific "
    "financial results or business developments were disclosed.", floor=0)
check(tag != "Results", "a disclaimer is still being read as the results",
      f"{(pts, tag)}")


# ---------------------------------------------------------------------------
# 39. A presentation filing attaches a presentation.
#
# Investor Presentation scores 57 and Investor Meet 55, and MEETING_KINDS is
# first-match-wins with the presentation leading it - so a passing MENTION
# beat the meeting a filing was actually about. Home First Finance announced
# its "schedule for upcoming analyst and institutional investor meetings,
# including non-deal roadshows in the UK" and mentioned only that officials
# "will use already public investor presentations".
MEETING_KIND_CASES = [
    ("Investor Meet",
     "Home First Finance has announced its schedule for upcoming analyst and "
     "institutional investor meetings, including non-deal roadshows in the "
     "UK. Company officials will use already public investor presentations "
     "during these discussions."),
    ("Investor Meet",
     "Ashok Leyland announced an investor meeting scheduled for 11 September "
     "2026 at Trident Nariman Point"),
    # The same words in the other order, which no pattern could see:
    # "a one-on-one meeting WITH analysts and institutional investors".
    ("Investor Meet",
     "Tips Music has scheduled a one-on-one meeting with analysts and "
     "institutional investors on September 12"),
    ("Investor Presentation",
     "Borosil Renewables shared its corporate presentation outlining current "
     "and planned solar glass capacity"),
    ("Investor Presentation",
     "Please find enclosed the investor presentation for the quarter ended "
     "June 30, 2026"),
    ("Concall",
     "Behari Lal Engineering Ltd has uploaded the audio recording of its "
     "Q1 FY 2026-27 earnings conference call"),
]
for want, text in MEETING_KIND_CASES:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == want, "the wrong kind of investor event",
          f"{(pts, tag)} want {want} <- {text[:52]!r}")


# ---------------------------------------------------------------------------
# 40. The exchange's own category is a source in its own right.
#
# The corroboration rule asks whether a tag could ONLY have come from the
# attachment, and it was asking the headline alone. A headline can drown out
# the category: Zinema Media's "Approval for Preferential Issue pursuant to
# NCLT order" scores 64/Legal-Reg, while the category says plainly "Company
# Update / Preferential Issue".
check(pipeline.category_from_summary(
          "Company Update / Preferential Issue",
          "Approval for Preferential Issue pursuant to NCLT order, subject "
          "to approval of shareholders",
          "Zinema Media is issuing 24.99 lakh equity shares to settle debts "
          "with creditors of Premier Futsal Management. The company is also "
          "increasing its authorized share capital.",
          "Pref") in (None, "Pref"),
      "a tag the exchange's own category names is being demoted")

# An L1 bidder has won the work, which is how a public contract is awarded.
check(rules.tag_supported(
          "Order",
          "BCPL Railway Infrastructure has emerged as the lowest bidder for "
          "a railway electrification project in the Asansol division"),
      "an order win cannot corroborate its own category")


# ---------------------------------------------------------------------------
# 25. A promoter converting warrants is a promoter, not an acquirer
#
# Modern Dairies: "promoter Krishan Kumar Goyal and persons acting in concert
# have converted convertible warrants into 1,900,000 equity shares, filed under
# SEBI Regulation 29(2)". Published as an Acquisition, helped along by the AI's
# own key number - "Acquisition of 1,900,000 equity shares".
#
# Two faults. "converted" was not in the promoter verb list, though converting
# warrants you hold is exactly what Regulation 29(2) exists to disclose. And
# Warrants was not a tag a promoter transaction could take over from.
#
# The trap in fixing it: "convert" as a stem also matches "CONVERTible
# warrants", so a company ALLOTTING convertible warrants to its promoters
# became the promoters dealing. The verb has to be the action.
# ---------------------------------------------------------------------------

PROMOTER_ACTED = [
    "Modern Dairies disclosed that promoter Krishan Kumar Goyal and persons "
    "acting in concert have converted convertible warrants into 1,900,000 "
    "equity shares. Acquisition of 1,900,000 equity shares",
    "The promoter has converted 5,00,000 warrants into equity shares",
    "Promoter group entity is converting its warrants into shares",
]
for text in PROMOTER_ACTED:
    check(rules.promoter_deal(text),
          "a promoter converting warrants is not read as a promoter dealing",
          f"{text[:62]!r}")
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Promoter Buy/Sell",
          "a promoter converting warrants landed elsewhere",
          f"{(pts, tag)} <- {text[:58]!r}")

# The company ISSUING them is a Warrants filing, however many times the word
# "promoter" appears as the recipient.
COMPANY_ISSUED = [
    "Allotment of 60,82,000 convertible warrants to promoters on a "
    "preferential basis",
    "Kiri Industries is issuing 60.82 lakh warrants to its promoters at "
    "Rs 475 per warrant",
    "Digicontent approved the preferential issue of 1,40,85,571 warrants at "
    "INR 26.41 each",
    "Allotment of 65,00,000 convertible equity warrants on a preferential "
    "basis to the promoter group",
]
for text in COMPANY_ISSUED:
    pts, tag = rules.score_text(text, floor=0)
    check(tag == "Warrants",
          "a company issuing warrants was read as its promoters dealing",
          f"{(pts, tag)} <- {text[:58]!r}")



# ---------------------------------------------------------------------------
# 26. Six filings that reached the insider page without a trade in them
#
# 11 September, every one of them tagged Promoter Buy/Sell and published on
# /insider as somebody dealing in their own shares.
#
# The first three are the company creating NEW shares. They say "promoter" -
# as the recipient, or even as "NON-promoter investors" - and they carry a
# verb the promoter rule looks for, because a convertible warrant "can be
# CONVERTED". The NSE copy of the Raymond Realty filing was sitting under
# Warrants at the same moment the BSE copy was under Promoter Buy/Sell, which
# is as clear as a bug report gets.
#
# The fourth moves shares inside the promoter family and says so in words the
# inter-se rule had never met. The last two are not about shares at all: they
# reached a share-dealing category from a passing match in the attachment,
# which nothing could check, because Promoter Buy/Sell was the one tag with no
# evidence rule.
# ---------------------------------------------------------------------------

COMPANY_ISSUE_NOT_A_TRADE = [
    ("Connplex",
     "Connplex Cinemas Limited has informed the Exchange about Preferential "
     "issue. Connplex Cinemas is raising Rs 18.64 crore by issuing 8,00,000 "
     "convertible warrants to non-promoter investors. These warrants can be "
     "converted into equity shares within 18 months."),
    ("Raymond Realty",
     "Fund Raising through Preferential Issue of Share Warrants and Increase "
     "in Authorised Share Capital. Raymond Realty approved raising up to "
     "about Rs 409 crore by issuing 66.57 lakh convertible warrants at "
     "Rs 614 each to a promoter-group investor, and increased its authorized "
     "share capital from Rs 70 crore to Rs 75 crore."),
    ("HBG Hotels",
     "Outcome of Board Meeting. HBG Hotels has approved raising Rs 47.02 "
     "crore through the preferential issue of 56.65 lakh convertible "
     "warrants. The company plans to use Rs 36 crore of these funds to "
     "acquire a 7,000 sq. mt. land parcel in Goa from its promoter group."),
]
for name, text in COMPANY_ISSUE_NOT_A_TRADE:
    check(not rules.promoter_deal(text),
          "a company issuing securities was read as a promoter trading",
          name)
    pts, tag = rules.score_text(rules.soften_stops(text), floor=0)
    check(tag == "Warrants",
          "a warrant issue did not come out as Warrants",
          f"{name}: {(pts, tag)}")

# ...and the promoter who really is dealing still is. A conversion of warrants
# ALREADY HELD creates nothing, and a sale on the open market on the day the
# board approved an issue is still a sale - which is why the fresh-issue guard
# has a second lock on it.
STILL_A_TRADE = [
    ("Modern Dairies converting warrants it holds",
     "Modern Dairies disclosed that promoter Krishan Kumar Goyal and persons "
     "acting in concert have converted convertible warrants into 19,00,000 "
     "equity shares, raising promoter holding."),
    ("a promoter selling on the day of an issue",
     "The board approved a preferential issue of 10,00,000 equity shares. "
     "Separately, promoter Ramesh Shah sold 45,000 shares in the open "
     "market on 9 September."),
    ("a SAST form that prints preferential allotment among its modes",
     "Disclosure under Regulation 29(2). Mode of acquisition: open market / "
     "public issue / rights issue / preferential allotment / inter-se "
     "transfer. Promoter Brij Rattan Bagri acquired 90,503 equity shares."),
]
for name, text in STILL_A_TRADE:
    check(rules.promoter_deal(text),
          "a real promoter trade was refused by the fresh-issue guard", name)

# Shares shuffled inside the family, in a filing that never says "inter-se".
TRADEWELL = (
    "Intimation for change in Promoter and promoter group shareholding and "
    "addition of Promoter group members. Tradewell Holdings Limited announced "
    "a minor internal reallocation of shares within its promoter group. "
    "Promoter Kamal Manchanda reduced his holding by 10,000 shares (0.33%), "
    "which were acquired by three new members added to the promoter group. "
    "Overall promoter and promoter group shareholding remains unchanged "
    "following the transactions.")
check(rules.interse_transfer(TRADEWELL),
      "a reallocation inside the promoter group was not read as inter-se",
      "Tradewell Holdings")
check(not rules.promoter_deal(TRADEWELL),
      "an inter-se reallocation was still read as a promoter trade",
      "Tradewell Holdings")

# A filing with no shares moving in it cannot corroborate a share-dealing tag.
NO_TRADE_IN_IT = [
    ("United Foodbrands",
     "United Foodbrands Limited has informed the Exchange about Issuance of "
     "Bank Guarantee in the form of a Stand-by Letter of Credit (SBLC). "
     "United Foodbrands issued a stand-by letter of credit worth Rs 17 crore "
     "through ICICI Bank to back a foreign-currency term loan taken by its "
     "wholly-owned subsidiary Barbeque Nation Restaurant LLC."),
    ("Burnpur Cement reclassification",
     "Intimation of NOC received from NSE in the matter of reclassification "
     "of a promoter to public category. Burnpur Cement has received a No "
     "Objection Certificate from the National Stock Exchange for "
     "reclassifying Mrs. Suchitra Agarwal from the promoter category to the "
     "public category."),
]
for name, text in NO_TRADE_IN_IT:
    check(not rules.tag_supported("Promoter Buy/Sell", rules.soften_stops(text)),
          "a filing with no share dealing in it corroborated Promoter Buy/Sell",
          name)

# The evidence rule asks for shares moving, NOT for the word "promoter" - that
# was the original objection to having one, and it was right. Every summary
# below describes a real promoter trade without using the word once.
REAL_TRADES = [
    "Innovative Money Matters Pvt Ltd acquired 55,000 shares of Avonmore "
    "Capital in the open market.",
    "Dr. Krishna Prasad Chigurupati sold 1.72 crore shares on Sep 11, 2026.",
    "Kalpesh B Kothari sold 18 shares in the open market. His holding fell "
    "from 67,674 to 67,656 shares.",
    "PAGAC Ecstasy Pte. Ltd. has increased the amount of debt secured by its "
    "shareholding in Nuvama Wealth Management.",
    "Peterhouse Investments Limited sold 150,000 equity shares of Usha "
    "Martin Limited in the open market.",
    "Nishant Pitti pledged 34,51,39,404 Easy Trip shares to Motilal Oswal.",
]
for text in REAL_TRADES:
    check(rules.tag_supported("Promoter Buy/Sell", rules.soften_stops(text)),
          "a real promoter trade failed its own evidence rule",
          text[:60])



# ---------------------------------------------------------------------------
# 27. A company buying a company, filed on a takeover form
#
# 7NR Retail "has acquired 100% of Cultureantique Jewellery Private Limited",
# funded by a preferential allotment. It went out on the insider page as a
# promoter trade.
#
# The guard that did it is a good one: a stake disclosure is filed under SAST
# precisely to say WHO moved the shares, so a summary that merely does not
# repeat the word "promoter" must not overturn it. What it lacked was the one
# exception - the summary saying, plainly, that the buyer was the company.
#
# It has to stay narrow. Every SAST headline carries the words "Substantial
# Acquisition of Shares & Takeovers", so anything keyed on "takeover" would
# unlock the guard for the entire category it protects.
# ---------------------------------------------------------------------------

SAST = "Disclosure under Regulation 29(2) of SEBI (Substantial Acquisition of Shares & Takeovers) Regulations, 2011"

_7NR_HEAD = "Preferential allotment"
_7NR = ("7NR Retail has acquired 100% of Cultureantique Jewellery Private "
        "Limited (CJPL) to diversify its business. The acquisition was funded "
        "through a preferential allotment of 9 crore equity shares to "
        "non-promoters via a share swap deal.")
for cat in ("", SAST, "Reg. 29(2) - SAST"):
    got = pipeline.category_from_summary(
        cat, _7NR_HEAD, _7NR_HEAD + " " + _7NR, current="Promoter Buy/Sell")
    check(got == "Acquisition",
          "a company buying a company stayed a promoter trade",
          f"category={cat[:34]!r} -> {got}")

# The promoter who really did buy shares is still protected by it.
AVONMORE = ("Promoter group entity Innovative Money Matters Private Limited "
            "has acquired 55,000 additional shares of Avonmore Capital in the "
            "open market.")
got = pipeline.category_from_summary(
    SAST, SAST, SAST + " " + AVONMORE, current="Promoter Buy/Sell")
check(got is None,
      "a promoter purchase was relabelled an acquisition again",
      f"-> {got}")


# ---------------------------------------------------------------------------

print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")

"""
Decides which announcements are important and which are routine paperwork.

How it works, plainly:
  1. If a filing matches the JUNK list, it is out. Full stop.
  2. Otherwise it gets a score out of 100 and a tag like "Results" or "Order Win".
  3. The filing CATEGORY (a fixed list the exchanges use) is trusted most.
     The headline only gets a full vote when the category is a vague one like
     "General Updates" or "Outcome of Board Meeting"; otherwise it can nudge
     the score but not run away with it.
  4. run.py keeps anything at or above `min_score` in config.json.

To tune: move a pattern between the lists below, or change its points.
Format is (tag shown on screen, points, "words|to|match"). Case is ignored.
"""

import re

# ---------------------------------------------------------------------------
# 1. JUNK - routine compliance filings. Dropped no matter what else they say.
# ---------------------------------------------------------------------------
JUNK = [
    r"trading window|closure of trading",
    r"newspaper (publication|advertisement|clipping)|copy of newspaper|publication in newspaper",
    r"loss of (share )?certificate|duplicate (share )?certificate|issue of duplicate",
    r"reconciliation of share capital",
    r"compliance certificate|certificate under (sebi|regulation)|annual secretarial",
    r"shareholding pattern|corporate governance report",
    r"investor complaint|grievance redressal",
    r"\biepf\b|unclaimed (dividend|share)|transfer of (equity )?shares to",
    r"share transfer|transmission of share",
    r"statement of deviation|monitoring agency",
    r"large corporate|lc framework",
    r"regulation 29\(|reg\.? ?29\(|regulation 31\(|regulation 10\(5\)|regulation 7\(2\)",
    r"submission of annual report|annual report for the (financial )?year",
    r"corrigend|amendment to (aoa|moa)|memorandum and articles",
    r"\besop\b|esos|esps|employee stock option|exercise of (stock )?option",
    r"scrutinizer|postal ballot notice|notice of (the )?(agm|egm|annual general)",
    r"proceedings of (the )?(agm|annual general)",
    r"\bfor the quarter ended.{0,10}$",
]

# ---------------------------------------------------------------------------
# 2. VAGUE categories - the exchange bucket tells us nothing, so read the
#    headline instead and give it a full vote.
# ---------------------------------------------------------------------------
VAGUE = [
    r"^general updates?$", r"^updates?$", r"^company update", r"^others?$",
    r"^outcome of (the )?board meeting", r"^board meeting",
    r"^press release", r"^media release", r"^announcement under regulation 30",
    r"^disclosure under sebi takeover", r"^insider trading",
    r"^integrated filing", r"^record date", r"^corp\.? action",
    r"^action\(s\) taken or orders passed", r"^news verification",
    r"^agreements?$", r"^intimation", r"^clarification",
]

# ---------------------------------------------------------------------------
# 3. IMPORTANT topics: (tag, points, pattern)
# ---------------------------------------------------------------------------
TOPICS = [
    ("Results",     62, r"financial result|quarterly result|(un)?audited (financial )?result|"
                        r"integrated filing.{0,5}financial|q[1-4] ?(fy)?\s?\d* result|"
                        r"results? for the (quarter|half|year)|standalone and consolidated financial"),
    ("Dividend",    60, r"\bdividend\b"),
    ("Bonus/Split", 68, r"bonus (issue|share)|issue of bonus|stock split|sub-?division of (equity |the )?share|"
                        r"split of (equity )?share|rights issue|letter of offer.{0,20}rights"),
    ("Buyback",     68, r"buy-?\s?back of (equity |fully )?"),
    ("M&A",         66, r"\bacquisition\b|has acquired|proposed acquisition|amalgamation|\bmerger\b|"
                        r"scheme of arrangement|de-?merger|slump sale|divestment|divestiture|"
                        r"stake sale|sale of (the )?(subsidiary|business|undertaking|division)|"
                        r"joint venture|strategic (partnership|alliance|investment)|"
                        r"share purchase agreement|\bspa\b executed"),
    ("Order Win",   62, r"bagging|receiv(ing|ed|t) of (orders?|contracts?|letter of award)|"
                        r"award of (order|contract)|order win|bags? (an? )?order|"
                        r"letter of (intent|award)|\bloi\b|work order|purchase order|"
                        r"contract (won|awarded|received|secured)|secures? (an? )?(order|contract|project)|"
                        r"\bwins?\b.{0,25}(order|contract|project|tender)"),
    ("Fund Raise",  58, r"fund ?rais|preferential (issue|allotment)|qualified institution|\bqip\b|"
                        r"rights entitlement|issue of (ncd|debenture|bond|warrant|convertible)|"
                        r"allotment of (equity share|warrant|ncd|debenture|bond|convertible)|"
                        r"capital raising|further public offer|\bfpo\b"),
    ("Open Offer",  62, r"open offer|public announcement.{0,25}(acquisition|offer)|"
                        r"detailed public statement|regulation 3\(1\)|delisting"),
    ("Legal/Reg",   58, r"insolvency|\bnclt\b|\bnclat\b|\bibc\b|\bcirp\b|liquidat|winding up|"
                        r"default in (payment|repayment)|one[- ]time settlement|debt restructur|"
                        r"forensic audit|sebi order|adjudicat|show cause|penalt|"
                        r"search and seizure|income tax (raid|survey|search)|\bfraud\b|"
                        r"attachment of (property|asset)|freezing of|arbitration award|"
                        r"supreme court|high court order|\bed\b (raid|summons)|qualified opinion"),
    ("Operations",  56, r"plant (shutdown|closure|fire|accident)|fire at (the )?(plant|factory|unit)|"
                        r"capacity (expansion|addition|augment)|new plant|greenfield|brownfield|"
                        r"commercial production|commissioning of|commencement of (production|operation)|"
                        r"force majeure|production (halt|suspend|stopp)|lock-?out|"
                        r"\bcapex\b|expansion (plan|project)"),
    ("Biz Update",  54, r"monthly business update|business update|revenue update|sales update|"
                        r"monthly sales|production (update|figures|volume)|operational (update|data)|"
                        r"quarterly (business |pre-?)update|key financial and operational|\bguidance\b"),
    ("Rating",      52, r"credit rating|rating (action|revision|upgrade|downgrade|reaffirm|assigned)|"
                        r"\bcrisil\b|\bicra\b|care ratings|india ratings|\bcareedge\b"),
    ("Leadership",  50, r"(resignation|appointment|cessation|re-?appointment|removal|retirement|change).{0,70}"
                        r"(managing director|chief executive|\bceo\b|chief financial|\bcfo\b|"
                        r"chairman|whole[- ]time director|statutory auditor|\bauditor\b)|"
                        r"change in (auditors|management)|resignation of (statutory )?auditor"),
    ("Corp Action", 50, r"change of name|name change|\bisin\b change|face value|"
                        r"reduction of (share )?capital|capital reduction"),
    ("Unusual",     48, r"spurt in volume|price (movement|volume)|clarification sought|news verification|"
                        r"exchange has sought"),
    ("Presentation",42, r"investor presentation|press release|media release|earnings call transcript|"
                        r"transcript of|analyst (meet|call)|conference call|con\.? ?call|"
                        r"institutional investor meet"),
    ("Board Meet",  40, r"board meeting|outcome of (the )?board"),
    ("People",      32, r"resignation|appointment|cessation|change in director|"
                        r"key managerial|company secretary|\bkmp\b|\bsmp\b|senior management"),
    ("Meeting",     22, r"shareholders meeting|postal ballot|voting result|\bagm\b|\begm\b|"
                        r"book closure"),
]

# ---------------------------------------------------------------------------
# 4. DOWNGRADE - things that LOOK big but are really only about the big thing.
#    "Audio recording of the earnings call on the Q1 results" is not the
#    results. "Board will meet on the 14th to consider results" is not either.
#    These cap the score no matter what else matched.
# ---------------------------------------------------------------------------
DOWNGRADE = [
    ("Presentation", 42, r"audio recording|video recording|transcript|earnings call|"
                         r"con\.? ?call|conference call|analysts?.{0,14}meet|investor meet|"
                         r"schedule of (the )?(analyst|investor)|intimation of (analyst|investor)"),
    ("Board Meet",   40, r"(intimation|notice|prior intimation) (of|for|regarding).{0,45}board meeting|"
                         r"board meeting (will be|is scheduled|to be held|shall be|has been scheduled)|"
                         r"meeting of the board of directors.{0,90}(will be held|is scheduled|shall be held|"
                         r"to consider)|to consider and approve|scheduled to be held on"),
    ("People",       32, r"internal auditor|secretarial auditor|cost auditor|"
                         r"appointment of (the )?(internal|secretarial|cost)"),
]

_JUNK_RE = [re.compile(p, re.I) for p in JUNK]
_DOWN_RE = [(tag, cap, re.compile(p, re.I)) for tag, cap, p in DOWNGRADE]
_VAGUE_RE = [re.compile(p, re.I) for p in VAGUE]
_TOPIC_RE = [(tag, pts, re.compile(p, re.I)) for tag, pts, p in TOPICS]


def _best(text):
    """Highest-scoring topic in a piece of text -> (points, tag, how_many_matched)."""
    if not text:
        return 0, None, 0
    hits = [(pts, tag) for tag, pts, rx in _TOPIC_RE if rx.search(text)]
    if not hits:
        return 0, None, 0
    pts, tag = max(hits)
    return pts, tag, len(hits)


def score(category, headline, critical=False):
    """Return (score 0-100, tag)."""
    category = (category or "").strip()
    headline = (headline or "").strip()

    if any(rx.search(category) or rx.search(headline) for rx in _JUNK_RE):
        return 3, "Routine"

    cat_pts, cat_tag, _ = _best(category)
    head_pts, head_tag, head_n = _best(headline)
    vague = not category or any(rx.search(category) for rx in _VAGUE_RE)

    if vague:
        # Category tells us nothing useful - the headline decides.
        pts, tag = (head_pts, head_tag) if head_pts >= cat_pts else (cat_pts, cat_tag)
    else:
        # Category leads; a strong headline can lift it, but only so far.
        pts, tag = cat_pts, cat_tag
        if head_pts - 8 > pts:
            pts, tag = head_pts - 8, head_tag

    if pts == 0:
        return 18, "Other"

    if head_n > 1:                 # several important themes in one filing
        pts += 4
    if critical:                   # BSE's own market-critical flag
        pts += 4
    pts = min(pts, 100)

    both = category + " || " + headline
    for d_tag, cap, rx in _DOWN_RE:
        if pts > cap and rx.search(both):
            pts, tag = cap, d_tag

    return pts, tag

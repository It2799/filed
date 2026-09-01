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
    r"corrigend",
    r"scrutinizer|postal ballot notice|notice of (the )?(agm|egm|annual general)",
    r"proceedings of (the )?(agm|annual general)",
    # A bare "<something> for the quarter ended <date>" heading is compliance
    # paperwork - but only when the something is not the results themselves.
    # Without the guard, whether a company's quarterly results survive came
    # down to how the date was punctuated: "quarter ended 30.6.2025" is 9
    # characters and was junked, "30.06.2025" is 10 and got through.
    r"^(?!.*\b(results?|earnings|outcome)\b).*\bfor the quarter ended.{0,10}$",
]
# NOTE: ESOP, annual reports and AoA/MoA amendments used to be dropped here.
# They're now kept as their own low-scoring categories, so they show under
# "All" but stay out of "Important".

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
# Points do double duty: they rank importance, AND they decide which label wins
# when a filing matches several. So the more specific pattern always carries a
# slightly higher number than the general one it sits inside - "Scheme Of
# Arrangement" beats "Acquisition", "QIP Allotment" beats "QIP" beats
# "Fund Raising". Anything scoring at or above `min_score` shows under
# "Important"; everything else is still kept and tagged, just under "All".
TOPICS = [
    # ---- corporate actions on the share itself -------------------------------
    ("Buyback",              70, r"buy-?\s?back"),
    ("Scheme Of Arrangement", 69, r"scheme of (arrangement|amalgamation|merger|demerger)|"
                                 r"composite scheme|de-?merger|\bdemerge"),
    ("Rights Issue",         68, r"rights issue|rights entitlement|letter of offer.{0,25}rights"),
    ("Split",                67, r"stock split|sub-?division of (equity |the )?share|"
                                 r"split of (equity )?share|face value.{0,30}split"),
    ("Bonus",                67, r"bonus (issue|share)|issue of bonus"),
    # "SAST" is the name of the regulations, not the name of an event. BSE
    # files every routine "someone's holding crossed a threshold" disclosure
    # under "Insider Trading / SAST", and "Substantial Acquisition of Shares"
    # is simply what the S and the A stand for - so both matched a promoter
    # buying 25,000 shares, scored it 66, and put it on the front page as an
    # open offer. They now carry their own label, below the bar. A real open
    # offer still announces itself in the words below.
    ("Open Offer",           66, r"open offer|detailed public statement|regulation 3\(1\)|"
                                 r"public announcement.{0,25}(acquisition|offer)"),
    ("Delisting",            64, r"\bdelist(ing|ed)?\b"),
    ("Stake Change",         50, r"\bsast\b|substantial acquisition of shares"),
    ("Acquisition",          65, r"\bacquisition\b|has acquired|proposed acquisition|amalgamation|"
                                 r"\bmerger\b|slump sale|divestment|divestiture|stake sale|"
                                 r"sale of (the )?(subsidiary|business|undertaking|division)|"
                                 r"joint venture|strategic (partnership|alliance|investment)|"
                                 r"share purchase agreement|\bspa\b executed"),

    # ---- raising money -------------------------------------------------------
    ("Qip Allotment",        63, r"qip allotment|allotment.{0,30}qualified institution|"
                                 r"allotment of (equity )?shares.{0,40}\bqip\b"),
    ("Qip",                  62, r"\bqip\b|qualified institution(s)? placement"),
    # A warrant has to be the instrument, not the verb. "\bwarrants?\b" alone
    # matched "the matter warrants disclosure" and "search warrant issued by
    # the Income Tax Department" - and over PDF prose, where "warrants further
    # clarification" is a stock phrase, it was a steady source of filings
    # promoted to a fund-raising item on nothing at all.
    ("Warrants",             61, r"convertible warrants?|share warrants?|"
                                 r"warrants? (allotment|conversion|holders?|"
                                 r"into|at rs|of rs)|"
                                 r"(issue|issuance|allotment|conversion|subscription|"
                                 r"exercise) of[^.]{0,30}warrants?"),
    ("Pref",                 60, r"preferential (issue|allotment|basis)|on a preferential"),
    ("Fund Raising",         58, r"fund ?rais|capital raising|further public offer|\bfpo\b|"
                                 r"issue of (ncd|debenture|bond|commercial paper)|"
                                 r"allotment of (ncd|debenture|bond|convertible)|"
                                 r"private placement"),

    # ---- performance and operations -----------------------------------------
    ("Results",              64, r"financial result|quarterly result|(un)?audited (financial )?result|"
                                 r"integrated filing.{0,5}financial|q[1-4] ?(fy)?\s?\d* result|"
                                 r"results? for the (quarter|half|year)|"
                                 r"standalone and consolidated financial"),
    # "receipt of", not "receivt of" - the alternation used to read
    # receiv(ing|ed|t), which spells receiving, received and receivt. The one
    # spelling it missed is the one the exchanges actually use: "Receipt of
    # Order" scored 18/Other whenever the category was too vague to save it.
    ("Order",                62, r"bagging|(receipt|receiving|received) of "
                                 r"(orders?|contracts?|letter of award)|"
                                 r"award of (order|contract)|order win|bags? (an? )?order|"
                                 r"letter of (intent|award)|\bloi\b|work order|purchase order|"
                                 r"contract (won|awarded|received|secured)|"
                                 r"secures? (an? )?(order|contract|project)|"
                                 r"\bwins?\b.{0,25}(order|contract|project|tender)"),
    ("Dividend",             60, r"\bdividend\b"),
    ("Capacity Increase",    57, r"capacity (expansion|addition|augment|increase)|new plant|"
                                 r"greenfield|brownfield|commercial production|commissioning of|"
                                 r"commencement of (production|operation)|\bcapex\b|"
                                 r"expansion (plan|project)|debottleneck"),
    ("Business Update",      55, r"monthly business update|business update|revenue update|"
                                 r"sales update|monthly sales|production (update|figures|volume)|"
                                 r"operational (update|data)|quarterly (business |pre-?)update|"
                                 r"key financial and operational|\bguidance\b"),

    # ---- trouble -------------------------------------------------------------
    ("Nclt",                 60, r"\bnclt\b|\bnclat\b|\bibc\b|\bcirp\b|insolvency|liquidat|"
                                 r"winding up|resolution professional|corporate insolvency"),
    ("Legal/Reg",            58, r"default in (payment|repayment)|one[- ]time settlement|"
                                 r"debt restructur|forensic audit|sebi order|adjudicat|show cause|"
                                 r"penalt|search and seizure|income tax (raid|survey|search)|"
                                 r"\bfraud\b|attachment of (property|asset)|freezing of|"
                                 r"arbitration award|supreme court|high court order|"
                                 r"\bed\b (raid|summons)|qualified opinion|"
                                 # tax and appellate orders - the exchanges file these under
                                 # the same "order" category as a purchase order
                                 r"gst (demand|notice|order|liabilit)|demand order|"
                                 r"assessment order|tax (demand|notice|liabilit)|"
                                 r"order-?in-?appeal|input tax credit"),
    ("Operations",           56, r"plant (shutdown|closure|fire|accident)|"
                                 r"fire at (the )?(plant|factory|unit)|force majeure|"
                                 r"production (halt|suspend|stopp)|lock-?out|strike at"),

    # ---- ratings and holdings ------------------------------------------------
    ("Ratings Update",       53, r"credit rating|rating (action|revision|upgrade|downgrade|"
                                 r"reaffirm|assigned)|\bcrisil\b|\bicra\b|care ratings|"
                                 r"india ratings|\bcareedge\b|\besg rating\b"),
    ("Bulk And Block",       42, r"bulk deal|block deal|bulk and block"),
    ("Fii",                  38, r"\bfii\b|\bfpi\b|foreign (institutional|portfolio) investor|"
                                 r"shareholding of promoter|promoter (holding|pledge)|"
                                 r"encumbrance|invocation of pledge"),

    # ---- people --------------------------------------------------------------
    ("Change In Management", 51, r"change in (management|directorate|auditors)|"
                                 r"(appointment|re-?appointment).{0,70}(managing director|"
                                 r"chief executive|\bceo\b|chief financial|\bcfo\b|chairman|"
                                 r"whole[- ]time director|statutory auditor)"),
    ("Resignation",          40, r"resignation|cessation|removal|retirement of|"
                                 r"stepped down|relinquish"),

    # ---- meetings and talk ---------------------------------------------------
    # These three used to share one "Concall" tag scored at 45, which put them
    # below the bar for Important - so a reader could not filter for them at
    # all. They are what an investor actually plans a week around, so each is
    # now its own category and each clears the bar on its own.
    ("Investor Presentation", 57, r"investor presentation|analyst presentation|"
                                  r"earnings presentation|corporate presentation"),
    ("Concall",              56, r"con\.? ?call|conference call|earnings call|"
                                 r"audio recording|video recording|transcript"),
    ("Investor Meet",        55, r"analysts?.{0,14}meet|institutional investor meet|"
                                 r"investor meet|"
                                 # "meet" has to be in it - without that,
                                 # "Intimation of Investor Presentation" was
                                 # being filed as a meeting.
                                 r"(schedule|intimation) of (the )?"
                                 r"(analyst|investor)[a-z /]{0,18}meet"),
    ("Outcome",              43, r"outcome of (the )?board meeting|outcome of the meeting"),
    ("Board Meeting",        41, r"board meeting|meeting of the board of directors"),
    ("Press Release",        44, r"press release|media release"),

    # ---- housekeeping, kept but low so they stay out of "Important" ----------
    ("Corp Action",          50, r"change of name|name change|\bisin\b change|"
                                 r"reduction of (share )?capital|capital reduction|record date|"
                                 r"book closure"),
    ("Unusual",              48, r"spurt in volume|price (movement|volume)|clarification sought|"
                                 r"news verification|exchange has sought"),
    ("Esop",                 30, r"\besop\b|esos|esps|employee stock option|"
                                 r"exercise of (stock )?option|stock appreciation"),
    ("Annual Report",        28, r"annual report|annual general meeting.{0,20}report"),
    ("Article Of Association", 27, r"article(s)? of association|memorandum and article|"
                                 r"\baoa\b|\bmoa\b|amendment to (aoa|moa)"),
    ("Meeting",              22, r"shareholders meeting|postal ballot|voting result|"
                                 r"\bagm\b|\begm\b"),
]

# ---------------------------------------------------------------------------
# 4. DOWNGRADE - things that LOOK big but are really only about the big thing.
#    "Audio recording of the earnings call on the Q1 results" is not the
#    results. "Board will meet on the 14th to consider results" is not either.
#    These cap the score no matter what else matched.
# ---------------------------------------------------------------------------
DOWNGRADE = [
    # An earnings call is still not the earnings, and a presentation is still
    # not the deal it describes - so these stay capped. The caps are just no
    # longer low enough to hide them from the reader entirely.
    ("Investor Presentation", 57, r"investor presentation|analyst presentation|"
                                  r"earnings presentation|corporate presentation"),
    ("Concall",       56, r"audio recording|video recording|transcript|earnings call|"
                          r"con\.? ?call|conference call"),
    ("Investor Meet", 55, r"analysts?.{0,14}meet|investor meet|"
                          r"(schedule|intimation) of (the )?"
                          r"(analyst|investor)[a-z /]{0,18}meet"),
    # The last two alternatives used to sit at the top level, not inside the
    # "meeting of the board of directors" group the indentation implied. So
    # "scheduled to be held on" and "to consider and approve" matched ANY text
    # containing them, and a completed acquisition that happened to mention an
    # EGM date was capped to 41 and relabelled a board meeting. Harmless while
    # only headlines were scored - they are short - and ruinous the moment the
    # same list is run over 4,000 characters of a board-outcome PDF, which is
    # what applying DOWNGRADE inside score_text() does.
    ("Board Meeting", 41, r"(intimation|notice|prior intimation) (of|for|regarding).{0,45}board meeting|"
                          r"board meeting (will be|is scheduled|to be held|shall be|has been scheduled|"
                          r"scheduled to be held)|"
                          r"meeting of the board of directors.{0,90}(will be held|is scheduled|"
                          r"shall be held|to consider and approve|to consider)"),
    # Labelled "Change In Management", not "Resignation" - the pattern matches
    # appointments as readily as departures, and calling an appointment a
    # resignation is the opposite of the truth.
    ("Change In Management", 32, r"internal auditor|secretarial auditor|cost auditor|"
                                 r"appointment of (the )?(internal|secretarial|cost)"),
]

# Downgrades that only make sense against a headline.
#
# The rest of the list describes what a document IS - a transcript, a slide
# deck, a notice that a board will meet - and that is just as true of 4,000
# characters as of forty. The auditor rule is different: it names one routine
# item on an agenda. Board minutes list a dozen such items, so over the body
# of a document it capped a genuine Rs 40 crore acquisition to 32 because the
# same meeting also appointed an internal auditor.
HEADLINE_ONLY = {"Change In Management"}

# ---------------------------------------------------------------------------
# 5. RETAG - the exchanges file a tax or court ORDER under the same category as
#    a purchase ORDER ("Award of Order / Receipt of Order"), so a GST demand
#    came out labelled as an order win. Same word, opposite meaning. These
#    patterns correct the label without touching the score.
# ---------------------------------------------------------------------------
RETAG = [
    ("Legal/Reg", r"gst (demand|order|notice|liabilit)|demand order|"
                  r"(income )?tax (demand|notice|order|liabilit)|assessment order|"
                  r"adjudicat|show cause|order-?in-?appeal|"
                  r"penalt.{0,40}(imposed|levied|order)|(imposed|levied).{0,40}penalt|"
                  r"input tax credit"),
]

_JUNK_RE = [re.compile(p, re.I) for p in JUNK]
_DOWN_RE = [(tag, cap, re.compile(p, re.I)) for tag, cap, p in DOWNGRADE]
_RETAG_RE = [(tag, re.compile(p, re.I)) for tag, p in RETAG]
_VAGUE_RE = [re.compile(p, re.I) for p in VAGUE]
_TOPIC_RE = [(tag, pts, re.compile(p, re.I)) for tag, pts, p in TOPICS]

# ---------------------------------------------------------------------------
# 6. THE THREE MEETING KINDS
#    BSE files calls and meetings under ONE heading - "Analysts/Institutional
#    Investor Meet/Con. Call Updates" - which matches all three patterns at
#    once. The generic machinery could not cope: the three sit in TOPICS at
#    57/56/55 AND in DOWNGRADE at the same numbers, so whichever scored highest
#    was immediately capped by the next one down, and every filing in that
#    shared bucket came out "Investor Meet" no matter what it said. "Audio
#    recording of the earnings conference call" was an Investor Meet.
#
#    They are three alternatives, not a ranking, so they are settled here
#    instead. The headline names the actual event and is trusted first; only
#    if it says nothing does the category get a vote, and a category naming
#    more than one of them means BSE's shared bucket, where a plain meet is by
#    far the most common thing and the safest default.
# ---------------------------------------------------------------------------
MEETING_KINDS = [
    ("Investor Presentation", r"investor presentation|analyst presentation|"
                              r"earnings presentation|corporate presentation"),
    ("Concall",               r"con\.? ?call|conference call|earnings call|"
                              r"audio recording|video recording|transcript"),
    ("Investor Meet",         r"analysts?.{0,14}meet|institutional investor meet|"
                              r"investor meet|road ?show|non-?deal roadshow"),
]
_MEETING_RE = [(tag, re.compile(p, re.I)) for tag, p in MEETING_KINDS]
_MEETING_TAGS = {tag for tag, _ in MEETING_KINDS}
# The score each kind carries, kept in step with TOPICS above so a concall out
# of BSE's shared bucket ranks the same as one filed under a clear heading.
MEETING_SCORE = {"Investor Presentation": 57, "Concall": 56, "Investor Meet": 55}


def meeting_kind(category, headline):
    """Which of the three this filing actually is. Headline wins."""
    for tag, rx in _MEETING_RE:
        if rx.search(headline or ""):
            return tag
    hits = [tag for tag, rx in _MEETING_RE if rx.search(category or "")]
    if len(hits) == 1:
        return hits[0]
    return "Investor Meet" if hits else None


def retag(text):
    """
    Re-label a filing once the PDF has actually been read.

    Plenty of headlines say nothing at all - a real one reads "Please refer to
    the letter enclosed", filed under "Award of Order / Receipt of Order". Only
    the PDF reveals it's a GST demand, not an order win. So after summarising
    we look again at what the document turned out to say.

    Returns a corrected tag, or None to leave it alone.
    """
    for r_tag, rx in _RETAG_RE:
        if rx.search(text or ""):
            return r_tag
    return None


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
        # Still worth relabelling - an unrecognised category can carry a
        # headline the retag rules understand.
        for r_tag, rx in _RETAG_RE:
            if rx.search(category + " || " + headline):
                return 50, r_tag
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

    # Once a filing has landed on any of the three meeting kinds, which one it
    # is gets settled by meeting_kind() rather than by whichever DOWNGRADE rule
    # happened to fire last. See section 6.
    if tag in _MEETING_TAGS:
        kind = meeting_kind(category, headline)
        if kind:
            tag, pts = kind, MEETING_SCORE[kind]

    # Correct the label where the category word is misleading. Score stands -
    # a tax demand is just as worth reading as an order win, it's not the same
    # kind of news.
    for r_tag, rx in _RETAG_RE:
        if rx.search(both):
            tag = r_tag
            break

    return pts, tag

def score_text(text, floor=0):
    """
    Score the actual contents of a filing rather than its headline.

    Exchange headlines are frequently useless - "Announcement under Regulation
    30 (LODR)-Press Release / Media Release" is what a company files for a
    Rs 260 crore acquisition. The news is in the PDF. This scores that text so
    a filing can be judged on what it says, not on how it was labelled.

    Returns (score, tag). Only the strongest topic counts, and a filing has to
    clear `floor` to be worth promoting.
    """
    if not text:
        return 0, None

    body = text[:4000]

    hits = [(pts, tag) for tag, pts, rx in _TOPIC_RE if rx.search(body)]
    if not hits:
        return 0, None
    pts, tag = max(hits)

    # Several strong themes in one document usually means a substantive
    # board outcome rather than a passing mention.
    strong = [h for h in hits if h[0] >= 55]
    if len(strong) > 1:
        pts += 4

    # The same "this only REFERS to the big thing" test score() applies. It was
    # missing here, and that asymmetry was the single largest source of wrong
    # categories on the site: two thirds of everything filed under Acquisition,
    # Pref and Warrants had been promoted by this function on a passing mention
    # somewhere in the PDF. "The proposal of fund raising is being placed
    # seeking approval" is a notice that a board will meet to consider raising
    # money; "Took note of the preferential issue" is a line in the minutes.
    # Neither is the event, and score() has always known that.
    for d_tag, cap, rx in _DOWN_RE:
        if d_tag in HEADLINE_ONLY:
            continue
        if pts > cap and rx.search(body):
            pts, tag = cap, d_tag

    if tag in _MEETING_TAGS:
        kind = meeting_kind("", body)
        if kind:
            tag, pts = kind, MEETING_SCORE[kind]

    for r_tag, rx in _RETAG_RE:
        if rx.search(body):
            tag = r_tag
            break

    pts = min(pts, 100)
    return (pts, tag) if pts >= floor else (0, None)

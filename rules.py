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
    # A company running a buyback files a report of the day's purchases EVERY
    # trading day for the length of the programme, under Regulation 18(i). One
    # buyback is one piece of news; the twenty daily reports that follow are a
    # ledger. They were scoring 70 apiece and crowding out the announcement
    # they were reporting on - Advanced Enzyme and SIS between them filed four
    # of the nineteen filings under Buyback.
    r"regulation 18\(i\)|daily report.{0,50}buy-?\s?back|"
    r"buy-?\s?back.{0,30}daily (report|disclosure)",
    # A partly-paid rights issue is followed by notices asking holders for the
    # next instalment. Housekeeping, not an issue.
    r"call money|reminder notice.{0,50}\bcall\b",
    # Depository plumbing: the date a company's shares became transferable at
    # CDSL or NSDL.
    r"date of connectivity|connectivity (informed|intimated) by",
    # Regulation 36(1)(b) is the rule that says a company must send its annual
    # report to shareholders. The covering letter is the single most misfiled
    # document on the site: it goes out with the annual report and the AGM
    # notice, so its PDF recites the dividend resolution, and twelve of the
    # thirteen wrong filings under Dividend were one of these letters. Shree
    # Hari Chemicals, Vippy Spinpro, Tega, Veerhealth, National Plastic and
    # UTL Industries all filed one on the same day.
    r"regulation 36\(1\)|reg\.? ?36\(1\)|"
    r"letter (to|sent to) (share ?holders|members|the members)|"
    r"web ?link.{0,30}annual report|annual report.{0,20}web ?link",
    # The KYC reminder that goes out with it.
    r"\bkyc\b (updation|update|details)|updation of \bkyc\b",
    # The sustainability report. Several hundred pages describing every plant,
    # every expansion and every governance policy the company has, which is why
    # it was read as a capacity increase and as a regulatory action.
    r"\bbrsr\b|business responsibility and sustainability report",
    # A company that has issued debentures certifies every interest payment on
    # the due date. Routine, and there is one per issue per period - all four
    # wrong filings under Buyback were interest certificates.
    r"payment of interest on[^.]{0,40}(non-?convertible|debenture|\bncd\b)|"
    r"certificate[^.]{0,40}payment of interest|"
    r"interest payment[^.]{0,20}(certificate|intimation)",
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
    # "Manager to the Offer" and the post-offer advertisement are the other two
    # names a real open offer goes by, and neither was listed - so Axis
    # Capital's post-offer advertisement for a live open offer scored nothing
    # at all.
    ("Open Offer",           66, r"open offer|detailed public statement|regulation 3\(1\)|"
                                 r"public announcement.{0,25}(acquisition|offer)|"
                                 r"manager to the offer|(post|pre)-? ?offer advertisement|"
                                 r"letter of offer.{0,30}(acquisition|open offer)"),
    ("Delisting",            64, r"\bdelist(ing|ed)?\b"),
    # A promoter buying or selling their own company's shares is news in its
    # own right - buying reads as confidence, selling as the opposite - but it
    # is NOT the company acquiring anything, which is what it used to be filed
    # as. 52 of 216 filings under Acquisition were a promoter dealing in shares.
    # See promoter_deal() below, which is what actually settles this: the words
    # here overlap Acquisition's, so points alone cannot separate them.
    ("Promoter Buy/Sell",    58, r"promoter.{0,40}(acquir|purchas|bought|sold|sell|"
                                 r"dispos|transferr?|gift|pledg|encumbr)|"
                                 r"(acquir|purchas|bought|sold|dispos|pledg).{0,40}"
                                 r"by (the )?promoter|"
                                 r"promoter group.{0,40}(stake|shares|holding)|"
                                 r"(creation|invocation|release) of (encumbrance|pledge)"),
    ("Stake Change",         50, r"\bsast\b|substantial acquisition of shares"),
    # Every tense of "acquire". The list used to hold "has acquired" and
    # "acquisition" but nothing in the future, so "ITC's subsidiary WILL
    # ACQUIRE a 22.1% stake in Happiest Minds" - which is how a deal is
    # announced on the day it is agreed, the day it is news - scored nothing at
    # all and came out Other(18).
    # The verb needs an object, or it is just English: "the auditor ACQUIRED an
    # understanding of the internal controls" scored 65 on the first attempt at
    # this. It has to be acquiring a stake, a percentage, a business, or a
    # named company.
    ("Acquisition",          65, r"\bacquisition\b|"
                                 r"acquir(e|es|ed|ing)\b[^.]{0,60}"
                                 r"(stake|shareholding|control of|\d[\d.]*\s?%|"
                                 r"per cent|business|undertaking|subsidiar|"
                                 r"private limited|\blimited\b|\bltd\b|\bllp\b|\binc\b)|"
                                 r"amalgamation|"
                                 r"\bmerger\b|slump sale|divestment|divestiture|stake sale|"
                                 r"sale of (the )?(subsidiary|business|undertaking|division)|"
                                 r"(enter\w*|form\w*|incorporat\w*|sign\w*|establish\w*|announc\w*) "
                                 r"[^.]{0,30}joint venture|"
                                 r"joint venture (agreement|with|company is|will be)|"
                                 # "Strategic partnership" and "strategic
                                 # investment" used to sit here bare, and they
                                 # are marketing words, not deals. Coforge
                                 # "expands strategic partnership with Pega" is
                                 # a commercial agreement to sell software
                                 # together, and Lloyds Enterprises' "Strategic
                                 # Investment Unit" is the NAME of a subsidiary
                                 # that was changing its name. Both were
                                 # published as acquisitions.
                                 #
                                 # A strategic investment is real news when it
                                 # says how much or how much of - so that is
                                 # what it now has to say.
                                 r"strategic investment[^.]{0,60}"
                                 r"(\d[\d.,]*\s?(%|per cent|crore|lakh|million|billion)|"
                                 r"stake|shareholding|equity)|"
                                 r"(acquisition|purchase) of[^.]{0,30}(stake|shareholding)|"
                                 r"share purchase agreement|\bspa\b executed"),

    # ---- raising money -------------------------------------------------------
    ("Qip Allotment",        63, r"qip allotment|allotment.{0,30}qualified institution|"
                                 r"allotment of (equity )?shares.{0,40}\bqip\b"),
    # Both spellings. SEBI's legal name for it is "Qualified Institutions
    # Placement"; every company and newspaper writes "institutional". Only the
    # first was listed, so a board approving a QIP in words rather than
    # initials scored nothing at all.
    ("Qip",                  62, r"\bqip\b|qualified institution(s|al)? placement"),
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
    # "fund raising" written forwards only. Half the filings say it backwards -
    # "raising of funds", "raise funds up to Rs 500 crore" - and those scored
    # nothing.
    ("Fund Raising",         58, r"fund ?rais|capital raising|further public offer|\bfpo\b|"
                                 r"rais(e|es|ed|ing) (of )?(funds|capital)|"
                                 r"raising of (funds|capital)|"
                                 r"issue of[^.]{0,30}(ncd|debenture|bond|commercial paper)|"
                                 # The quantity sits between the verb and the
                                 # instrument - "allotment of 30,000 non-
                                 # convertible debentures" - and the pattern
                                 # required them to be adjacent. CreditAccess
                                 # Grameen's Rs 300 crore debenture allotment
                                 # scored nothing here and was published as a
                                 # rights issue on the strength of its PDF.
                                 r"allotment of[^.]{0,30}(ncd|debenture|bond|convertible)|"
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
                                 r"(an? |the )?(orders?|contracts?|letter of award)|"
                                 # "Awarding of order(s)/contract(s)" is BSE's
                                 # own name for the order category, and this
                                 # said "award of", which does not match it.
                                 # Every filing the exchange itself labelled an
                                 # order scored 18/Other and then took whatever
                                 # tag its PDF happened to suggest - Ashoka
                                 # Buildcon's Letter of Acceptance from Rail
                                 # Vikas Nigam came out as a capacity increase.
                                 r"award(ing)? of (an? )?(order|contract)|"
                                 r"order win|bags? (an? )?order|"
                                 # ...and "letter of acceptance", which is what
                                 # the railways and most government bodies
                                 # actually send. Only intent and award were
                                 # listed.
                                 r"letter of (intent|award|acceptance)|\bloa\b|"
                                 r"\bloi\b|work order|purchase order|"
                                 r"contract (won|awarded|received|secured)|"
                                 # One adjective was enough to lose a Rs 100
                                 # crore order. Autoline Industries' press
                                 # release read "Secures PRESTIGIOUS Order Worth
                                 # Rs 100 Crores from Tata Motors Passenger
                                 # Vehicles" and the pattern was "secures? (an?
                                 # )?(order|contract|project)" - the verb and
                                 # its object had to be adjacent, with at most
                                 # an "a" between them. It scored 44 and never
                                 # reached the front page.
                                 #
                                 # Companies write these lines to be read, so
                                 # they are full of adjectives: prestigious,
                                 # significant, repeat, maiden, largest-ever.
                                 # The verb now just has to be in the same
                                 # sentence as its object.
                                 # Only the verbs that mean business. "Received"
                                 # is ordinary English - "the company received a
                                 # routine order from the registrar" - so it
                                 # keeps the tight form above and is not listed
                                 # here. Securing, bagging and winning an order
                                 # are not things that happen in a covering
                                 # letter.
                                 r"(secure[sd]?|securing|bag|bags|bagged|"
                                 r"win|wins|winning|\bwon\b|awarded)"
                                 r"[^.]{0,45}"
                                 r"(orders?|contracts?|work order|purchase order|"
                                 r"letter of (award|acceptance|intent)|tender|"
                                 r"\bproject\b|\bmandate\b)|"
                                 # "Business Order from Tata Motors Passenger
                                 # Vehicles Limited." - the whole headline, with
                                 # no verb at all.
                                 r"business order|export order|repeat order"),
    ("Dividend",             60, r"\bdividend\b"),
    # Pharma had no category at all, so a whole class of material news scored
    # nothing and stayed off the front page. Suven Life Sciences announced the
    # completion of patient enrollment in a global Phase-3 study of Masupirdine
    # for Alzheimer's agitation - a company-defining event - and it scored 0.
    #
    # Three separate things, because they move a share price in different
    # directions: permission to sell a drug, the trial that earns the
    # permission, and the inspection that can take it away.
    # Naming a regulator is NOT an approval. "USFDA" alone used to be listed
    # here, and it made "USFDA inspection concluded with five observations" -
    # which is bad news - score higher as a Product Approval than as the
    # inspection it plainly is. The regulator has to be granting something.
    ("Product Approval",     59, r"(final|tentative|marketing) approval|"
                                 r"marketing authoris|marketing authoriz|"
                                 r"drug master file|\bdmf\b filing|"
                                 r"\banda\b|abbreviated new drug|"
                                 r"\bnda\b (filing|approval|submission)|"
                                 r"(approv\w+|clearance|cleared|authoris\w+|"
                                 r"authoriz\w+|registration granted)"
                                 r"[^.]{0,45}"
                                 r"(drug|formulation|molecule|device|vaccine|"
                                 r"injection|tablet|capsule|generic|"
                                 r"\bapi\b|dossier)|"
                                 r"(usfda|\bfda\b|\bema\b|\bcdsco\b|\bmhra\b|"
                                 r"\banvisa\b|\btga\b)"
                                 r"[^.]{0,45}"
                                 r"(approv\w+|granted|clearance|cleared)|"
                                 r"product (launch|approval|registration)"),
    # Scored ABOVE Product Approval on purpose: a Form 483 mentions the
    # regulator and the product both, and it is the inspection that is the news.
    ("Plant Inspection",     63, r"form 483|establishment inspection report|"
                                 r"\beir\b received|warning letter|import alert|"
                                 r"(zero|no|nil) (483 )?observations?|"
                                 r"(usfda|\bfda\b|regulatory|gmp)[^.]{0,40}"
                                 r"(inspection|audit)|"
                                 r"(inspection|audit) of[^.]{0,45}"
                                 r"(facility|plant|unit|site)"),
    # "Phase" on its own is an ordinary English word - "Phase 2 of the plant
    # expansion has been commissioned" scored as a clinical trial on the first
    # attempt. It has to be a phase OF something medical.
    ("Clinical Trial",       59, r"phase[- ]?(1|2|3|i{1,3})\b[^.]{0,45}"
                                 r"(trial|stud|clinical|patient|dosing|"
                                 r"candidate|molecule|therapy)|"
                                 r"(trial|stud(y|ies)|clinical|patient)"
                                 r"[^.]{0,45}phase[- ]?(1|2|3|i{1,3})\b|"
                                 r"clinical (trial|study|data|programme|program)|"
                                 r"patient (enrol|enroll|recruit|dosing)|"
                                 r"topline (data|result)|"
                                 r"(primary|secondary) endpoint|"
                                 r"pivotal (study|trial)|"
                                 r"investigational new drug"),
    # "capex" alone used to be here. It is one word of ordinary business
    # English and it turns up in job descriptions - a filing announcing a new
    # President of Manufacturing scored 57 and was published as a capacity
    # expansion. It now has to be capex OF something, or a capex plan.
    ("Capacity Increase",    57, r"capacity (expansion|addition|augment|increase)|new plant|"
                                 r"greenfield|brownfield|commercial production|"
                                 # "commissioning of" only, so "the plant has
                                 # been commissioned" scored nothing at all.
                                 r"commissioning of|commissioned[^.]{0,30}"
                                 r"(plant|unit|facility|line|capacity|project)|"
                                 r"(plant|unit|facility|line|project)[^.]{0,30}"
                                 r"(has been |is now )?commissioned|"
                                 r"commencement of (production|operation)|"
                                 r"capex (plan|program|programme|of|outlay)|"
                                 r"capital expenditure of|"
                                 r"expansion (plan|project)|debottleneck"),
    # "guidance" alone used to be here, and it appears in any document that
    # mentions SEBI guidance or governance guidance - a chief general
    # manager's resignation letter scored 55 and was filed as a business
    # update. It now has to be guidance ABOUT something.
    ("Business Update",      55, r"monthly business update|business update|revenue update|"
                                 r"sales update|monthly sales|production (update|figures|volume)|"
                                 r"operational (update|data)|quarterly (business |pre-?)update|"
                                 r"key financial and operational|"
                                 r"(revenue|earnings|growth|margin|volume|sales) guidance|"
                                 r"guidance for (fy|q[1-4]|the )"),

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
    # The verb as well as the noun. This wanted "appointment of a chief
    # executive" and missed "has appointed Vivek Jetley as its new CEO", which
    # is how a summary says it and how half of all headlines say it. Hexaware's
    # new CEO was left sitting under Acquisition because of it.
    ("Change In Management", 51, r"change in (management|directorate|auditors)|"
                                 # The role first and the event second, which
                                 # is how a company writes a two-word headline:
                                 # "CFO Appointment", "Company Secretary
                                 # Resignation". Only the other word order was
                                 # listed, so ZF Commercial Vehicle Control
                                 # Systems' "CFO Appointment" scored 18/Other
                                 # and was published as a capacity increase
                                 # once its PDF had been read.
                                 r"(managing director|chief executive|\bceo\b|"
                                 r"chief financial|\bcfo\b|chief operating|\bcoo\b|"
                                 r"company secretary|whole[- ]time director|"
                                 r"\bkmp\b|chairman)\s+"
                                 r"(appointment|re-?appointment|resignation|"
                                 r"cessation|change|transition)|"
                                 r"(appointment|re-?appointment|appointed|"
                                 r"re-?appointed|elevat\w+|designat\w+)"
                                 r"[^.]{0,70}(managing director|"
                                 r"chief executive|\bceo\b|chief financial|\bcfo\b|chairman|"
                                 r"whole[- ]time director|statutory auditor|"
                                 r"company secretary|chief operating|\bcoo\b|"
                                 r"chief technology|\bcto\b|"
                                 r"(independent|executive|additional|woman|"
                                 r"non-?executive|nominee)[^.]{0,24}director|"
                                 # ...and a plain one. "Intimation for
                                 # appointment of Director" named no kind of
                                 # director, matched nothing, scored 18/Other,
                                 # and SATYA MicroCapital's new nominee
                                 # director was published as a Delisting once
                                 # the PDF had been read. An appointment verb
                                 # is already required within 70 characters,
                                 # which is what keeps this from matching every
                                 # mention of a board of directors.
                                 r"\bdirectors?\b|"
                                 r"cost accountant|internal auditor|"
                                 r"key managerial|"
                                 r"\bpresident\b|vice[- ]president|"
                                 r"head of|chief [a-z]+ officer)"),
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
    # "...this Board Meeting regarding the financial results for the quarter"
    # is a notice that results are coming, and the trading-window paragraph
    # that carries it appears in every one of them.
    ("Board Meeting", 41, r"board meeting.{0,60}(regarding|to consider|to approve)"
                          r"[^.]{0,40}(financial )?results|"
                          r"trading window.{0,80}board meeting|"
                          r"(intimation|notice|prior intimation) (of|for|regarding).{0,45}board meeting|"
                          r"board meeting (will be|is scheduled|to be held|shall be|has been scheduled|"
                          r"scheduled to be held)|"
                          r"meeting of the board of directors.{0,90}(will be held|is scheduled|"
                          r"shall be held|to consider and approve|to consider)"),
    # An AGM notice, recognised from the document rather than the category.
    # Physicswallah filed one under "General Updates", so nothing blocked it
    # from being read, and the notice carries a website breadcrumb reading
    # "investor-relations > Financial Results > Annual Report" - which was
    # enough to publish a meeting notice as Results.
    ("Meeting", 22, r"notice (is hereby given|of the [0-9]{1,3}(st|nd|rd|th))"
                    r"[^.]{0,80}annual general meeting|"
                    r"[0-9]{1,3}(st|nd|rd|th) annual general meeting (of|will|is)"),

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
    # An ORDER from a government is the opposite of an order from a customer,
    # and the exchanges file both under "Award of Order / Receipt of Order".
    #
    # MOIL's demand notice for unpaid water tax arrived under that heading and
    # was published as an order win. The old pattern wanted the word "tax"
    # before "demand" - "tax demand", "tax notice" - and this one reads "demand
    # notice ... for unpaid water tax", with the tax at the far end of the
    # sentence. So the shape is matched now, not just one word order.
    ("Legal/Reg", r"gst (demand|order|notice|liabilit)|demand order|"
                  r"(income )?tax (demand|notice|order|liabilit)|assessment order|"
                  r"demand notice|notice of demand|"
                  r"demand.{0,60}(unpaid|outstanding|arrears|dues)|"
                  r"adjudicat|show cause|order-?in-?appeal|"
                  r"penalt.{0,40}(imposed|levied|order)|(imposed|levied).{0,40}penalt|"
                  r"input tax credit|"
                  r"(recovery|garnishee|attachment) (notice|order)"),

    # "Receipt of Order" where the order is a permission, not a purchase.
    # Darjeeling Industries received government approval to shift its
    # registered office and was published as having won work.
    # Who the order came FROM settles it. A customer places an order; a
    # registrar, a ministry or a tribunal issues one. Both arrive under
    # "Receipt of Order".
    ("Legal/Reg", r"(order|approval|permission|sanction|no objection|\bnoc\b|"
                  r"direction|notice) (from|of|by|issued by) "
                  r"(the )?(government|ministry|registrar|regional director|"
                  r"central government|state government|reserve bank|\brbi\b|"
                  r"\bsebi\b|\bnclt\b|tribunal|court|commissioner|"
                  r"income tax|customs|excise|municipal)|"
                  r"(government|ministry|registrar|tribunal|court) "
                  r"(approval|order|sanction|direction)"),
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
    # A bare "Presentation" counts. BSE files these as "...has informed the
    # Exchange about Presentation", with nothing qualifying it, and the filing
    # then fell through to Investor Meet - eClerx's slide deck was published as
    # a meeting. This pattern only runs once a filing is already known to be
    # one of the three meeting kinds, so the loose word is safe here.
    ("Investor Presentation", r"investor presentation|analyst presentation|"
                              r"earnings presentation|corporate presentation|"
                              r"\bpresentations?\b"),
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

# ---------------------------------------------------------------------------
# 7. PROMOTER DEALING vs THE COMPANY ACQUIRING SOMETHING
#
# Both are written with the same verbs - acquired, purchased, sold, transferred
# - so points cannot separate them: "Acquisition" scores 65 and would always
# beat "Promoter Buy/Sell" at 58, which is why 52 filings about a promoter
# buying shares in his own company were published as corporate acquisitions.
#
# What separates them is WHO. A promoter or promoter-group entity dealing in
# the company's own shares is a promoter deal, however it is phrased. A company
# buying a stake in another company is an acquisition, even when a promoter is
# mentioned somewhere in the document.
# ---------------------------------------------------------------------------
_PROMOTER_ACTOR = re.compile(
    r"promoter|promotor|\bpac\b|person acting in concert", re.I)

_PROMOTER_DEAL = re.compile(
    r"(acquir|purchas|bought|sold|sell|dispos|transferr?|gift|pledg|encumbr)", re.I)

# A real corporate deal, which wins even when a promoter is named nearby.
_CORPORATE_DEAL = re.compile(
    r"acquisition of .{0,40}(private limited|pvt\.? ?ltd|limited|ltd\b|inc\b|"
    r"llp\b|business|undertaking|division|subsidiar)|"
    r"scheme of (arrangement|amalgamation|merger|demerger)|"
    r"slump sale|joint venture|share purchase agreement|"
    r"acquire[sd]? .{0,30}(stake|shareholding) in .{0,40}(limited|ltd|inc|llp)|"
    r"wholly[- ]owned subsidiary|"
    # A formal open offer is a real event with its own machinery - a public
    # announcement, a letter of offer, a committee of independent directors -
    # and it always names promoters, because they are who is being bought out.
    # Without this it would be mistaken for the promoters simply dealing.
    r"open offer|detailed public statement|letter of offer|"
    r"committee of independent directors|public announcement", re.I)


# Shares moving inside the promoter family, which is not a deal at all.
#
# A father gifting shares to his son, or a husband to his wife, is filed on the
# same SAST forms as a real acquisition and reads exactly like one: "acquired
# 40.94 lakh shares". No money changes hands, nobody has bought or sold
# anything, and it says nothing about the company. SEBI exempts it from the
# open offer rules for that reason, under Regulations 10(5) and 10(6).
#
# It was being published as an Open Offer - the literal opposite - because the
# summary explains the exemption and the words "open offer" are in the
# sentence. Jeyyam Global Foods and two Sanghvi Movers filings were all sitting
# under Open Offer on 3 September.
#
# It is not Promoter Buy/Sell either. That category exists because a promoter
# buying reads as confidence and selling reads as the opposite, and a gift
# between relatives carries neither signal.
# The blank SEBI form prints its own list of options:
#
#   "Mode of sale (e.g. open market / public issue / rights issue /
#    preferential allotment / inter-se transfer / encumbrance, etc.)"
#
# which contains the words this looks for and means nothing at all. It is the
# same template that once scattered stake disclosures across every category.
# Recognised by the company it keeps: no real filing lists four different modes
# of transfer in one breath.
_FORM_OPTION_LIST = re.compile(
    r"mode of (sale|acquisition|disposal)|"
    r"open market\s*/|/\s*inter-?\s?se transfer|"
    r"preferential allotment\s*/", re.I)

_INTERSE = re.compile(
    r"inter-?\s?se transfer|inter-?\s?se\b[^.]{0,30}promoter|"
    r"internal transfer[^.]{0,40}promoter|"
    r"regulation 10\(5\)|regulation 10\(6\)|reg\.? ?10\(5\)|reg\.? ?10\(6\)|"
    r"gift deed|by way of gift|as a gift\b|"
    r"transfer[^.]{0,60}(no consideration|without consideration)|"
    r"exempt(ed)? from[^.]{0,30}open offer", re.I)

INTERSE_SCORE = 45


def interse_transfer(text):
    """Shares moving within the promoter family - a gift, not a transaction."""
    if not text:
        return False
    # A formal open offer names its own machinery. "Exempt from an open offer"
    # does not, and that is the whole difference.
    if re.search(r"detailed public statement|letter of offer|"
                 r"committee of independent directors|"
                 r"manager to the offer|offer advertisement", text, re.I):
        return False
    # The blank form lists "inter-se transfer" among its options. Strip the
    # list before looking, so a genuine inter-se transfer described elsewhere
    # in the same document still counts.
    cleaned = _FORM_OPTION_LIST.sub(" ", text)
    cleaned = re.sub(r"\(e\.?g\.?[^)]{0,200}\)", " ", cleaned, flags=re.I)
    return bool(_INTERSE.search(cleaned))


def promoter_deal(text):
    """Is this a promoter dealing in their own company's shares?

    Requires both a promoter and a dealing verb, and yields to anything that
    reads as a real corporate transaction - a company can buy another company
    on a day its promoter also happened to buy shares.
    """
    if not text:
        return False
    # A gift inside the family is not a promoter buying or selling. Checked
    # first, because these carry every word this function looks for.
    if interse_transfer(text):
        return False
    if _CORPORATE_DEAL.search(text):
        return False
    return bool(_PROMOTER_ACTOR.search(text) and _PROMOTER_DEAL.search(text))


# Tags a promoter deal is allowed to take over from. Anything else - a buyback,
# a scheme, an open offer with a formal public announcement - keeps its label.
# Tags a promoter deal may take over. Open Offer and Rights Issue are here
# because a promoter transfer disclosed on a SAST form scores them off the
# form's own wording - "proposed transfer of shares within the promoter family"
# was published as an Open Offer. A genuine open offer is protected by
# _CORPORATE_DEAL above, which wins first.
_DEALING_TAGS = {"Acquisition", "Stake Change", "Promoter Buy/Sell", "Other",
                 "Open Offer", "Rights Issue", "Inter-se Transfer"}
PROMOTER_SCORE = 58


# ---------------------------------------------------------------------------
# 8. A GENERAL MEETING NOTICE IS ONE THING, WHEREVER IT ARRIVES
#
# An AGM notice carries the whole year with it - the accounts, the dividend
# resolution, the reappointment of auditors, the enabling resolution for a
# preferential issue or a QIP. Scored on any of that, one document was being
# filed under a dozen different headings: Pref, Qip, Warrants, Acquisition,
# Business Update, Nclt. It reads as a mess because it is one.
#
# So the notice wins outright. If the filing IS a general meeting notice, it is
# a Meeting, whatever else the paperwork mentions.
#
# The test is whether the filing IS the notice, not whether it MENTIONS a
# meeting. A dividend declared subject to approval at the AGM is a dividend -
# 152 of them say so - and demoting those would be a worse mistake than the one
# being fixed.
# ---------------------------------------------------------------------------
_MEETING_NOTICE_CAT = re.compile(
    r"\bagm\b|\begm\b|annual general meeting|extraordinary general meeting|"
    r"shareholders meeting|postal ballot", re.I)

# One name for the meeting, used everywhere below.
_GM = r"(annual general meeting|extraordinary general meeting|\bagm\b|\begm\b)"

_MEETING_NOTICE_TEXT = re.compile(
    # the document announcing itself
    r"notice (is hereby given|of the|of an?)[^.]{0,80}"
    r"(annual |extraordinary |general )*meeting|"
    r"[0-9]{1,3}(st|nd|rd|th) (annual general meeting|\bagm\b)|"
    # 40 characters was too tight for how these are actually written.
    # "Intimation under regulation 30 wrt to weblink for forthcoming AGM" puts
    # 51 characters between the two words and was not recognised, so the
    # filing kept the tag its PDF had given it - Dividend.
    #
    # Widening is safe because of the guard in pipeline.category_from_summary:
    # this only decides anything when the text names no substantive event, and
    # a dividend that mentions its approving AGM names one.
    r"(intimation|notice|convening|convened)[^.]{0,80}" + _GM + r"|"
    r"(has (scheduled|announced|convened|called)|will hold|to be held)"
    r"[^.]{0,60}" + _GM + r"|"
    r"schedule (of|for)[^.]{0,40}" + _GM + r"|"
    r"e-?voting[^.]{0,40}" + _GM + r"|"
    # A postal ballot is a vote with no meeting, so none of the wordings above
    # reach it - yet it fails in exactly the same way, because the notice
    # lists every resolution being put and gets tagged as whichever one scores
    # highest. "Notice of postal ballot seeking approval for the issue of
    # convertible warrants" came out as Warrants.
    r"postal ballot notice|notice[^.]{0,25}postal ballot|"
    r"postal ballot[^.]{0,60}(seeking|for) (the )?approval|"
    # Closing the register of members FOR THE PURPOSE OF the AGM. Rashtriya
    # Chemicals filed exactly that and it was published as a Dividend, because
    # the same notice sets the dividend record date and the summary says so.
    #
    # What it turns on is the purpose, which the filing states outright. A book
    # closure "for the purpose of AGM" is a meeting notice; one "for the
    # purpose of Dividend" is a dividend, and Sunteck Realty's stays one.
    # 220 characters, because the dates sit in between: "...will remain closed
    # from Saturday, September 19, 2026, to Friday, September 25, 2026 for
    # taking record of the Members of the Company for the purpose of AGM" puts
    # 175 of them between the two halves.
    r"(register of members|share transfer books?|book closure|closure of "
    r"(the )?register)[^.]{0,220}(for the purpose of|in connection with|"
    r"for)[^.]{0,25}" + _GM, re.I)

MEETING_NOTICE_SCORE = 22


def meeting_notice(category, headline, body=""):
    """Is this filing itself a notice of a general meeting?"""
    if _MEETING_NOTICE_CAT.search(category or ""):
        return True
    return bool(_MEETING_NOTICE_TEXT.search((headline or "") + " " + (body or "")))


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


# Categories that name the event exactly, where the headline may not overrule.
#
# "Company Update / Appointment of Statutory Auditor/s" says what the filing
# is. The letter announcing the appointment carries the audit firm's profile,
# and one of those listed "Merger & Acquisition" among its services - enough
# for the headline branch below to lift a routine appointment to Acquisition,
# which is the single most visible category on the site.
#
# For these, the category decides and the headline can only add points to the
# category's own verdict, never replace it. Vague categories are unaffected:
# that is what VAGUE is for.
SPECIFIC_CATEGORY = re.compile(
    r"appointment of|resignation of|change in (director|management|auditor)|"
    r"\bcessation\b|(statutory|internal|secretarial|cost) auditor|"
    r"annual general meeting|\bagm\b|\begm\b|shareholders meeting|"
    r"postal ballot|annual report|newspaper publication|trading window|"
    r"book closure|record date", re.I)


def score(category, headline, critical=False):
    """Return (score 0-100, tag)."""
    category = (category or "").strip()
    headline = (headline or "").strip()

    if any(rx.search(category) or rx.search(headline) for rx in _JUNK_RE):
        return 3, "Routine"

    cat_pts, cat_tag, _ = _best(category)
    head_pts, head_tag, head_n = _best(headline)
    # A specific suffix beats a vague prefix. VAGUE holds "^company update",
    # which swallowed every "Company Update / ..." category - including
    # "Company Update / Appointment of Statutory Auditor/s", which says exactly
    # what the filing is. Treated as vague, its headline got a full vote, and
    # the audit firm's own list of services ("Merger & Acquisition") renamed a
    # routine appointment as a deal.
    specific = bool(category) and bool(SPECIFIC_CATEGORY.search(category))
    vague = (not category
             or (any(rx.search(category) for rx in _VAGUE_RE) and not specific))

    if vague:
        # Category tells us nothing useful - the headline decides.
        pts, tag = (head_pts, head_tag) if head_pts >= cat_pts else (cat_pts, cat_tag)
    elif specific:
        # The category already names the event. The headline can raise the
        # score - a resignation of a chief executive is bigger news than a
        # resignation of an internal auditor - but it cannot rename the filing.
        pts, tag = cat_pts, cat_tag
        if head_pts - 8 > pts:
            pts = head_pts - 8
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
        # A promoter deal is recognised by its actor rather than by a topic
        # pattern, so it has to be asked about here too. "Internal transfer of
        # shares between members of the promoter group" matches no topic at
        # all and would otherwise leave as Other(18).
        if interse_transfer(category + " || " + headline):
            return INTERSE_SCORE, "Inter-se Transfer"
        if promoter_deal(category + " || " + headline):
            return PROMOTER_SCORE, "Promoter Buy/Sell"
        # Same for a meeting notice. "Convening of the Extraordinary General
        # Meeting on 20 September" matches no topic either, and would have left
        # here as Other while its neighbours were correctly called Meeting.
        if meeting_notice(category, headline):
            return MEETING_NOTICE_SCORE, "Meeting"
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

    # A promoter dealing in their own shares is not the company acquiring
    # anything. See section 7 - points cannot separate these, only the actor.
    if tag in _DEALING_TAGS and interse_transfer(both):
        tag, pts = "Inter-se Transfer", INTERSE_SCORE
    elif tag in _DEALING_TAGS and promoter_deal(both):
        tag, pts = "Promoter Buy/Sell", PROMOTER_SCORE

    # Correct the label where the category word is misleading. Score stands -
    # a tax demand is just as worth reading as an order win, it's not the same
    # kind of news.
    for r_tag, rx in _RETAG_RE:
        if rx.search(both):
            tag = r_tag
            break

    # And a general meeting notice is a Meeting, whatever its annexures say.
    if meeting_notice(category, headline):
        return MEETING_NOTICE_SCORE, "Meeting"

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
        # A meeting notice matches no topic at all - it is not an event, it is
        # an invitation to one - so it left here as nothing and whatever tag the
        # filing already carried survived. The same early return that swallowed
        # promoter deals and meeting notices in score().
        if meeting_notice("", "", body):
            return MEETING_NOTICE_SCORE, "Meeting"
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

    if tag in _DEALING_TAGS and interse_transfer(body):
        tag, pts = "Inter-se Transfer", INTERSE_SCORE
    elif tag in _DEALING_TAGS and promoter_deal(body):
        tag, pts = "Promoter Buy/Sell", PROMOTER_SCORE

    for r_tag, rx in _RETAG_RE:
        if rx.search(body):
            tag = r_tag
            break

    # A general meeting notice is a Meeting here too. This override was added
    # to score() and not to this function, which is the one that reads the PDF
    # and the summary - so an AGM notice carrying an enabling resolution for a
    # preferential issue went on being filed as Pref. Eight of the twenty-three
    # filings under Pref were general meeting notices.
    # This used to sit here unconditionally, and it was too strong: it beat a
    # real event merely because the text also mentioned the meeting that will
    # approve it. Sunteck Realty's dividend record date, Gujarat Intrux's, and
    # Foseco's approved final dividend all became "Meeting" on 3 September.
    #
    # A notice only wins when it is ALL there is - which is the check at the
    # top of this function, where nothing matched at all. If the text names an
    # event of its own, that event is the news and the meeting is context.

    pts = min(pts, 100)
    return (pts, tag) if pts >= floor else (0, None)

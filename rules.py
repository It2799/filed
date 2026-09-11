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
    r"regulation 18\(i\)|daily report.{0,50}(buy-?\s?back|bought back)|"
    r"daily buy-?\s?back|buy-?\s?back.{0,20}on a daily basis|"
    r"daily disclosure.{0,100}(buy-?\s?back|bought back|shares bought back)|"
    r"buy-?\s?back.{0,30}daily (report|disclosure)|"
    r"closure of (the )?buy-?\s?back offer",
    # A partly-paid rights issue is followed by notices asking holders for the
    # next instalment. Housekeeping, not an issue.
    r"call money|reminder notice.{0,50}\bcall\b",
    # Depository plumbing: the date a company's shares became transferable at
    # CDSL or NSDL.
    r"date of connectivity|connectivity (informed|intimated) by",
    # A bill. Prakash Steelage filed the invoice from the agent who made its
    # SAST filings - Rs 1.77 lakh, taxable Rs 1.5 lakh, GST Rs 13,500 - and it
    # was published as an Acquisition, because the invoice describes what it
    # was for. The company's own purchase ledger is not news.
    r"\binvoice\b|tax invoice|debit note|credit note|"
    r"taxable (amount|value)[^.]{0,30}\bgst\b|"
    r"(filing|professional|consultancy|service) (fees|charges)[^.]{0,30}"
    r"(invoice|payable|paid)",
    # Changing the registrar. The letter is addressed to shareholders and
    # recites every class of security the registrar will handle, so S&S Power
    # Switchgear's "Change in RTA" was published under Warrants at 61.
    r"change (in|of) \brta\b|change (in|of) registrar|"
    r"registrar and (share )?transfer agent|\brta\b (change|transition)|"
    r"appointment of (the )?registrar",
    # A mutual fund's own paperwork - portfolio statements, net asset values,
    # expense ratios - which BSE carries alongside company announcements. A
    # fortnightly portfolio lists every instrument the fund holds, so reading
    # one finds several hundred company names and every kind of security there
    # is: Choice Gold ETF's was published as a Rights Issue.
    #
    # "Scheme" is their word for a fund, which is also how a mutual fund ends
    # up in Scheme Of Arrangement.
    r"fortnightly portfolio|monthly portfolio|portfolio (statement|disclosure)|"
    r"net asset value|\bnav\b\s*(as on|as of|as at|of the scheme|[0-9])|"
    r"(total )?expense ratio|scheme information document|"
    r"scheme of[^.]{0,30}mutual fund",
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
    r"payment of interest on[^.]{0,40}(non-?convertible|debenture|\bncds?\b)|"
    r"certificate[^.]{0,40}payment of interest|"
    r"interest payment[^.]{0,20}(certificate|intimation)|"
    # "interest PAYMENTS ON its listed non-convertible debentures" - the same
    # thing said the other way round, which the line above does not reach
    # because it wants "payment OF interest on". Summit Digitel's record date
    # for NCD interest was published as Fund Raising: the attachment recites
    # the debenture issue, and "issue of debentures" is a fund raise.
    r"interest payments? on[^.]{0,50}"
    r"(non-?convertible|debenture|\bncds?\b|\bbond)|"
    # A record date for interest, or for redeeming an instrument, is debt
    # servicing. A record date for a dividend, bonus or split is not, and is
    # deliberately not matched here.
    r"record date[^.]{0,80}(interest|coupon|redemption|redeem)|"
    r"(interest|coupon)[^.]{0,60}record date|"
    # ...and every other way a company says "we paid the interest and repaid
    # the principal on the due date". Sixteen of the twenty-nine filings under
    # Buyback were these: REC, Power Finance, Exim Bank, L&T Finance, National
    # Housing Bank, a Vadodara Municipal Corporation green bond coupon. A
    # redemption is the borrower giving the money back, which reads like the
    # company buying its securities in - and none of it is news. There is one
    # per instrument per due date, and since NSE's debt list started being
    # fetched there are dozens a day.
    r"confirmation of (redemption|payment|interest)|"
    r"redemption of[^.]{0,50}(\bncds?\b|debenture|commercial paper|\bbond|"
    r"\bncrps\b|\bcp\b)|"
    r"repayment of[^.]{0,40}(commercial paper|\bncds?\b|debenture|\bbond)|"
    r"payment towards interest|interest and princip|princip\w+ and interest|"
    r"coupon payment|payment of (the )?coupon|"
    r"certificate of interest|"
    r"(intimation|disclosure) (of|for|regarding) (the )?"
    r"(payment|repayment|redemption)[^.]{0,40}"
    r"(interest|princip|commercial paper|\bncds?\b|debenture|\bbond)",
    # A bare "<something> for the quarter ended <date>" heading is compliance
    # paperwork - but only when the something is not the results themselves.
    # Without the guard, whether a company's quarterly results survive came
    # down to how the date was punctuated: "quarter ended 30.6.2025" is 9
    # characters and was junked, "30.06.2025" is 10 and got through.
    r"^(?!.*\b(results?|earnings|outcome)\b).*\bfor the quarter ended.{0,10}$",
    # SEBI opened a special window for shareholders to re-lodge physical
    # share transfer requests, and every company files a monthly report
    # on it whether or not anybody used the window - Hisar Spinning
    # Mills' report says the registrar received none. Five were live on
    # 8 September and all five were published as Clinical Trials, on
    # "trans" and a stray "phase" somewhere in the attachment.
    r"re-?lodg(e|ing|ement|ment)",
    r"special window[^.]{0,40}(physical|re-?lodg|transfer)",
    # Unclaimed shares moving to the demat suspense account, and the
    # letters chasing shareholders about them, are the same paperwork.
    r"(demat|unclaimed) suspense (escrow )?account",
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
    # "bought back" is how a company describes the thing after it has done it,
    # and it matched nothing: Man Infraconstruction "bought back 7,09,145
    # equity shares from the open market" was published as an Acquisition.
    ("Buyback",              70, r"buy-?\s?back|(bought|buying|purchas\w+) back|"
                                 r"shares bought back"),
    # An amalgamation IS a scheme, whether or not the filing writes the words
    # "scheme of" in front of it. Only the long form was listed, so Warren Tea
    # announcing that "the NCLT has reserved the final order for its proposed
    # amalgamation" fell through to Acquisition, which had bare "amalgamation"
    # in its own list and scores four points lower.
    ("Scheme Of Arrangement", 69, r"scheme of (arrangement|amalgamation|merger|demerger)|"
                                 r"composite scheme|de-?merger|\bdemerge|"
                                 r"\bamalgamat\w+"),
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
    # The bare word "acquisition" does not win when what is being acquired is
    # a thing rather than a company. "In-principle approval for the
    # acquisition of land for about Rs 50 crore" is a capacity increase, and
    # it outranked one at 65 to 57 on this word alone.
    # The bare word "acquisition", except where it is not an event at all.
    #
    # Not when what is being acquired is a thing rather than a company:
    # "in-principle approval for the acquisition of land" is a capacity
    # increase, and it outranked one at 65 to 57 on this word alone.
    #
    # And not when it is part of the NAME of the takeover regulations. SEBI
    # (Substantial Acquisition of Shares and Takeovers) Regulations, 2011 is a
    # title, and it appears in every disclosure filed under it. Prakash
    # Steelage's invoice from the agent who filed one - Rs 1.77 lakh, GST
    # Rs 13,500 - was published as an Acquisition on that phrase, with "it
    # signals an insider is acquiring shares" written underneath.
    ("Acquisition",          65, r"(?<!substantial )\bacquisition\b"
                                 r"(?! of shares and takeover)"
                                 r"(?![^.]{0,40}\b(land|plant|"
                                 r"machinery|equipment|aircraft|vessel|"
                                 r"property|premises|building)\b)|"
                                 r"acquir(e|es|ed|ing)\b[^.]{0,60}"
                                 r"(stake|shareholding|control of|\d[\d.]*\s?%|"
                                 r"per cent|business|undertaking|subsidiar|"
                                 r"private limited|\blimited\b|\bltd\b|\bllp\b|\binc\b)|"
                                 r"amalgamation|"
                                 r"\bmerger\b|slump sale|stake sale|"
                                 # Selling is as much a deal as buying. On 8 September three
                                 # divestments were tagged by whatever else their summary
                                 # happened to mention, because only the noun was listed here:
                                 # "divestment" matched, "divested its entire stake" did not,
                                 # and neither did "sale of the investment in Credo". Elgi
                                 # Equipments and Gujarat Apollo went to Scheme Of Arrangement,
                                 # Sanginita to New Subsidiary.
                                 r"divest(s|ed|ing|ment|iture)\b|"
                                 r"sale of (the )?(subsidiary|business|undertaking|division)|"
                                 r"sal(e|es) of[^.]{0,40}"
                                 r"\b(stake|shareholding|investment|equity stake)\b|"
                                 r"sold[^.]{0,40}"
                                 r"\b(stake|shareholding|entire (investment|holding))\b|"
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
                                 r"share purchase agreement|\bspa\b executed|"
                                 # Two real deals lived only in the evidence
                                 # list and not here, so tightening the check
                                 # to this pattern demoted them: International
                                 # Gemological "will consolidate control over
                                 # IGI Botswana", and NLC India's addendum to
                                 # "transfer about 709 MW of renewable assets".
                                 # Both are acquisitions; this is where that
                                 # belongs.
                                 r"consolidat\w+ control|acquir\w+ control\b|"
                                 r"transfer\w*[^.]{0,40}\b(assets|undertaking|"
                                 r"megawatt|\bmw\b)\b"),

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
                                 r"exercise) of[^.]{0,30}warrants?|"
                                 # "of" is optional here too, and the quantity
                                 # sits in between: "is issuing 60.82 lakh
                                 # warrants to its promoters at Rs 475 per
                                 # warrant" matched nothing at all.
                                 # "of" is optional here too, and the quantity
                                 # sits in between: "is issuing 60.82 lakh
                                 # warrants to its promoters" matched nothing.
                                 #
                                 # The verb has to come FIRST. "Search warrant
                                 # issued by the Income Tax Department" is a
                                 # raid, and an earlier attempt at this made it
                                 # a securities issue - which is why the
                                 # pattern was tight in the first place.
                                 # .{0,30} and not [^.]{0,30}: the quantity in
                                 # between is "60.82 lakh", and a full stop
                                 # class stops dead on the decimal point.
                                 r"(issu|allot|convert|subscrib)\w*"
                                 r".{0,30}\bwarrants?\b|"
                                 r"\bwarrants? (issue\b|price|per warrant)"),
    # The paperwork AFTER an issue, not the issue.
    #
    # An exchange approving the listing or trading of shares already allotted
    # is a formality that arrives days later, and it recites the issue it
    # relates to - so six of the twenty filings under Pref were one of these:
    # Pakka, Fonebox, Tejassvi Aaharam, Vaishali Pharma, Scan Steels and
    # Porwal Auto. The issue itself was announced separately and is found on
    # its own.
    #
    # Above Pref at 61 so it wins the filing it describes, and below the
    # important line at 55 would hide it entirely - a reader watching a
    # preferential issue does want to know when the shares start trading, just
    # not filed as the issue. So it sits just under the deal categories.
    ("Listing Approval",     52, r"(listing|trading) approval|"
                                 r"approval for (listing|trading)|"
                                 r"in-?principle approval[^.]{0,70}"
                                 r"(listing|issue|allot)|"
                                 r"listed and admitted to dealings|"
                                 r"(admitted to|permitted for) (dealings|trading)"),
    ("Pref",                 60, r"preferential (issue|allotment|basis)|on a preferential"),
    # "fund raising" written forwards only. Half the filings say it backwards -
    # "raising of funds", "raise funds up to Rs 500 crore" - and those scored
    # nothing.
    ("Fund Raising",         58, r"fund ?rais|capital raising|further public offer|\bfpo\b|"
                                 r"rais(e|es|ed|ing) (of )?(funds|capital)|"
                                 r"raising of (funds|capital)|"
                                 # "raising up to INR 1,000 crore", which
                                 # names an amount instead of the word "funds"
                                 # - the only wording accepted before. A
                                 # borrowing committee's Rs 1,000 crore NCD
                                 # approval and Canara Bank's USD 2,000 million
                                 # bond programme both scored zero, and reached
                                 # the site only because the exchange category
                                 # happened to say Fund Raising. Described in a
                                 # PDF under a vague category, they were lost.
                                 # An amount alone is not enough. "Revenue
                                 # guidance raised to Rs 500 crore" is a
                                 # business update, and the first version of
                                 # this made it a fund raise at 58 - a figure
                                 # being revised upwards read as money being
                                 # brought in. So the sentence has to name what
                                 # is being raised as well.
                                 # ...and what is being raised has to be the money,
                                 # not a shareholding. A stake disclosure reads
                                 # "raising his holding to 46,82,622 shares (6.169%
                                 # of VOTING CAPITAL)", and capital is on the list
                                 # below, so a promoter buying 9,481 shares of W.S.
                                 # Industries was published as a fund raise, as was
                                 # JM Financial ARC buying 3% of Alok Industries.
                                 r"rais(e|es|ed|ing)(?![^.]{0,40}\b(holding|stake|"
                                 r"shareholding|voting capital|paid-?up)\b)[^.]{0,60}"
                                 r"(funds|capital|equity|\bdebt\b|\bncds?\b|"
                                 r"debenture|\bbonds?\b|commercial paper|"
                                 r"private placement|borrowing)|"
                                 # "by ISSUING listed, rated, secured,
                                 # redeemable non-convertible debentures" -
                                 # every adjective in that list was inside a
                                 # 30-character window that had to reach the
                                 # word "debenture".
                                 r"issu(e|es|ed|ing|ance)( of)?[^.]{0,60}"
                                 r"(\bncds?\b|debenture|\bbonds?\b|"
                                 r"commercial paper)|"
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
    # "of" is optional. "Receipt of order" and "received an order" are the
    # same news; only the first was matched, so a press release saying the
    # company "received an order worth Rs 120 crore" scored nothing.
    ("Order",                62, r"bagging|(receipt|receiving|received)( of)? "
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
    # A partnership is not an acquisition and it is not nothing.
    #
    # "Strategic partnership" used to sit inside Acquisition, which was wrong -
    # Coforge expanding a reselling agreement with Pega is not a takeover - so
    # it was taken out on 3 September. That left no home for it at all, and the
    # next day Balaji Telefilms announced a partnership with YouTube for five
    # original shows across 200 episodes and scored 44, below the line, on
    # neither page. Removing the wrong answer without building the right one.
    #
    # Kept below the deal categories: a partnership is real news and it is not
    # a change of ownership.
    ("Partnership",          56, r"strategic (partnership|alliance|tie-?up|"
                                 r"collaboration)|"
                                 r"partner(s|ed|ing)? with\b|"
                                 r"partnership with\b|"
                                 r"(signs?|signed|enters? into|entered into|"
                                 r"executed)[^.]{0,50}"
                                 r"(memorandum of understanding|\bmou\b|"
                                 r"collaboration agreement|partnership agreement|"
                                 r"distribution agreement|licen[sc]ing agreement|"
                                 r"technology transfer|definitive agreement)|"
                                 r"\bmou\b with\b|joint development agreement"),
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
                                 # Buying an asset is not buying a company.
                                 # Afcom Holdings' letter of intent with Boeing
                                 # for four 777-8F aircraft, and Innova Captab
                                 # buying land for Rs 50 crore, were both
                                 # published as Acquisitions.
                                 r"(purchase|acquisition|buy|buying|acquire) "
                                 r"(of |up to |about )?[^.]{0,40}"
                                 r"(land|plant|machinery|equipment|aircraft|"
                                 r"vessel|property|building|premises|"
                                 r"manufacturing facility)|"
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
                                 r"re-?appointed|appoint(s|ing)?|re-?appoint(s|ing)?|"
                                 r"elevat\w+|designat\w+)"
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
                                 r"manager of the (company|firm)|"
                                 r"key managerial|"
                                 r"\bpresident\b|vice[- ]president|"
                                 r"head of|chief [a-z]+ officer)"),
    ("Resignation",          40, r"resignation|cessation|removal|retirement of|"
                                 r"stepped down|relinquish|"
                                 # Maxvolt Energy's chairman was "due to retire by
                                 # rotation", which names the role BEFORE the verb, so
                                 # the windowed appointment pattern could not see it
                                 # and the filing scored nothing at all.
                                 r"retire(s|ment|ing)? by rotation"),

    # ---- meetings and talk ---------------------------------------------------
    # These three used to share one "Concall" tag scored at 45, which put them
    # below the bar for Important - so a reader could not filter for them at
    # all. They are what an investor actually plans a week around, so each is
    # now its own category and each clears the bar on its own.
    # 57 against Investor Meet's 55, so a passing MENTION of a
    # presentation beat the meeting a filing was actually about, by two
    # points. Home First Finance announced "its schedule for upcoming
    # analyst and institutional investor meetings, including non-deal
    # roadshows in the UK", and added that officials "will use ALREADY
    # PUBLIC investor presentations during these discussions" - so a
    # meeting schedule was published as a presentation, as were Ashok
    # Leyland's and Tips Music's.
    #
    # A presentation filing attaches a presentation. That is what tells
    # the two apart, and it was never a question of points.
    ("Investor Presentation", 57,
                                  r"(attach\w+|enclos\w+|submit\w+|upload\w+|shar\w+|"
                                  r"releas\w+|publish\w+|post(ed|ing)?|herewith|copy of|"
                                  r"made available)[^.]{0,50}"
                                  r"(investor|analyst|earnings|corporate) presentation|"
                                  r"(investor|analyst|earnings|corporate) presentation[^.]{0,50}"
                                  r"(attached|enclosed|submitted|uploaded|herewith|"
                                  r"is (being )?shared|available on the|on the website)"),
    ("Concall",              56, r"con\.? ?call|conference call|earnings call|"
                                 r"audio recording|video recording|transcript"),
    ("Investor Meet",        55, r"analysts?.{0,14}meet|institutional investor meet|"
                                 # The same words the other way round:
                                 # "a one-on-one meeting WITH analysts
                                 # and institutional investors".
                                 r"meet(ing)?s?\s+(with|of)\s+(the\s+)?"
                                 r"(analyst|investor|institutional|fund manager)|"
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
                  # A fine is a penalty by another name, and "imposing a fine
                  # of Rs 1,60,000" said neither of the words above.
                  r"(imposing|imposed|levying|levied)[^.]{0,40}fine|"
                  r"fine of (rs|inr|₹)\.? ?\d|"
                  r"input tax credit|"
                  r"(recovery|garnishee|attachment) (notice|order)"),

    # "Receipt of Order" where the order is a permission, not a purchase.
    # Darjeeling Industries received government approval to shift its
    # registered office and was published as having won work.
    # Who the order came FROM settles it. A customer places an order; a
    # registrar, a ministry or a tribunal issues one. Both arrive under
    # "Receipt of Order".
    # An order that IMPOSES something is never a customer order, whoever
    # it names and whichever way round it is said. This is the reliable
    # half of the question: a customer places an order, it does not levy
    # a penalty or demand a duty.
    ("Legal/Reg", r"(impos\w+|levy|levied|demand\w*|recover\w*)"
                  r"[^.]{0,40}(penalt|\bfine\b|fine of|interest|tax|"
                  r"duty|\bgst\b|\bigst\b|excise)|"
                  r"order-in-(original|appeal|revision)|"
                  # "an IRDAI order" - the regulator named first.
                  r"(\bsebi\b|\brbi\b|\birdai?\b|\btrai\b|\bcci\b|"
                  r"\bdgft\b|\bpfrda\b|\bnclt\b|\bnclat\b|tribunal|"
                  r"customs|excise|income tax|commissioner|magistrate|"
                  r"collector|ministry|registrar|adjudicating officer)"
                  r"[^.]{0,30}\border\b"),
    ("Legal/Reg", r"(order|approval|permission|sanction|no objection|\bnoc\b|"
                  r"direction|notice) (from|of|by|issued by) "
                  r"(the )?(government|ministry|registrar|regional director|"
                  r"central government|state government|reserve bank|\brbi\b|"
                  r"\bsebi\b|\bnclt\b|tribunal|court|commissioner|"
                  r"income tax|customs|excise|municipal|"
                  # Restaurant Brands Asia "received an order from the
                  # Additional District Magistrate in Agra under the Food
                  # Safety and Standards Act, imposing a fine of Rs 1,60,000"
                  # was published as an order win. A magistrate does not place
                  # orders with caterers.
                  r"magistrate|collector|district (authority|administration)|"
                  r"police|labour|pollution control|\bfssai\b|food safety|"
                  r"drug controller|\bcdsco\b|enforcement directorate|"
                  r"\bnclat\b|high court|supreme court|arbitral)|"
                  r"(government|ministry|registrar|tribunal|court) "
                  r"(approval|order|sanction|direction)|"
                  r"legal dispute|litigation|recovery suit|"
                  r"court.{0,35}(dismiss|adjourn|hear|appeal|order|stay)|"
                  r"tribunal.{0,35}(issued|passed|order|appeal)|"
                  r"securities appellate tribunal|case with sebi|appeal filed"),
]

_JUNK_RE = [re.compile(p, re.I) for p in JUNK]
_DOWN_RE = [(tag, cap, re.compile(p, re.I)) for tag, cap, p in DOWNGRADE]
_RETAG_RE = [(tag, re.compile(p, re.I)) for tag, p in RETAG]
_VAGUE_RE = [re.compile(p, re.I) for p in VAGUE]
_TOPIC_RE = [(tag, pts, re.compile(p, re.I)) for tag, pts, p in TOPICS]

# What each tag is worth, so a filing relabelled off its AI summary can take
# the new tag's score with it.
#
# This exists for the press releases. A company files one under the category
# "Press Release" with the headline "Please refer attached file", which scores
# 44 - below the 55 needed to be shown, and below the 55 needed to be
# SUMMARISED, so nothing ever asked what the release said. Balaji Telefilms
# filed on both exchanges on 4 September and appeared on neither page.
#
# Highest wins where a tag appears twice in TOPICS, which is how a couple of
# them are written.
SCORE_FOR_TAG = {}
for _tag, _pts, _ in TOPICS:
    SCORE_FOR_TAG[_tag] = max(SCORE_FOR_TAG.get(_tag, 0), _pts)


# A company issues a press release because it wants the news noticed, so the
# document is worth reading even when the headline says nothing at all.
PRESS_RELEASE_CAT = re.compile(r"press release|media release", re.I)


def is_press_release(category):
    return bool(PRESS_RELEASE_CAT.search(category or ""))


# Tags that are not an answer. Each one means the headline said nothing AND the
# topic patterns found nothing in the document either - which is the exact
# situation where a person would open the PDF and read it.
#
# Filings wearing one of these get an AI summary whatever they score, and the
# summary is then allowed to name the event and promote the filing to what that
# event is worth. There are about fifteen a day, so it costs almost nothing.
#
# "Corp Action" is here because a record date names no action: the document is
# the only thing that says whether it is a dividend, a bonus or a split.
# "Unusual" is the exchange asking a company to explain a price move, and what
# it is explaining is in the reply.
UNDECIDED = {"Other", "Outcome", "Press Release", "Board Meeting",
             "Corp Action", "Unusual"}


def undecided(tag):
    return tag in UNDECIDED

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
    # A presentation filing ATTACHES a presentation, and this list is
    # first-match-wins, so the qualified form has to come before the meet.
    # Home First Finance announced its "schedule for upcoming analyst and
    # institutional investor meetings, including non-deal roadshows in the
    # UK" and mentioned only that officials "will use already public investor
    # presentations" - which was enough to publish a meeting schedule as a
    # presentation while this entry led the list unqualified.
    ("Investor Presentation", r"(attach\w+|enclos\w+|submit\w+|upload\w+|"
                              r"shar\w+|releas\w+|publish\w+|herewith|"
                              r"copy of|made available)[^.]{0,50}"
                              r"(investor|analyst|earnings|corporate) "
                              r"presentation|"
                              r"(investor|analyst|earnings|corporate) "
                              r"presentation[^.]{0,50}"
                              r"(attached|enclosed|submitted|uploaded|"
                              r"herewith|is (being )?shared|"
                              r"available on the|on the website)"),
    ("Concall",               r"con\.? ?call|conference call|earnings call|"
                              r"audio recording|video recording|transcript"),
    ("Investor Meet",         r"analysts?.{0,14}meet|institutional investor meet|"
                              r"investor meet|road ?show|non-?deal roadshow|"
                              # "a one-on-one meeting WITH analysts and
                              # institutional investors" - Tips Music, and the
                              # same words in the other order.
                              r"meet(ing)?s?\s+(with|of)\s+"
                              r"(the\s+)?(analyst|investor|institutional|"
                              r"fund manager)"),
    # Last, and only for the filings nothing above explains: BSE's bare
    # "Presentation" category, where eClerx's slide deck came from.
    ("Investor Presentation", r"\bpresentations?\b"),
]
_MEETING_RE = [(tag, re.compile(p, re.I)) for tag, p in MEETING_KINDS]
_MEETING_TAGS = {tag for tag, _ in MEETING_KINDS}
# The score each kind carries, kept in step with TOPICS above so a concall out
# of BSE's shared bucket ranks the same as one filed under a clear heading.
MEETING_SCORE = {"Investor Presentation": 57, "Concall": 56, "Investor Meet": 55}

# The three meeting kinds and the promoter/notice tags are scored by their own
# constants rather than by a topic pattern, so they have to be added by hand.
SCORE_FOR_TAG.update(MEETING_SCORE)

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

# "sold" and "sell" were listed; "sale" was not. Nila Spaces' promoter
# "disclosed an open-market sale of 1,000,000 shares" matched no verb at all,
# so the filing was not recognised as a promoter dealing and its summary
# relabelled it an Acquisition.
_PROMOTER_DEAL = re.compile(
    r"(acquir|purchas|bought|sold|sell|sale|dispos|divest|"
    # a word-bounded buy/buys/buying, not bare "buy", so that a buyback filing mentioning
    # promoters is not read as one of them dealing.
    r"\bbuy(s|ing)?\b|"
    r"transferr?|gift|pledg|encumbr|subscrib)", re.I)

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
SCORE_FOR_TAG["Inter-se Transfer"] = INTERSE_SCORE


# An issue CREATES shares; an inter-se transfer MOVES them. Both mention the
# open-offer exemption, which is what this rule keys on, so Shah Foods'
# preferential issue of warrants to its promoters came out as an inter-se
# transfer once the open-offer reading was taken away from it.
_FRESH_ISSUE = re.compile(
    r"preferential (issue|allotment)|"
    r"(issue|issuing|issuance|allot\w+) of[^.]{0,40}"
    r"(warrant|equity share|new share|convertible)|"
    r"rights issue|\bqip\b|private placement of|"
    r"increase[^.]{0,30}(authorised|authorized) share capital", re.I)


def interse_transfer(text):
    """Shares moving within the promoter family - a gift, not a transaction."""
    if not text:
        return False
    # New securities being created is not existing ones changing hands.
    if _FRESH_ISSUE.search(text):
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


# Setting a company up is not buying one.
#
# 15 of the 144 filings under Acquisition were a company incorporating a
# subsidiary - Bondada Engineering, Brigade Enterprises, Fineotex, Kalpataru,
# Aurobindo, Dhanuka in Ireland, Craftsman in Germany. Nothing was bought and
# no money changed hands with anyone; the company registered a new entity,
# usually to enter a market or ring-fence a project.
#
# Real news, so it sits above the line, and clearly not a deal.
_NEW_SUBSIDIARY = re.compile(
    r"(incorporat\w+|form(ed|ation|ing)|set up|setting up|establish\w+|"
    r"registered)[^.]{0,70}"
    r"(wholly[- ]owned subsidiar|step[- ]down subsidiar|new subsidiar|"
    r"subsidiar\w+ (company|named)|joint venture company|"
    # Keystone Realtors "jointly set up a new real-estate LLP called One
    # Landmark House LLP" - the same event, in the vehicle Indian developers
    # actually use. Only "incorporation of ... LLP" was listed, and this
    # filing says "set up".
    r"\bllp\b|limited liability partnership|"
    # Welspun Corp's "associate company Welspun Slagexcel Private Ltd was
    # incorporated" is the same event under a different word.
    r"associate company)|"
    r"incorporation of[^.]{0,50}(subsidiar|company|\bllp\b)|"
    # ...and the same sentence written backwards. Welspun Corp's "associate
    # company Welspun Slagexcel Private Ltd was incorporated" puts the verb
    # last, and everything above requires it first.
    r"(subsidiar\w+|associate company|joint venture company)"
    r"[^.]{0,60}(was |has been |have been )?"
    r"(incorporated|formed|registered)", re.I)

# ...unless it actually bought something, which wins.
_BOUGHT_SOMETHING = re.compile(
    r"acquisition of[^.]{0,50}(stake|shareholding|equity|business|"
    r"undertaking|division)|"
    r"acquir(e|ed|es|ing)[^.]{0,50}(stake|shareholding|\d[\d.]*\s?%|per cent)|"
    r"share purchase agreement|slump sale|"
    r"scheme of (arrangement|amalgamation|merger|demerger)|"
    r"open offer|detailed public statement", re.I)

NEW_SUBSIDIARY_SCORE = 56
SCORE_FOR_TAG["New Subsidiary"] = NEW_SUBSIDIARY_SCORE


def new_subsidiary(text):
    """Did the company register a new entity rather than buy one?"""
    if not text:
        return False
    if _BOUGHT_SOMETHING.search(text):
        return False
    return bool(_NEW_SUBSIDIARY.search(text))


# The bigger event, when a promoter transaction is a step inside one.
#
# The promoter override replaces any dealing tag once the text mentions a
# promoter transaction, which is right for a Regulation 29 form and wrong for
# a corporate event that happens to contain one. Happiest Minds "is merging
# with ITC Infotech ... the deal involves a promoter stake sale and a
# subsequent merger where ITC Infotech will be the surviving entity" - a
# billion-dollar merger, published as a promoter buying shares.
_PART_OF_A_DEAL = re.compile(
    r"\bmerg(e|es|ed|er|ing)\b|amalgamat\w+|de-?merger|surviving entity|"
    r"scheme of (arrangement|amalgamation|merger)|open offer|takeover|"
    r"slump sale|acquir\w+[^.]{0,40}(entire|100 ?%|control|majority)", re.I)


def part_of_a_bigger_deal(text):
    """Is the promoter transaction a step inside a corporate event?"""
    return bool(_PART_OF_A_DEAL.search(text or ""))


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
SCORE_FOR_TAG["Promoter Buy/Sell"] = PROMOTER_SCORE


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


# The same mistake again, one meeting down.
#
# A company must tell the exchange when its board is GOING to meet and what it
# will consider. That notice names the thing it will consider, so it was being
# filed as that thing:
#
#   Manba Finance        "will hold a board meeting on 22 Sep to consider
#                         increasing its authorised share capital"      -> Pref
#   NHC Foods            "board will meet on 9 Sep to discuss a possible
#                         fund raise"                               -> Warrants
#   Commercial Syn Bags  "will hold a board meeting on 5 September"  -> Warrants
#
# None of them has decided anything. The board has not met.
# "board meeting" is written a dozen ways and two of them mattered here. Hero
# FinCorp "is holding a board COMMITTEE meeting on September 15 to discuss
# raising funds through the issuance of non-convertible debentures" - a notice
# that a committee will meet, published as a Fund Raising. The pattern wanted
# the words "board meeting" adjacent and the verb "will hold".
# "Committee meeting" on its own counts too. Unifinz Capital "will hold a
# committee meeting on September 8 to consider a debenture issue" had no word
# "board" in it anywhere, and a committee of the board meeting to approve an
# issue is the same kind of notice.
_BOARD = (r"board(?:\s+\w+){0,2}\s+meeting|meeting of the board|"
          r"board of directors|committee meeting|"
          r"meeting of the (\w+ ){0,2}committee")

_BOARD_FUTURE = re.compile(
    r"(?:" + _BOARD + r")[^.]{0,90}"
    r"(will be held|is scheduled|to be held|will meet|shall be held|"
    r"is proposed to be held)|"
    # Every verb a company uses for "a meeting is coming". "postponed its
    # Board of Directors meeting to September 8" and "announced a board meeting
    # on 7 September" were both missed, and both are notices of a future
    # meeting - a postponed meeting has still not happened.
    r"(will hold|is holding|holds|has scheduled|is convening|to convene|"
    r"has convened|scheduled|postponed|deferred|rescheduled|announced|"
    r"intimation of|notice of)[^.]{0,40}(?:" + _BOARD + r")|"
    r"board (of directors )?will (meet|consider)", re.I)

_BOARD_PURPOSE = re.compile(
    r"to consider|to discuss|to approve|to evaluate|inter[- ]alia|"
    r"for considering|to transact|to propose|to take up|to fix|"
    r"to determine|to authorise|to authorize|to seek|"
    # The purpose is often a sentence later, in the future tense: "...will hold
    # a board meeting on September 5. The board will discuss a preferential
    # issue." Commercial Syn Bags, filed as Warrants.
    r"will (discuss|consider|deliberate|evaluate|take up)", re.I)

# What makes it the EVENT rather than the notice. A board that has met and
# decided is news; these words say it did.
_BOARD_DONE = re.compile(
    r"\boutcome\b|has approved|have approved|board approved|"
    r"board has|were approved|was approved|approved the (allotment|issue|"
    r"scheme|acquisition|appointment)|allotted|"
    r"proceedings of|minutes of|considered and approved", re.I)

# When the meeting is what the filing is ABOUT.
#
# The existing rule says a notice wins only if the text names no substantive
# event. That is too weak for the commonest shape of all, because these filings
# name the dividend in the same breath as the meeting:
#
#   Rithwik       "will close its books from 24 to 30 September for the Annual
#                  General Meeting and dividend"
#   Kiran Vyapar  "book closure dates for its upcoming Annual General Meeting
#                  ... to determine eligibility for the dividend payment"
#   TANFAC        "share register will be closed ... for the 52nd AGM and
#                  dividend entitlement"
#   Pecos Hotels  "has scheduled its 21st Annual General Meeting ... has set
#                  18 September as the record date"
#
# All four were published as Dividend. The word is there, so score_text
# returns Dividend at 60, and 60 is substantive.
#
# Two ways the meeting is the subject rather than the context:
#
#   1. A book closure or record date that names the meeting as its PURPOSE.
#      "for the AGM and dividend" is a closure for the AGM; the dividend rides
#      along. Sunteck Realty's "record date for its upcoming dividend is
#      17 September" names the dividend as the purpose and stays a Dividend -
#      the AGM is a separate sentence, and [^.] cannot reach it.
#
#   2. The summary OPENS by scheduling one. What a filing leads with is what
#      it is about. A scheduling verb is required: Foseco's "shareholders have
#      approved a final dividend at its 41st Annual General Meeting" mentions
#      the meeting in its first sentence too, and is a dividend.
_CLOSURE_FOR_MEETING = re.compile(
    r"(book closure|clos\w+[^.]{0,30}(books|register|share transfer books)|"
    r"(share )?register[^.]{0,30}(will be |is |been )?clos|"
    r"record date|announced the dates?)"
    r"[^.]{0,150}(for|purpose of|in connection with|towards)[^.]{0,40}" + _GM,
    re.I)

# The meeting APPROVES the dividend; it is not what the record date is for.
# "Shareholders on record by this date will be eligible for the payout, subject
# to approval at the AGM" is a dividend, and a bare "dates?" in the pattern
# above used to match the word "date" in it and read the AGM as the purpose.
_MEETING_APPROVES = re.compile(
    r"(subject to|pending|if|upon|after) approval[^.]{0,40}" + _GM + r"|"
    r"approv\w+ (at|by|in)[^.]{0,20}" + _GM, re.I)

_MEETING_SCHEDULED = re.compile(
    r"(scheduled|convened|convening|will hold|will be held|is scheduled|"
    r"announced the dates? for|notice of|intimation of|has fixed)"
    r"[^.]{0,70}" + _GM + r"|"
    + _GM + r"[^.]{0,50}(is |has been |will be |to be )"
    r"(scheduled|convened|held)", re.I)


def meeting_is_the_subject(text):
    """Is the general meeting what this filing is about, not just context?"""
    if not text:
        return False

    # The same first-purpose test applies to the opening sentence. "The board
    # has set 23 September as the record date for the final dividend and
    # scheduled its 41st AGM" opens by scheduling a meeting AND by declaring a
    # dividend, and the dividend comes first - so it is a dividend, and the
    # meeting is when it gets approved.
    first = text.split(".", 1)[0]
    m = _MEETING_SCHEDULED.search(first)
    if m:
        # _MONEY_HAPPENED rather than a shorter list of its own. The
        # shorter list knew dividend, bonus, split and buyback, so a board
        # approving a preferential issue of 2.5 million convertible warrants
        # counted as nothing at all - and KCK Industries became a Meeting
        # because the same sentence went on to schedule the AGM that would
        # approve it. Two definitions of "something happened" is one too
        # many.
        before = first[:m.start()]
        money = (_MONEY_HAPPENED.search(before)
                 or re.search(r"dividend|bonus|split|buy-?back", before,
                              re.I))
        if not money:
            return True

    m = _CLOSURE_FOR_MEETING.search(text)
    if not m:
        return False

    # Which purpose is named FIRST.
    #
    # These filings routinely name two - "for the Annual General Meeting and
    # dividend" - and the first one is what the closure is for. Without this
    # test the pattern reaches over a hundred characters ahead and finds a
    # meeting mentioned later in the same sentence, which turned 60 genuine
    # dividends into meetings on the first attempt:
    #
    #   "record date for the final dividend and scheduled its 41st AGM"
    #        dividend first  -> a Dividend, and the AGM is when it is approved
    #   "close its books from 24 to 30 September for the AGM and dividend"
    #        meeting first   -> a Meeting, and the dividend rides along
    #
    # The match ends at the meeting, so a dividend inside it came first.
    clause = m.group(0)
    if _MEETING_APPROVES.search(clause):
        return False
    return not re.search(r"dividend|bonus|split|buy-?back", clause, re.I)


# The backstop: a meeting notice is a Meeting unless something actually HAPPENED.
#
# Ishan's rule, stated plainly - an AGM never belongs in another category. The
# rules above each settle one shape of that (the closure whose purpose is the
# meeting, the summary that opens by scheduling one), and each leaves a tail.
# Filatex India's letter to shareholders carrying "web links to the 36th AGM
# notice and annual report, and a reminder to claim any unclaimed dividends"
# was published as a Dividend on the word unclaimed dividends.
#
# So: if the filing is a notice of a general meeting, and nothing was approved,
# declared, allotted, received or paid, it is a Meeting. What keeps the real
# ones out is that a dividend filing always says the dividend was DONE - the
# board recommended it, the record date is fixed, the payout is Rs 12.50 - and
# a notice of a meeting says only that a meeting will be held.
_MONEY_HAPPENED = re.compile(
    r"(approved|declared|recommended|allotted|allotment of|received|paid|"
    r"fixed|has set|issued|raising up to|will raise|completed|executed|"
    r"entered into|sold|acquired|sanctioned)"
    r"[^.]{0,80}(dividend|bonus|split|buy-?back|preferential|warrant|"
    r"rights issue|\bqip\b|debenture|\bncds?\b|stake|shareholding|"
    r"acquisition|crore|lakh|\brs\.? ?\d)|"
    r"record date[^.]{0,60}(dividend|bonus|split)|"
    r"(dividend|bonus|split)[^.]{0,60}(record date|of rs|per share|"
    r"declared|recommended|approved|entitlement)", re.I)


def meeting_only(category, headline, body=""):
    """A notice of a meeting, with no money event actually recorded."""
    text = " ".join(x for x in (headline, body) if x)
    if not meeting_notice(category or "", headline or "", body or ""):
        return False
    return not _MONEY_HAPPENED.search(text)


# Paying a debt is not raising one.
#
# The JUNK list catches this when the headline says so. These headlines do not:
# Summit Digitel's is "Record Date Updates" and Hero FinCorp's is "Intimation
# under Regulation 50(1)". Only the attachment says what it is about, and the
# attachment for an interest notice recites the debenture issue itself - face
# value, coupon, tenor - so reading it finds "issue of debentures" and calls it
# a fund raise. Ten filings on 8 September.
#
# So the test has to run where the document is read, not only on the headline.
_DEBT_SERVICE = re.compile(
    r"interest payments? on[^.]{0,50}"
    r"(non-?convertible|debenture|\bncds?\b|\bbond)|"
    r"payment of interest on[^.]{0,40}(non-?convertible|debenture|\bncds?\b)|"
    r"record date[^.]{0,80}(interest|coupon|redemption|redeem)|"
    r"(interest|coupon)[^.]{0,60}record date|"
    r"confirmation of (redemption|payment|interest)|"
    r"redemption of[^.]{0,50}(\bncds?\b|debenture|commercial paper|\bbond)|"
    r"repayment of[^.]{0,40}(commercial paper|\bncds?\b|debenture|\bbond)|"
    r"coupon payment|interest and princip|payment towards interest|"
    # Redeeming an instrument, however it is announced. Star Health
    # "exercising its call option to fully redeem 4,000 non-convertible
    # debentures" and IIFL's "redemption schedule for its Series D32" were
    # both Fund Raising - paying money back read as taking it in.
    r"redemption schedule|call option[^.]{0,60}redeem|"
    r"call option[^.]{0,80}(bond|debenture|\bncds?\b|\bat-?1\b|tier i\b|perpetual)|"
    r"redeem[^.]{0,50}(\bncds?\b|debenture|\bbonds?\b|commercial paper)|"
    r"part(ial)? redemption|principal (repayment|payment)", re.I)

# ...unless the filing is ALSO announcing new money. Deliberately narrow: it
# looks for a decision to raise, not for the word "debenture", because every
# interest notice mentions the debentures it is paying interest on. Matching
# "issue of debentures" here would cancel the rule on every filing it is meant
# to catch.
_NEW_MONEY = re.compile(
    r"(approved|approves|proposes? to|board has|resolved to|decided to)"
    r"[^.]{0,70}(issue|issuance|rais|allot|placement|borrow)|"
    r"allotment of[^.]{0,40}"
    r"(\bncds?\b|debenture|\bbond|equity|shares|warrant)|"
    r"fund ?rais|private placement of|preferential (issue|allotment)|"
    r"\bqip\b|rights issue|further public offer", re.I)

# The exchange approving a listing wins over the issue it recites.
#
# Points cannot settle this. A trading approval for shares "allotted to
# non-promoters on a preferential basis" carries the word preferential, and
# Pref scores 60 against Listing Approval's 52, so the formality always lost
# to the event it was reporting on. Pakka Ltd and Fonebox Retail stayed under
# Pref for exactly that reason after the category was added.
_LISTING_APPROVAL = re.compile(
    r"(listing|trading) approval|approval for (listing|trading)|"
    r"in-?principle approval[^.]{0,70}(listing|issue|allot)|"
    r"listed and admitted to dealings|"
    r"(admitted to|permitted for) (dealings|trading)", re.I)

# ...unless a board decided something today, in which case the decision is the
# news and the approval is a line in it.
_DECIDED_TODAY = re.compile(
    r"board (has )?approved|board approved|resolved to issue|"
    r"approved the (issue|allotment|raising) of|"
    r"approved a (preferential|rights|further) ", re.I)

LISTING_APPROVAL_SCORE = 52


# "Exempt from an open offer" is not an open offer.
#
# The third time this shape has bitten. An inter-se transfer says it, and so
# does a preferential issue to promoters - Shah Foods' warrant issue carried
# the exemption and was published as an Open Offer at 70, which is the literal
# opposite of what the filing says.
#
# A real open offer names its machinery: a detailed public statement, a letter
# of offer, a manager to the offer, a post-offer advertisement, or an offer to
# acquire a stated percentage. If none of that is present and an exemption is,
# it is not one.
_OPEN_OFFER_MACHINERY = re.compile(
    r"detailed public statement|letter of offer|manager to the offer|"
    r"(post|pre)-? ?offer advertisement|committee of independent directors|"
    r"open offer to acquire|"
    r"open offer[^.]{0,60}\d[\d.]*\s?(%|per cent)|"
    # A public announcement IS the machinery, whether or not the words "open
    # offer" follow it - "Public announcement for the acquisition of 26% of
    # the equity share capital" is the opening move of one, and requiring the
    # phrase turned it into a plain Acquisition.
    r"public announcement|regulation 3\(1\)", re.I)

# Announcing one, as opposed to referring to one.
_OPEN_OFFER_ANNOUNCED = re.compile(
    r"(launch\w*|announc\w*|mak\w*|made|propos\w*|filed|submitt\w*)"
    r"[^.]{0,50}open offer|"
    r"open offer[^.]{0,40}(to acquire|for the acquisition|has (opened|closed))|"
    r"(opening|closing) date[^.]{0,30}open offer|"
    r"open offer (period|price|size)", re.I)


def open_offer_real(text):
    """Is the filing ABOUT an open offer, or does it merely mention one?

    A real open offer names its machinery - a detailed public statement, a
    letter of offer, a manager to the offer, a post-offer advertisement - or
    announces itself. Anything else is context, and context was enough to win:
    Shah Foods' preferential issue of warrants to its promoters says an
    executive director "resigned following a change in management post an open
    offer", and was published as an Open Offer at 70.
    """
    if not text:
        return False
    return bool(_OPEN_OFFER_MACHINERY.search(text)
                or _OPEN_OFFER_ANNOUNCED.search(text))


def listing_approval(text):
    """Is this the exchange clearing shares to trade, rather than the issue?"""
    if not text:
        return False
    if not _LISTING_APPROVAL.search(text):
        return False
    return not _DECIDED_TODAY.search(text)


DEBT_SERVICE_SCORE = 20


def debt_servicing(text):
    """Is this a payment on money already borrowed, rather than new money?"""
    if not text:
        return False
    if _NEW_MONEY.search(text):
        return False
    return bool(_DEBT_SERVICE.search(text))


BOARD_NOTICE_SCORE = 41


def board_meeting_notice(text):
    """Is this only a notice that the board is going to meet?"""
    if not text:
        return False
    if _BOARD_DONE.search(text):
        return False
    return bool(_BOARD_FUTURE.search(text) and _BOARD_PURPOSE.search(text))


def meeting_kind(category, headline):
    """Which of the three this filing actually is. Headline wins."""
    for tag, rx in _MEETING_RE:
        if rx.search(headline or ""):
            return tag
    hits = [tag for tag, rx in _MEETING_RE if rx.search(category or "")]
    if len(hits) == 1:
        return hits[0]
    return "Investor Meet" if hits else None


# A regulator acting AGAINST the company is a legal matter. A regulator
# granting what the company asked for is the thing it asked for.
#
# The retag rule for "an order FROM a regulator is not a customer order" also
# covers approvals, and retag has the last word - so an appointment needing
# the Reserve Bank's consent came out as Legal/Reg. Navi Finserv's nominee
# director and Real Touch Finance's managing director both did. An NCLT
# SANCTIONING a scheme of arrangement would have gone the same way, and that
# is the scheme itself, not litigation.
_CONSENT = re.compile(
    r"approv\w*|permi\w+|sanction\w*|no objection|\bnoc\b|consent", re.I)
# What makes an order a legal matter is that it takes something from the
# company: a penalty, a demand, a recovery. Not who signed it, and not
# which way round the sentence is written.
#
# Lactose India's "amalgamation has become effective, following the NCLT
# order dated August 20" names no approval at all, so looking for a
# consent word was not enough - it was still filed as litigation.
_ADVERSE = re.compile(
    r"impos\w+|levy|levied|demand\w*|penalt\w*|\bfine[sd]?\b|recover\w*|"
    r"prosecut\w*|show cause|attach\w+ (of|the)|freez\w+|disqualif\w*|"
    r"suspend\w*|cancell?\w*|revok\w*|restrain\w*|injunct\w*", re.I)
_CONSENT_FOR = re.compile(
    r"appoint|scheme of (arrangement|amalgamation|merger)|"
    r"licen[cs]e|registration|renewal|merger|amalgamat|fund rais|"
    r"preferential|allotment|listing|in-?principle|open offer|"
    r"increase in authorised|change of name", re.I)


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
        m = rx.search(text or "")
        if not m:
            continue
        # A consent, plus a named event for the consent to be about: leave
        # the event's own tag alone.
        # Read around the match, not just the match. Four real mergers
        # were sent to Legal/Reg by "NCLT order" - and the word that makes
        # it a consent, "approving", sat just outside the matched span:
        # Share India Securities, Venmax Drugs, Lactose India and GB Global
        # had all just had their schemes sanctioned.
        near = (text or "")[max(0, m.start() - 130):m.end() + 130]
        if (r_tag == "Legal/Reg"
                and not _ADVERSE.search(near)
                and (_CONSENT.search(near)
                     or _CONSENT_FOR.search(text or ""))):
            continue
        return r_tag
    return None


# A person's honorific ends in a full stop, and the rules read a full stop as
# the end of the sentence.
#
# Almost every pattern here is windowed - "(appointment|appointed)[^.]{0,70}
# (director|chief financial|...)" - and the window exists for a good reason: it
# keeps a match inside one sentence, so "the board approved the results" and a
# later mention of an acquisition cannot combine into a deal. But [^.] stops
# dead at the dot in "Mr.", and an appointment is exactly the kind of filing
# that names a person:
#
#   "re-appointed Ms. Neha Kailash Bhageria as an Independent Director"
#        no match - the window ends two characters in, at "Ms."
#   "re-appointed Neha Kailash Bhageria as an Independent Director"
#        matches, at 51, correctly
#
# Six filings on 8 September were mis-tagged by this alone: five under
# Legal/Reg and one under Investor Meet, all of them appointments or
# re-appointments, all of them scoring nothing at all so that whatever word
# triage found in the attachment decided the category. It is worth fixing here
# rather than in one pattern, because it silently weakens every windowed
# pattern in the file against any filing that names a person - which is most
# of the ones about people.
#
# Only titles and initials. "Ltd." and "etc." are left alone deliberately:
# those DO end sentences, and merging two sentences would let a window cross
# from one event into the next, which is the fault the windows prevent.
_HONORIFIC = re.compile(
    r"\b(mr|mrs|ms|dr|shri|smt|sri|kum|prof|messrs|m/s|rs|inr)\.",
    re.I)
_INITIAL = re.compile(r"\b([A-Za-z])\.(?=\s*[A-Z])")
# And the one inside a number. "set a record date for a Rs 0.60
# dividend" has a full stop between "record date" and "dividend", so the
# rule that recognises a dividend record date -
# record date[^.]{0,60}(dividend) - could not see past "Rs 0". Aristo
# Bio-Tech's board set a record date for a 60 paise dividend and the
# filing was published as a Meeting, which is the mistake that turned
# sixty real dividends into meetings once already. One pattern was given
# .{0,30} for this in August; every other windowed pattern still had the
# hole.
_DECIMAL = re.compile(r"(\d)\.(\d)")


# The exchange categories that mean "this filing is a stake disclosure".
#
# It matters WHERE a Promoter Buy/Sell tag came from. Filed under SAST or
# Regulation 29, the form's whole purpose is to record who moved the shares,
# and no summary can overrule it. Arrived from a regex in the attachment, it
# has no such standing - every SAST form prints the words "promoter and
# promoter group" in its table headings whether or not the acquirer is one.
#
# Lived in triage as STAKE_CATEGORY, where only triage could ask it.
STAKE_CATEGORY = [
    r"\bsast\b|insider trading|substantial acquisition of shares",
    r"reg\.? ?29|regulation 29|reg\.? ?10\(|regulation 10\(",
    r"disclosure under sebi takeover",
]
_STAKE_CATEGORY_RE = [re.compile(p, re.I) for p in STAKE_CATEGORY]


def stake_category(category):
    """Is this the exchange category a stake disclosure is filed under?"""
    return any(rx.search(category or "") for rx in _STAKE_CATEGORY_RE)


# A sentence that says nothing happened should count for nothing.
#
# Four filings under Investor Meet were relabelled Results by their own
# disclaimer: "No specific financial results or business developments were
# disclosed in this filing" scores 64 as Results, because "financial results"
# is in it. Action Construction Equipment, SEDEMAC Mechatronics and Axis
# Solutions were all notices of an analyst meeting that had nothing to
# report, and said so.
#
# Only sentences with no number in them. "not less than Rs 100 crore was
# approved" is a real event that happens to contain the word not, and a
# sentence carrying a figure is almost never a denial.
_NOTHING_HAPPENED = re.compile(
    r"[^.]*\b(no|not|nothing|none|neither)\b[^.\d]{0,120}"
    r"\b(disclos\w+|declar\w+|announc\w+|approv\w+|shared|discuss\w+|"
    r"decided|provided|made|taken)\b[^.\d]*\.",
    re.I)


def drop_denials(text):
    """Remove sentences whose whole content is that nothing happened."""
    if not text:
        return text
    return _NOTHING_HAPPENED.sub(" ", text)


def soften_stops(text):
    """Drop the full stops that are not ends of sentences."""
    if not text:
        return text
    text = drop_denials(text)
    text = _HONORIFIC.sub(r"\1", text)
    text = _INITIAL.sub(r"\1", text)
    return _DECIMAL.sub(r"\1\2", text)


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
    headline = soften_stops((headline or "").strip())

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
        if new_subsidiary(category + " || " + headline):
            return NEW_SUBSIDIARY_SCORE, "New Subsidiary"
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
    if tag in _DEALING_TAGS and new_subsidiary(both):
        tag, pts = "New Subsidiary", NEW_SUBSIDIARY_SCORE
    elif tag in _DEALING_TAGS and interse_transfer(both):
        tag, pts = "Inter-se Transfer", INTERSE_SCORE
    elif (tag in _DEALING_TAGS and promoter_deal(both)
          and not part_of_a_bigger_deal(both)):
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

    body = soften_stops(text[:4000])

    # Paying a debt is not raising one, and this is the only place that can
    # tell - the headline on these says "Record Date Updates". Checked before
    # the topics, because the attachment recites the debenture issue and
    # "issue of debentures" scores as a fund raise at 58.
    if debt_servicing(body):
        return (DEBT_SERVICE_SCORE, "Routine") if DEBT_SERVICE_SCORE >= floor             else (0, None)

    # An exchange clearing shares to trade is not the issue that created them.
    # Checked here rather than left to points, because the approval always
    # recites the issue and Pref outscores it.
    if listing_approval(body):
        return (LISTING_APPROVAL_SCORE, "Listing Approval")             if LISTING_APPROVAL_SCORE >= floor else (0, None)

    hits = [(pts, tag) for tag, pts, rx in _TOPIC_RE if rx.search(body)]

    # An Open Offer has to BE one, not merely mention one. Dropped from the
    # hits rather than handled afterwards, so whatever the filing IS about -
    # a preferential issue of warrants, in Shah Foods' case - wins on its own
    # merits instead of losing to Open Offer at 66.
    if hits and not open_offer_real(body):
        hits = [h for h in hits if h[1] != "Open Offer"]

    if not hits:
        # A meeting notice matches no topic at all - it is not an event, it is
        # an invitation to one - so it left here as nothing and whatever tag the
        # filing already carried survived. The same early return that swallowed
        # promoter deals and meeting notices in score().
        if meeting_notice("", "", body):
            return MEETING_NOTICE_SCORE, "Meeting"
        # Registering a new company matches no topic either - nothing was
        # bought, sold, issued or paid. 15 of the 144 filings under Acquisition
        # were this, and they got there from the PDF rather than from here.
        if new_subsidiary(body):
            return NEW_SUBSIDIARY_SCORE, "New Subsidiary"
        # A promoter dealing matches no topic either - "disclosed an
        # open-market sale of 1,000,000 shares" names no event the topic
        # patterns know. score() has asked this at its own early return since
        # the start; this function never did.
        if interse_transfer(body):
            return INTERSE_SCORE, "Inter-se Transfer"
        if promoter_deal(body):
            return PROMOTER_SCORE, "Promoter Buy/Sell"
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

    if tag in _DEALING_TAGS and new_subsidiary(body):
        tag, pts = "New Subsidiary", NEW_SUBSIDIARY_SCORE
    elif tag in _DEALING_TAGS and interse_transfer(body):
        tag, pts = "Inter-se Transfer", INTERSE_SCORE
    elif (tag in _DEALING_TAGS and promoter_deal(body)
          and not part_of_a_bigger_deal(body)):
        tag, pts = "Promoter Buy/Sell", PROMOTER_SCORE

    # retag() rather than a second copy of its loop. There WERE two copies,
    # and they had drifted: the guard that stops a regulator's CONSENT from
    # reading as a legal matter was added to the function, so retag() left
    # Navi Finserv's RBI-approved nominee director alone while this loop went
    # on calling it Legal/Reg. Every fix to one of two copies is a fix to
    # half the pipeline, and the half that reads the PDF is the half that
    # matters here.
    r_tag = retag(body)
    if r_tag:
        tag = r_tag

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


# ---------------------------------------------------------------------------
# 12. A TAG FROM THE PDF HAS TO BE CORROBORATED BY THE SUMMARY
#
# Triage reads every attachment and promotes on a regex hit, which is how real
# news buried under "General Updates" gets found. It is also how a passing
# word in a 40-page document decides a category. On 8 September:
#
#   Maral Overseas       a report on re-lodgement of physical share transfer
#                        requests, published as a Clinical Trial
#   Venus Remedies       a special window for re-lodging physical shares, also
#                        a Clinical Trial
#   Elgi Equipments      a subsidiary divesting a stake, a Scheme Of Arrangement
#   Superior Industrial  a secretarial audit report, a Buyback
#
# In every case the headline scored 18/Other and the SUMMARY named nothing of
# the kind. The summary is written from the same document, so if the document
# really were about a clinical trial the summary would say so. It does not,
# which means the match was incidental.
#
# So a tag that could only have come from the document has to be visible in the
# summary too. This is the same rule that already guarded Acquisition, Scheme
# and Open Offer, applied to every category that claims a specific event -
# because the fault was never specific to deals.
#
# Deliberately absent: Meeting, Routine, Other, Corp Action, Board Meeting and
# the rest that say "we could not tell". There is nothing to corroborate.
TAG_EVIDENCE = {
    # This has to stay in step with pipeline._DEAL_EVIDENCE, which
    # learned three wordings the hard way by demoting three real deals
    # that used them. Both regexes now judge the same tag, so a wording
    # missing from either one demotes a genuine deal.
    "Acquisition": r"acquisi|acquir|merger|amalgamat|slump sale|divest|"
                   r"stake|shareholding|takeover|share purchase|"
                   r"sell|sold|sale of|controlling interest|hive[- ]off|"
                   r"consolidat\w+ control|control over|joint venture|"
                   r"transfer(ring)? (of )?[^.]{0,30}"
                   r"(assets|megawatt|\bmw\b)",
    "Scheme Of Arrangement": r"scheme of|amalgamat|de-?merger|arrangement|"
                             r"\bnclt\b|merger",
    "Open Offer": r"open offer|detailed public statement|public announcement|"
                  r"manager to the offer|letter of offer|takeover",
    "Buyback": r"buy-?\s?back|bought back|tender offer",
    # "on a private placement basis to the promoters" is the same event
    # without the word, and allotment covers the rest.
    "Pref": r"preferential|private placement|allot",
    "Warrants": r"warrant",
    "Rights Issue": r"rights issue|right issue|rights entitlement",
    "Qip": r"\bqip\b|qualified institution",
    "Qip Allotment": r"\bqip\b|qualified institution",
    "Bonus": r"bonus",
    "Split": r"split|sub-?division|face value",
    "Dividend": r"dividend",
    "Fund Raising": r"fund ?rais|rais\w+|\bncds?\b|debenture|\bbond|"
                    r"commercial paper|private placement|borrow|\bfpo\b",
    # BCPL Railway "emerged as the lowest bidder for a railway
    # electrification project in the Asansol division", which is how a
    # public contract is won, and none of the words below appear in it.
    "Order": r"order|contract|letter of (award|intent|acceptance)|tender|"
             r"bidder|lowest bid|\bl-?1\b|"
             r"bagg|\bwon\b|\bwins\b|secured|award|mandate|\bloa\b|\bloi\b",
    "Clinical Trial": r"clinical|trial|phase|patient|endpoint|topline|enrol|"
                      r"dosing|pivotal|molecule|therap|efficacy",
    "Product Approval": r"approv|\bfda\b|usfda|cdsco|\banda\b|\bdmf\b|"
                        r"clearance|cleared|registration|launch|drug|"
                        r"formulation|generic|marketing authoris",
    "Plant Inspection": r"inspect|audit|form 483|observation|warning letter|"
                        r"\beir\b|import alert|\bgmp\b|facility|plant",
    "Capacity Increase": r"capacity|plant|greenfield|brownfield|capex|"
                         r"expansion|commission|production|facility|"
                         r"capital expenditure|land|machinery|equipment",
    "Partnership": r"partner|alliance|collaborat|\bmou\b|"
                   r"memorandum of understanding|tie-?up|agreement",
    "New Subsidiary": r"subsidiar|incorporat|\bllp\b|associate company|"
                      r"joint venture",
    "Delisting": r"delist",
    # Deliberately absent: Promoter Buy/Sell, Inter-se Transfer and Stake
    # Change. Those are not read off the document at all - they come from the
    # stake-disclosure form, which is filed under SAST precisely to say who
    # moved the shares. The summary of one reads "Innovative Money Matters Pvt
    # Ltd acquired 55,000 shares of Avonmore Capital" and never says promoter,
    # so asking it to corroborate would demote every one of them.
    # Vas Infrastructure and JCT both filed notices of their Committee of
    # Creditors meetings, which is a thing only a company in insolvency
    # files, and neither summary used any of the words above.
    "Nclt": r"\bnclt\b|\bnclat\b|tribunal|insolvency|resolution plan|"
            r"\bcirp\b|liquidat|moratorium|\bibc\b|"
            r"committee of creditors|\bcoc\b|resolution professional|"
            r"creditors|capital reduction|reduction of (share )?capital",
    "Listing Approval": r"listing|trading|in-?principle|admitted|dealings",
    "Esop": r"esop|employee stock|stock option|\bsar\b|share-?based",
    # PTC Industries' sustainability report was published as Legal/Reg
    # and Datamatics winning a US pet-care customer as a Concall. Both
    # tags came from the attachment and neither summary contained a
    # single word that argued for them.
    "Legal/Reg": r"order|penalt|\bsebi\b|court|tribunal|notice|demand|litigat|"
                 r"\bfine\b|show cause|adjudicat|appeal|writ|prosecut|compound|"
                 r"search|survey|raid|\bgst\b|income tax|arbitrat|settle|"
                 r"regulat|complian|violation|non-?compliance|disqualif",
    "Concall": r"conference call|earnings call|con-?call|analyst|transcript|"
               r"audio recording|recording of|investor call|earnings conference",
    "Investor Meet": r"investor|analyst|institutional|meet|conference|roadshow|"
                     r"webinar|schedul",
    "Ratings Update": r"rating|\bicra\b|crisil|india ratings|brickwork|"
                      r"acuite|infomerics|outlook|\bcare\b",
    "Results": r"result|earning|profit|revenue|turnover|quarter|half.year|"
               r"financial statement|ebitda|\bpat\b|standalone|consolidated",
    "Annual Report": r"annual report|annual accounts",
}

_TAG_EVIDENCE_RE = {t: re.compile(p, re.I) for t, p in TAG_EVIDENCE.items()}


_TOPIC_BY_TAG = {}
for _t, _p, _rx in _TOPIC_RE:
    _TOPIC_BY_TAG.setdefault(_t, []).append(_rx)


def topic_matches(tag, text):
    """Would this text produce `tag` from the topic patterns themselves?

    Stricter than tag_supported, and deliberately. The evidence lists are loose
    on purpose - they exist to catch a filing with NOTHING to do with its
    category - and looseness is wrong when the question is whether a deal
    actually happened. TAG_EVIDENCE["Acquisition"] contains "joint venture" and
    "acquir", so Syrma's joint venture company CHANGING ITS NAME and Modern
    Dairies' promoter converting warrants both counted as evidence of an
    acquisition, and both stayed under it.

    The topic pattern is the thing that would have put a filing in the category
    in the first place. If it does not match, the category was not earned.
    """
    rxs = _TOPIC_BY_TAG.get(tag)
    if not rxs or not text:
        return True                    # no pattern to judge on; leave it alone
    return any(rx.search(text) for rx in rxs)


def tag_supported(tag, text):
    """Does `text` contain anything that would justify `tag`?

    True for any tag with no evidence rule - those are the ones that make no
    claim, and there is nothing to check.
    """
    rx = _TAG_EVIDENCE_RE.get(tag)
    if rx is None:
        return True
    if not text:
        return True                    # nothing to judge on; leave it alone
    return bool(rx.search(text))

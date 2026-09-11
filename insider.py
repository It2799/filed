"""
Who inside a company is buying or selling its shares.

Every promoter, director and designated employee must tell the exchange when
they trade their own company's stock - SEBI's Prohibition of Insider Trading
rules, Regulation 7(2). It is the one disclosure that says what the people who
know most about a business are doing with their own money.

The announcements scraper already sees these arrive, but only as prose: a PDF
saying "please find enclosed the disclosure under Regulation 7(2)". The filing
itself is structured, and this reads that instead - who, how many, at what
price, by what route, and what they hold now.

WHERE IT COMES FROM
    NSE publishes the day's disclosures at
    nsearchives.nseindia.com/content/RSS/InsiderTrading.xml. Each item links an
    XBRL file holding the whole filing, and one filing can cover several
    people: NCL Industries' on 11 September covered three.

    Not the nseindia.com/api/corporates-pit endpoint, which looks like the
    obvious source and is not. It answers only per-symbol, returns twenty rows,
    and lags: on 12 September it gave NCL Industries nothing newer than
    28 March, while the feed had that day's filing. A day-old insider trade is
    not worth reading.

    BSE lists an equivalent feed on its own rss-feed page and it has been
    returning 404 - their side. The XBRL is on BSE's schema either way, so the
    parser below will read theirs unchanged the day it comes back. Until then
    anything filed only on BSE is missed, and that is worth knowing.

WHAT IS LEFT OUT, and why
    ESOP                 an employee exercising options is being paid, not
                         taking a view. About 18% of all rows.
    Inter-se-Transfer    shares moving inside the promoter family. No money
                         changes hands and nobody has decided anything.
    Welfare trusts       a company's own employee trust, holding shares for an
                         ESOP scheme and moving them mechanically.

    None of the three says anything about what an insider thinks the shares are
    worth, which is the only reason to read this at all.
"""

import datetime
import re
import time
import xml.etree.ElementTree as ET

import requests

import sources

FEED = "https://nsearchives.nseindia.com/content/RSS/InsiderTrading.xml"

# What the page Ishan linked actually calls.
#
# https://www.nseindia.com/companies-listing/corporate-filings-insider-trading
# is an empty shell until its JavaScript runs; the table is filled from
# /api/corporates-pit-gg, with a from_date and a to_date. The older
# /api/corporates-pit is still in the page's source, commented out, and it is
# the one this file used to reach for - per symbol, and months behind. That is
# why a week of history looked impossible.
#
# It is not. This endpoint answers for the whole market over a date range:
# 198 filings for the last seven days, 839 for thirty. Every row carries
# xmlFileName - the same XBRL the reader below already parses.
API_INDEX = "https://www.nseindia.com/api/corporates-pit-gg"
PIT_PAGE = ("https://www.nseindia.com/companies-listing/"
            "corporate-filings-insider-trading")

# How the trade was done. These say nothing about what the person thinks the
# shares are worth.
#
# Searched, not anchored. The old rule wanted the mode to be EXACTLY "esop",
# so "ESOS" - an Employee Stock Option SCHEME, the same thing with a different
# last letter - went straight through and onto the page.
SKIP_MODE = re.compile(
    r"\besop\b|\besos\b|\besps\b|\bespp\b|"
    r"employee stock option|employees stock option|stock option scheme|"
    r"sweat equity|share[- ]based|"
    r"inter[\s-]?se[\s-]?transfer", re.I)

# A company's own employee trust.
#
# Matched against the name with every non-letter removed, because they are
# punctuated every possible way: "Eclerx Employee Welfare (Trust)" slipped
# through a pattern expecting "welfare trust" as two plain words, and
# "JSW Steel Employees Welfare Trust ?  ESOP Plan 2016   A/c" is one real name.
#
# A family trust is NOT one of these. "Adivam Family Trust" is somebody's own
# money taking a view, which is the whole point of reading this.
# It matched on the word TRUST, and the trusts do not always carry it in the
# name. "Eclerx Employee Welfare" is the name; "Trust" is the CATEGORY, in a
# different field, so the letters the rule read were "eclerxemployeewelfare"
# and nothing matched. Ten of its trades were on the page. "Firstsource
# Employee Benefit Trust" missed by one letter - the rule wanted
# "employeesbenefittrust", with an s.
#
# So the rule keys on what these things actually are: an EMPLOYEE vehicle.
# Whatever the company calls it, "employee" or "staff" is next to "welfare",
# "benefit", "trust" or "stock option", and a person's name never is.
SKIP_NAME = re.compile(
    r"employee\w{0,2}welfare|employee\w{0,2}benefit|employee\w{0,2}trust|"
    r"staff\w{0,2}welfare|staff\w{0,2}benefit|staff\w{0,2}trust|"
    r"welfare\w{0,2}trust|benefittrust|"
    r"esoptrust|esopplan|esopscheme|esopaccount|"
    r"employeestockoption|employeesstockoption|"
    r"sharebased|sweatequity|"
    r"gratuitytrust|providentfund|superannuation", re.I)

# The same thing said across two fields rather than one. A vehicle whose
# CATEGORY is Trust and whose name mentions its employees is an employee
# trust however it is spelled - this is the backstop for the next one of
# these that is named in a way nobody predicted.
_STAFF_WORD = re.compile(r"employee|staff|welfare|esop|gratuity", re.I)


def _letters(s):
    return re.sub(r"[^A-Za-z]", "", s or "")

# The XBRL tags that matter, without their namespace.
TAGS = {
    "company": "NameOfTheCompany",
    "symbol": "Symbol",
    "scrip": "ScripCode",
    "isin": "ISINCode",
    "regulation": "DisclosureUnderRegulation",
    "filed_on": "DateOfFiling",
    "revised": "RevisedFilling",
    "who": "NameOfThePerson",
    "category": "CategoryOfPerson",
    "instrument": "TypeOfInstrument",
    "before_n": "SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity",
    "before_pct": "SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding",
    "shares": "SecuritiesAcquiredOrDisposedNumberOfSecurity",
    "value": "SecuritiesAcquiredOrDisposedValueOfSecurity",
    "side": "SecuritiesAcquiredOrDisposedTransactionType",
    "after_n": "SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity",
    "after_pct": "SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding",
    "mode": "ModeOfAcquisitionOrDisposal",
    "told_company": "DateOfIntimationToCompany",
    "exchange": "ExchangeOnWhichTheTradeWasExecuted",
}


def _local(tag):
    return re.sub(r"^\{[^}]*\}", "", tag)


def _num(v):
    if v is None:
        return 0
    s = str(v).replace(",", "").strip()
    if not s or s == "-":
        return 0
    try:
        return float(s)
    except ValueError:
        return 0


def _price(value, shares):
    """What one share went for, which the filing never states outright."""
    if not value or not shares:
        return 0.0
    return round(float(value) / float(shares), 2)


def _date(v):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y"):
        try:
            return datetime.datetime.strptime(str(v).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def feed_items(text, log=print):
    """(company, symbol, xbrl url, when) for each disclosure in the feed."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        log(f"  insider feed: could not parse - {e}")
        return []

    # Deduplicated by URL. The feed lists the same filing more than once -
    # South West Pinnacle's appeared fourteen times on 11 September, and
    # fetching each copy turned two people's trades into twenty-eight rows.
    # One filing, one fetch.
    out, seen = [], set()
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        if not link.endswith(".xml") or link in seen:
            continue
        seen.add(link)
        parts = [p.strip() for p in (item.findtext("description") or "").split("|")]
        out.append({
            "symbol": parts[0] if parts else "",
            "company": (item.findtext("title") or "").strip(),
            "url": link,
            "kind": parts[2] if len(parts) > 2 else "",      # Original / Revised
            "when": (item.findtext("pubDate") or "").strip(),
        })
    return out


def parse_xbrl(text):
    """Every person's trade in one filing.

    A filing covers one company and any number of people. XBRL keeps them
    apart with contextRef - the company's own fields sit on "MainI" and each
    person on "Disclosure1", "Disclosure2" and so on - so the values have to be
    grouped by that rather than read in document order. Reading them in order
    would pair the first person's name with the third person's share count.
    """
    root = ET.fromstring(text)
    want = {v: k for k, v in TAGS.items()}

    main, people = {}, {}
    for el in root.iter():
        name = want.get(_local(el.tag))
        if not name:
            continue
        value = (el.text or "").strip()
        if not value:
            continue
        ctx = el.attrib.get("contextRef", "")
        if ctx.lower().startswith("disclosure"):
            people.setdefault(ctx, {})[name] = value
        else:
            main.setdefault(name, value)

    return main, [people[k] for k in sorted(people)]


def skip_reason(person):
    """Why this trade is not worth showing, or None to keep it.

    Ishan's rule, and it has not changed: an employee stock scheme, a company
    welfare trust and a transfer inside a promoter family are all filed on
    this form and none of them is anybody deciding what the shares are worth.
    """
    if SKIP_MODE.search(person.get("mode") or ""):
        return (person.get("mode") or "").strip().lower()

    name = _letters(person.get("who"))
    if SKIP_NAME.search(name):
        return "employee trust"

    # A family trust is NOT one of these. "Adivam Family Trust" is somebody's
    # own money taking a view, which is the whole point of reading this - so
    # the category alone is never enough, the name has to mention the staff.
    category = (person.get("category") or "")
    if re.search(r"trust", category, re.I) and _STAFF_WORD.search(name):
        return "employee trust"
    return None


# What the filing calls the transaction, and what a person would call it.
#
# Matched as a substring rather than by exact equality. The old map keyed on
# "revoke" and "pledge", and the XBRL says "Pledge Revoke" and "Pledge
# Creation", so nothing matched and the sentence read "pledge revoke
# 18,176,000 shares". Pledge Revoke is checked before Pledge for the obvious
# reason.
_VERBS = [
    ("pledge revoke", "released a pledge on"),
    ("pledge release", "released a pledge on"),
    ("pledge invoke", "had a pledge invoked on"),
    ("pledge creation", "pledged"),
    ("revoke", "released a pledge on"),
    ("invoke", "had a pledge invoked on"),
    ("encumbrance", "encumbered"),
    ("pledge", "pledged"),
    ("buy", "bought"),
    ("sell", "sold"),
    ("acquisition", "bought"),
    ("disposal", "sold"),
]


# Who the person is, in words rather than in the exchange's shorthand. The
# form offers a dozen categories and a reader only wants to know whether this
# is somebody who RUNS the company, somebody related to them, or staff.
_ROLES = [
    ("promoter and director", "a promoter and director"),
    ("promoter group", "a promoter group entity"),
    ("promoter", "a promoter"),
    ("immediate relative", "a relative of an insider"),
    ("relative", "a relative of an insider"),
    ("key managerial", "senior management"),
    ("designated", "a designated employee"),
    ("director", "a director"),
    ("employee", "an employee"),
    ("trust", "a trust"),
]

# How it was done, said the way a person would say it. "by market purchase"
# is the form's wording; "on the open market" is English.
_HOWS = [
    ("market purchase", "on the open market"),
    ("market sale", "on the open market"),
    ("open market", "on the open market"),
    ("off market", "off market"),
    ("inheritance", "by inheritance"),
    ("gift", "as a gift"),
    ("allotment", "through an allotment"),
    ("conversion", "on conversion"),
    ("rights", "through a rights issue"),
    ("preferential", "through a preferential issue"),
    ("invocation", ""),
    ("pledge", ""),
    ("others", ""),
    ("other", ""),
]


def _indian(n):
    """1234567 -> 12,34,567. The way the number is actually written here."""
    n = int(n or 0)
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) <= 3:
        return sign + s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups + [tail])


def _rupees(v):
    """Rs 3.21 crore, not Rs 32,071,369."""
    v = float(v or 0)
    if v >= 10 ** 7:
        return f"Rs {v / 10 ** 7:,.2f} crore"
    if v >= 10 ** 5:
        return f"Rs {v / 10 ** 5:,.2f} lakh"
    return "Rs " + _indian(round(v))


def _each(price):
    """A share price, with the paise where a reader would look for them.

    Rs 872.50 is how a block gets priced and how the buyer talks about it, so
    rounding it to Rs 872 throws away a real number. Above a thousand rupees
    nobody quotes the paise, and a four-decimal average is noise.
    """
    price = float(price or 0)
    if not price:
        return ""
    if price < 1000:
        return f"Rs {price:,.2f}"
    return "Rs " + _indian(round(price))


def _stake(pct):
    """A holding, to two decimals, without pretending 0.0238% is precision."""
    try:
        v = float(str(pct).strip().rstrip("%"))
    except (TypeError, ValueError):
        return ""
    if not v:
        return ""
    return "under 0.01%" if v < 0.01 else f"{v:.2f}%"


def _role(category):
    c = (category or "").strip().lower()
    if not c:
        return ""
    return next((v for k, v in _ROLES if k in c), "a " + c)


def _how(mode):
    m = (mode or "").strip().lower()
    if not m:
        return ""
    for k, v in _HOWS:
        if k in m:
            return v
    return "by " + m


def headline(row):
    """One sentence, written for a person rather than for a form.

    It used to read:

        Eclerx Employee Welfare (Trust) bought 16,900 shares worth
        Rs 32,071,369 by market purchase - now holds 0.0238%

    which is the form's own words in the form's own order, with a rupee figure
    nobody can read at a glance and a stake quoted to four decimals it does
    not have. Now:

        Kalidindi Ravi, a promoter and director, bought 800 shares at
        Rs 176.50 each - Rs 1.41 lakh in all - on the open market.
        Holding after: 0.07%.

    The price per share is the number that was missing altogether, and it is
    the one that says whether somebody paid up or picked something off the
    floor.
    """
    side = (row.get("side") or "").strip().lower()
    verb = next((v for k, v in _VERBS if k in side), side or "traded")
    a_pledge = "pledge" in verb

    who = (row.get("who") or "").strip() or "An insider"
    role = _role(row.get("category"))
    shares = int(row.get("shares") or 0)
    value = row.get("value") or 0
    price = row.get("price") or _price(value, shares)

    lead = f"{who}, {role}," if role else who
    count = f"{_indian(shares)} shares" if shares else "shares"

    # A pledge is not a purchase. Nobody paid a price per share to pledge
    # something they already own, so "at Rs 176 each" would be a lie.
    if a_pledge:
        text = f"{lead} {verb} {count}"
        if value:
            text += f", worth {_rupees(value)}"
    else:
        text = f"{lead} {verb} {count}"
        each = _each(price)
        if each:
            text += f" at {each} each"
        if value:
            text += f" - {_rupees(value)} in all"
        how = _how(row.get("mode"))
        if how:
            text += f", {how}"
    text += "."

    after = _stake(row.get("after_pct"))
    if after:
        text += f" Holding after: {after}."
    return text


def index_filings(from_date, to_date, log=print, session=None):
    """Every insider filing in the window, from the page's own endpoint.

    One request covers the whole market and the whole range, which is the
    difference between this and everything tried before it. Returns the same
    shape feed_items() did, so nothing downstream changes.
    """
    s = session or _nse_session_or_plain()
    hdr = {"Accept": "*/*", "Referer": PIT_PAGE,
           "X-Requested-With": "XMLHttpRequest"}
    fmt = "%d-%m-%Y"
    out, seen = [], set()

    for index in ("equities", "sme"):
        try:
            r = s.get(API_INDEX, timeout=60, headers=hdr,
                      params={"index": index,
                              "from_date": from_date.strftime(fmt),
                              "to_date": to_date.strftime(fmt)})
            rows = (r.json() or {}).get("data") or []
        except Exception as e:
            log(f"  insider index ({index}): {type(e).__name__}: {e}")
            continue

        for row in rows:
            # xmlFileName is the plain XBRL. ixbrl is the same thing wrapped in
            # HTML with undeclared namespace prefixes, which an XML parser
            # will not read.
            url = (row.get("xmlFileName") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "url": url,
                "symbol": (row.get("symbol") or "").strip(),
                "company": (row.get("companyName") or "").strip(),
                "kind": (row.get("typeOfSubmission") or "").strip(),
            })
        log(f"  insider index ({index}): {len(rows)} filings")

    return out


def fetch(from_date, to_date, log=print, session=None):
    """Insider trades disclosed in the window, one record per person."""
    s = session or _nse_session_or_plain()
    hdr = {"User-Agent": sources.UA, "Accept": "*/*",
           "Referer": "https://www.nseindia.com/"}

    items = index_filings(from_date, to_date, log=log, session=s)
    if not items:
        return []

    log(f"  insider: {len(items)} filings to read")

    # A second guard, on the trade rather than the file. A company may file a
    # revision that repeats a trade already disclosed, and the same person's
    # same trade should appear once however many times it is filed.
    kept, skipped, failed, seen_trades = [], {}, 0, set()
    for item in items:
        try:
            fr = s.get(item["url"], timeout=40, headers=hdr)
            if fr.status_code != 200:
                failed += 1
                continue
            main, people = parse_xbrl(fr.content)
        except Exception:
            failed += 1
            continue

        filed = _date(main.get("filed_on"))
        if not filed or not (from_date <= filed <= to_date):
            continue

        for p in people:
            why = skip_reason(p)
            if why:
                skipped[why] = skipped.get(why, 0) + 1
                continue

            fingerprint = (main.get("symbol") or item["symbol"],
                           p.get("who"), p.get("shares"), p.get("value"),
                           p.get("mode"), p.get("told_company"))
            if fingerprint in seen_trades:
                continue
            seen_trades.add(fingerprint)

            row = {
                "id": f"PIT-{item['symbol']}-{item['url'].rsplit('/', 1)[-1]}-"
                      f"{len(kept)}",
                "exchange": "NSE",
                "symbol": main.get("symbol") or item["symbol"],
                "scrip": main.get("scrip", ""),
                "company": main.get("company") or item["company"],
                "who": p.get("who", ""),
                "category": p.get("category", ""),
                "side": p.get("side", ""),
                "mode": p.get("mode", ""),
                "shares": int(_num(p.get("shares"))),
                "value": _num(p.get("value")),
                # The filing gives a total and never a price. A reader wants
                # the price: Rs 32,071,369 for 16,900 shares means nothing
                # until it is Rs 1,898 each, which is the number you can hold
                # against what the share is trading at today.
                "price": _price(_num(p.get("value")), _num(p.get("shares"))),
                "before_n": int(_num(p.get("before_n"))),
                "before_pct": p.get("before_pct", ""),
                "after_n": int(_num(p.get("after_n"))),
                "after_pct": p.get("after_pct", ""),
                "traded_on": p.get("told_company", ""),
                "filed_on": str(filed),
                "regulation": main.get("regulation", ""),
                "revised": (main.get("revised", "false").lower() == "true"
                            or item["kind"].lower() == "revised"),
                "url": item["url"],
            }
            row["headline"] = headline(row)
            kept.append(row)

    if skipped:
        log("  insider: left out " + ", ".join(
            f"{n} {k}" for k, n in sorted(skipped.items(), key=lambda kv: -kv[1])))
    if failed:
        log(f"  insider: {failed} filings could not be read")
    log(f"  insider: {len(kept)} trades worth showing")
    return kept



# ---------------------------------------------------------------- history

# The feed holds today and empties overnight, so a week of history has to come
# from somewhere else. nseindia.com/api/corporates-pit does have history - it
# is only the LIVE end it lags on, which is why the daily reader does not use
# it - but it answers per symbol, so it needs a list of companies to ask about.
API_PIT = "https://www.nseindia.com/api/corporates-pit"


def _api_row(row, sym):
    """One row of the per-symbol API, in the same shape the XBRL reader gives."""
    qty = int(_num(row.get("secAcq")))
    out = {
        "id": f"PIT-{row.get('did') or ''}-{sym}",
        "exchange": "NSE",
        "symbol": (row.get("symbol") or sym or "").strip(),
        "scrip": "",
        "company": (row.get("company") or sym or "").strip(),
        "who": (row.get("acqName") or "").strip(),
        "category": (row.get("personCategory") or "").strip(),
        "side": (row.get("tdpTransactionType") or "").strip(),
        "mode": (row.get("acqMode") or "").strip(),
        "shares": qty,
        "value": _num(row.get("buyValue")) or _num(row.get("sellValue")),
        "before_n": int(_num(row.get("befAcqSharesNo"))),
        "before_pct": row.get("befAcqSharesPer") or "",
        "after_n": int(_num(row.get("afterAcqSharesNo"))),
        "after_pct": row.get("afterAcqSharesPer") or "",
        "traded_on": (row.get("acqfromDt") or "").strip(),
        "filed_on": "",
        "regulation": (row.get("anex") or "").strip(),
        "revised": False,
        "url": "",
    }
    out["headline"] = headline(out)
    return out


def fetch_history(symbols, from_date, to_date, log=print, session=None,
                  pause=0.25):
    """Insider trades for these symbols, filed in the window.

    Used to fill the page with the past week the first time, and to repair a
    day the daily reader missed. Slower than the feed and behind it, so it is
    not what the every-pass reader uses.
    """
    s = session or _nse_session_or_plain()
    hdr = {"Accept": "application/json", "Referer": PIT_PAGE,
           "X-Requested-With": "XMLHttpRequest"}

    kept, skipped, seen = [], {}, set()
    for i, sym in enumerate(symbols):
        try:
            r = s.get(API_PIT, params={"symbol": sym}, timeout=35, headers=hdr)
            rows = (r.json() or {}).get("data") or []
        except Exception:
            continue

        for row in rows:
            when = _date(row.get("intimDt")) or _date(row.get("date"))
            if not when or not (from_date <= when <= to_date):
                continue

            person = {"mode": row.get("acqMode"), "who": row.get("acqName")}
            why = skip_reason(person)
            if why:
                skipped[why] = skipped.get(why, 0) + 1
                continue

            key = (sym, row.get("acqName"), row.get("secAcq"),
                   row.get("acqMode"), row.get("acqfromDt"))
            if key in seen:
                continue
            seen.add(key)

            out = _api_row(row, sym)
            out["filed_on"] = str(when)
            kept.append(out)

        if pause:
            time.sleep(pause)
        if log and i and i % 100 == 0:
            log(f"  insider history: {i}/{len(symbols)} symbols, "
                f"{len(kept)} trades")

    if skipped:
        log("  insider history: left out " + ", ".join(
            f"{n} {k}" for k, n in sorted(skipped.items(), key=lambda kv: -kv[1])))
    log(f"  insider history: {len(kept)} trades from {len(symbols)} symbols")
    return kept


def _nse_session_or_plain():
    """A session that has shaken hands with NSE, or a plain one if that failed."""
    try:
        return sources._nse_session()
    except Exception:
        s = requests.Session()
        s.headers.update({"User-Agent": sources.UA})
        return s


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--show", type=int, default=30)
    a = p.parse_args()
    today = datetime.date.today()
    rows = fetch(today - datetime.timedelta(days=a.days), today)
    rows.sort(key=lambda r: -(r["value"] or 0))
    print()
    for r in rows[:a.show]:
        print(f"  {r['company'][:24]:<26}{r['headline'][:104]}")

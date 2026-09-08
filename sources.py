"""Pulls the raw announcement lists from BSE and NSE and puts them in one shape."""

import datetime
import re
import time
from urllib.parse import urlparse

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

BSE_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
BSE_PDF_LIVE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/"
BSE_PDF_HIST = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/"
NSE_API = "https://www.nseindia.com/api/corporate-announcements"
NSE_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"


def _clean(s):
    if not s:
        return ""
    s = s.replace("''", "'").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


def _external_url(value):
    """Return only a complete HTTP(S) URL; exchange placeholders become blank."""
    text = str(value or "").strip()
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    return text if parsed.scheme in ("http", "https") and parsed.netloc else ""


def _attachment_name(value):
    """BSE supplies a filename, not a URL, and occasionally a placeholder."""
    text = str(value or "").strip()
    if not text or text.lower() in {"-", "n/a", "na", "null", "none", "#"}:
        return ""
    return text


# ---------------------------------------------------------------- BSE

def fetch_bse(from_date, to_date, log=print):
    """BSE only answers one calendar day at a time, so we walk the days."""
    out, day = [], from_date
    while day <= to_date:
        rows = _fetch_bse_day(day, log)
        log(f"  BSE {day:%d %b}: {len(rows)} rows")
        out.extend(rows)
        day += datetime.timedelta(days=1)
    return out


def _fetch_bse_day(day, log=print):
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.bseindia.com/corporates/ann.html",
        "Origin": "https://www.bseindia.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    out, page = [], 1
    while page <= 60:
        params = {
            "pageno": page,
            "strCat": "-1",
            "strPrevDate": day.strftime("%Y%m%d"),
            "strScrip": "",
            "strSearch": "P",
            "strToDate": day.strftime("%Y%m%d"),
            "strType": "C",
            "subcategory": "-1",
        }
        # A page that fails is retried before the day is given up on.
        #
        # This used to break out of the loop on the first exception, which
        # silently truncated the entire rest of the day: page 4 times out, the
        # run reports "BSE 03 Sep: 160 rows" with no error, and everything
        # filed after mid-morning is simply absent. Nothing downstream could
        # tell - the filings were never fetched, so nothing knew to miss them.
        #
        # Reconciling against BSE's own RSS feed is what exposed it: on
        # 3 September a run fetched 349 of the day's 729 documents, and looked
        # perfectly healthy doing it.
        rows, failure = None, None
        for attempt in range(4):
            try:
                r = requests.get(BSE_API, params=params, headers=headers,
                                 timeout=45)
                rows = r.json().get("Table", []) or []
                break
            except Exception as e:
                failure = f"{type(e).__name__}: {e}"
                time.sleep(1 + attempt * 2)

        if rows is None:
            # Loud, and not silent truncation. The day is short and the run
            # should say so - tools/reconcile_feeds.py will say so too.
            log(f"  BSE {day:%d %b} page {page} failed after 4 tries "
                f"({failure}). The rest of this day was not fetched.")
            break

        if not rows:
            break

        for a in rows:
            att = _attachment_name(a.get("ATTACHMENTNAME"))
            cat = _clean(a.get("CATEGORYNAME"))
            sub = _clean(a.get("SUBCATNAME"))
            head = _clean(a.get("HEADLINE")) or _clean(a.get("NEWSSUB"))
            out.append({
                "id": "BSE-" + str(a.get("NEWSID") or a.get("SCRIP_CD")),
                "exchange": "BSE",
                "company": _clean(a.get("SLONGNAME")),
                "ticker": str(a.get("SCRIP_CD") or ""),
                "category": " / ".join(x for x in (cat, sub) if x),
                "headline": head,
                "dt": a.get("NEWS_DT") or a.get("DT_TM") or "",
                "pdf_url": (BSE_PDF_LIVE + att) if att else "",
                "pdf_alt": (BSE_PDF_HIST + att) if att else "",
                "page_url": _external_url(a.get("NSURL")),
                "critical": bool(a.get("CRITICALNEWS")),
            })

        # When BSE says how many pages there are, believe it and nothing else.
        #
        # These two tests used to be joined by "or", so a short page ended the
        # day even when BSE had just said there were five more. A page is not
        # reliably full - the API pads and trims - and one 30-row page on a
        # 700-filing day threw away everything after it.
        try:
            total_pages = int(rows[0].get("TotalPageCnt") or 0)
        except (TypeError, ValueError):
            total_pages = 0

        if total_pages:
            if page >= total_pages:
                break
        elif len(rows) < 40:
            # No page count given, so a short page is the only signal there is.
            break
        page += 1
        time.sleep(0.4)

    return out


# ---------------------------------------------------------------- NSE

def _nse_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    s.get("https://www.nseindia.com/", timeout=45)
    s.get(NSE_PAGE, timeout=45)
    return s


# NSE keeps its announcements in separate lists and will only hand over one at
# a time. Only "equities" was ever asked for, so everything filed by a company
# on the SME board or against a listed debt instrument was never fetched at
# all - not scored low, not filtered out, never seen.
#
# On 3 September that was 79 of NSE's 332 announcements, a quarter of the
# exchange: Happy Steels, Magson Retail, Smarten Power Systems, Refractory
# Shapes, and Tata Steel's commercial paper redemption. Reconciling against
# NSE's own RSS feed is what found it - see tools/reconcile_feeds.py. Nothing
# inside the pipeline could have: it had no idea what it had not asked for.
#
# "municipalBond" and "invitsreits" are real indexes too and answer 200 with an
# empty list most days. They are listed here so that the day one of them
# carries something, it arrives.
NSE_INDEXES = ("equities", "sme", "debt", "municipalBond", "invitsreits")


def _nse_index(session, index, from_date, to_date, log):
    """One index's announcements, or None if the request failed outright.

    None and [] mean different things: [] is a genuine "nothing filed today",
    which is the normal answer for the municipal bond list, and None is a
    failure worth retrying with a fresh handshake.
    """
    params = {
        "index": index,
        "from_date": from_date.strftime("%d-%m-%Y"),
        "to_date": to_date.strftime("%d-%m-%Y"),
    }
    try:
        r = session.get(NSE_API, params=params, timeout=60, headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": NSE_PAGE,
            "X-Requested-With": "XMLHttpRequest",
        })
    except Exception as e:
        log(f"  NSE {index}: {type(e).__name__}: {e}")
        return None
    if r.status_code != 200:
        log(f"  NSE {index}: HTTP {r.status_code}")
        return None
    try:
        data = r.json()
    except Exception:
        return None
    return data if isinstance(data, list) else None


def fetch_nse(from_date, to_date, log=print):
    try:
        s = _nse_session()
    except Exception as e:
        log(f"  NSE handshake failed: {type(e).__name__}: {e}")
        return []

    data = []
    for index in NSE_INDEXES:
        got = _nse_index(s, index, from_date, to_date, log)
        if got is None:                       # the handshake may have gone stale
            try:
                s = _nse_session()
            except Exception:
                pass
            got = _nse_index(s, index, from_date, to_date, log)
        if got:
            log(f"  NSE {index}: {len(got)} rows")
            # Which list it came from, kept on the row. NSE has always known
            # whether a company is on the SME board - it keeps them in a
            # separate list - and the answer was simply being thrown away at
            # this line, which is why the SME dashboard needed BSE's scrip list
            # for one exchange and nothing at all for the other.
            for a in got:
                a["_nse_index"] = index
            data.extend(got)

    if not data:
        return []

    out = []
    for a in data:
        att = _external_url(a.get("attchmntFile"))
        sym = _clean(a.get("symbol"))
        out.append({
            "id": "NSE-" + str(a.get("seq_id") or (sym + str(a.get("sort_date")))),
            "exchange": "NSE",
            # "sme" is one of NSE's five lists, so this is not a guess.
            "board": "SME" if a.get("_nse_index") == "sme" else "Main",
            "company": _clean(a.get("sm_name")) or sym,
            "ticker": sym,
            "category": _clean(a.get("desc")),
            "headline": _clean(a.get("attchmntText")) or _clean(a.get("desc")),
            "dt": a.get("sort_date") or a.get("an_dt") or "",
            "pdf_url": att,
            "pdf_alt": "",
            "page_url": f"https://www.nseindia.com/get-quotes/equity?symbol={sym}" if sym else "",
            "critical": False,
            "industry": _clean(a.get("smIndustry")),
        })

    log(f"  NSE: {len(out)} rows")
    return out


# ---------------------------------------------------------------- shared

def parse_dt(raw):
    """Best-effort parse of the different date formats the two sites use."""
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(raw[:26], fmt)
        except ValueError:
            continue
    return None


def _key(a):
    """Rough identity of a filing so the same news on both exchanges merges."""
    comp = re.sub(r"\b(limited|ltd|the|india|industries|company|co)\b|[^a-z0-9]", "",
                  (a["company"] or "").lower())
    head = re.sub(r"[^a-z0-9]", "", (a["headline"] or "").lower())[:70]
    return comp, head


def merge(items):
    """Collapse the same announcement filed on both exchanges into one card."""
    seen = {}
    for a in sorted(items, key=lambda x: (x["exchange"] != "NSE",)):
        k = _key(a)
        if k in seen and k[1]:
            other = seen[k]
            if a["exchange"] not in other["exchange"]:
                other["exchange"] = "NSE + BSE"
                if not other.get("pdf_url"):
                    other["pdf_url"] = a.get("pdf_url", "")
                    other["pdf_alt"] = a.get("pdf_alt", "")
        else:
            seen[k] = a
    return list(seen.values())


# The RSS feeds are deliberately not read here.
#
# They were, briefly, on 3 September - as a safety net for anything the JSON
# APIs failed to hand over. It worked, and it was the wrong answer. The feeds
# carry the whole of both exchanges, including debt instruments, mutual fund
# NAVs and unlisted private companies, and they carry no category at all, so
# every addition arrived as an uncategorised row for the rules to guess at.
# Company names came through as "VPIL-18%-RESET RATE-27-04-". It cluttered the
# dashboard and Ishan asked for it out.
#
# The faults it was insuring against are fixed where they belong instead:
# fetch_nse asks for all five of NSE's lists, and _fetch_bse_day retries a
# failed page rather than abandoning the rest of the day.
#
# tools/reconcile_feeds.py still reads them, to report anything the APIs did
# not return. Nothing it sees reaches the site.


# ---------------------------------------------------------------- SME or main

# Which board a company is listed on, which is not something either
# announcement API says.
#
# The two boards are different products. An SME company files under the same
# regulations and lands in the same feed, but it is a Rs 40 crore business with
# three analysts following it, sitting next to Reliance. A reader looking for
# one is not looking for the other, so they get their own dashboard.
#
# NSE is easy: it keeps SME in its own list, and fetch_nse already asks for it -
# the answer just was not being written down. BSE is harder. Its SME companies
# file into the same corpfiling system as everyone else and carry ordinary
# scrip codes in the same 54xxxx range as new main-board listings, so nothing
# in a filing distinguishes them.
#
# What does distinguish them is the list of who is on the board, and bsesme.com
# publishes it - not through an API, but as the options of the scrip dropdown on
# its announcements page. 581 companies, in the HTML. Every JSON endpoint
# guessed at returned the site's 404 page; the dropdown was there all along.
BSE_SME_PAGE = "https://www.bsesme.com/corpoaratefilings/Announcements.aspx"

_SME_CACHE = None
_SME_OPTION = re.compile(
    r"<option[^>]*value=\"(\d{6})\"[^>]*>([^<]{1,60})</option>", re.I)


def _sme_cache_path():
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sme_scrips.json")


def bse_sme_scrips(log=print, max_age_days=7):
    """{scrip code: symbol} for every company on the BSE SME board.

    Cached on disk, because the list changes when a company lists or migrates
    to the main board - a few times a month, not a few times an hour. A stale
    list is far better than none: the worst it does is put a newly listed SME
    on the main dashboard for a week.
    """
    global _SME_CACHE
    if _SME_CACHE is not None:
        return _SME_CACHE

    import json
    import os
    import time as _time

    path = _sme_cache_path()
    try:
        age = (_time.time() - os.path.getmtime(path)) / 86400
        if age < max_age_days:
            with open(path, encoding="utf-8") as f:
                _SME_CACHE = json.load(f)
            log(f"  SME list: {len(_SME_CACHE)} companies (cached, "
                f"{age:.1f} days old)")
            return _SME_CACHE
    except Exception:
        pass

    try:
        r = requests.get(BSE_SME_PAGE, headers={"User-Agent": UA}, timeout=60)
        found = {code: name.strip()
                 for code, name in _SME_OPTION.findall(r.text)}
        # A handful would mean the page changed shape. Keep whatever is on disk
        # rather than replacing a good list with a broken one.
        if len(found) < 100:
            raise ValueError(f"only {len(found)} scrips found; page changed?")
        _SME_CACHE = found
        with open(path, "w", encoding="utf-8") as f:
            json.dump(found, f, indent=0, sort_keys=True)
        log(f"  SME list: {len(found)} companies (refreshed)")
        return found
    except Exception as e:
        log(f"  SME list: could not refresh ({type(e).__name__}: {e})")
        try:
            with open(path, encoding="utf-8") as f:
                _SME_CACHE = json.load(f)
            log(f"  SME list: using the stale copy, {len(_SME_CACHE)} companies")
        except Exception:
            _SME_CACHE = {}
            log("  SME list: none available, everything will read as main board")
        return _SME_CACHE


def tag_boards(rows, log=print):
    """Write board = "SME" or "Main" onto every row. Mutates and returns rows."""
    sme = bse_sme_scrips(log=log)
    n = 0
    for r in rows:
        if r.get("board"):
            continue                      # fetch_nse already knew, from its index
        code = str(r.get("ticker") or "")
        r["board"] = "SME" if code in sme else "Main"
        if r["board"] == "SME":
            n += 1
    total_sme = sum(1 for r in rows if r.get("board") == "SME")
    log(f"  boards: {total_sme} SME, {len(rows) - total_sme} main "
        f"({n} matched by BSE scrip code)")
    return rows

"""Pulls the raw announcement lists from BSE and NSE and puts them in one shape."""

import datetime
import re
import time

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
            att = (a.get("ATTACHMENTNAME") or "").strip()
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
                "page_url": a.get("NSURL") or "",
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
            data.extend(got)

    if not data:
        return []

    out = []
    for a in data:
        att = (a.get("attchmntFile") or "").strip()
        sym = _clean(a.get("symbol"))
        out.append({
            "id": "NSE-" + str(a.get("seq_id") or (sym + str(a.get("sort_date")))),
            "exchange": "NSE",
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


# ---------------------------------------------------------------- RSS feeds

# A third way in, and the one that does not depend on the JSON APIs behaving.
#
# Both exchanges publish the same announcements as RSS, built by a different
# part of their systems. Two coverage faults this week - NSE handing over one
# of its five lists, BSE's paging ending on a timed-out page - were invisible
# from inside because a run that fetches half the exchange looks exactly like
# one that fetches all of it. Autoline's Tata Motors order and Suven's trial
# result were both sitting in a feed while the APIs said nothing.
#
# So the feeds are read as a SOURCE, not only as the check in
# tools/reconcile_feeds.py. Whatever the APIs return, anything in the feed and
# not in that answer is added. When the APIs are healthy this contributes
# nothing, which is the point: it costs two HTTP requests to make a bad fetch
# stop mattering.
#
# The feeds are a rolling window of the last few thousand filings, so they
# cover today and yesterday, not a week. That is exactly where a miss hurts
# most - the live page.
BSE_RSS = "https://www.bseindia.com/data/xml/announcements.xml"
NSE_RSS = "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"

_RSS_SCRIP = re.compile(r"\((\d{4,6})\)\s*$")
_RSS_SUBJECT = re.compile(r"\|\s*SUBJECT\s*:\s*(.+)$", re.I | re.S)


def _rss_rows(xml_text, exchange, log=print):
    """Feed entries in the same shape the JSON APIs produce."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        log(f"  {exchange} RSS: could not parse - {type(e).__name__}: {e}")
        return []

    out = []
    for it in root.findall(".//item"):
        def text(tag):
            return (it.findtext(tag) or "").strip()

        link = text("link")
        if not link:
            continue

        title = text("title")
        desc = text("description")

        # NSE writes the category after "|SUBJECT:"; BSE gives none, so the
        # headline stands in and rules.py treats it as a vague one - which is
        # right, because it then reads the PDF.
        cat = ""
        m = _RSS_SUBJECT.search(desc)
        if m:
            cat = _clean(m.group(1))
            desc = desc[: m.start()]

        scrip = _RSS_SCRIP.search(title)
        company = _clean(_RSS_SCRIP.sub("", title))

        # The attachment name is the id. It is what the JSON APIs key on too,
        # so a filing arriving both ways is one filing, not two.
        att = link.rstrip("/").rsplit("/", 1)[-1].split("?")[0]

        out.append({
            "id": f"{exchange}-RSS-{att}",
            "exchange": exchange,
            "company": company,
            "ticker": scrip.group(1) if scrip else "",
            "category": cat,
            "headline": _clean(desc),
            "dt": text("pubDate"),
            "pdf_url": link,
            "pdf_alt": "",
            "page_url": "",
            "critical": False,
            "from_rss": True,
        })
    return out


def fetch_rss(from_date, to_date, log=print):
    """Both feeds, limited to the days asked for."""
    rows = []
    for exchange, url in (("BSE", BSE_RSS), ("NSE", NSE_RSS)):
        try:
            r = requests.get(url, headers={
                "User-Agent": UA,
                "Referer": "https://www.bseindia.com/",
                "Accept": "*/*",
            }, timeout=60)
            if r.status_code != 200:
                log(f"  {exchange} RSS: HTTP {r.status_code}")
                continue
            got = _rss_rows(r.text, exchange, log)
        except Exception as e:
            log(f"  {exchange} RSS: {type(e).__name__}: {e}")
            continue

        inside = []
        for a in got:
            d = parse_dt(a["dt"])
            if d and from_date <= d.date() <= to_date:
                inside.append(a)
        log(f"  {exchange} RSS: {len(got)} in the feed, {len(inside)} in range")
        rows.extend(inside)
    return rows


def add_missing(existing, extra, log=print):
    """Whatever `extra` has that `existing` does not, by attachment.

    Matched on the attachment name alone. Both feeds and both APIs name the
    same file, so this is exact - unlike the company-and-headline fallback the
    reconciliation tool needs, which exists only because BSE's feed sometimes
    links a second copy of a document.
    """
    def att(a):
        u = a.get("pdf_url") or ""
        if not u:
            return None
        return u.rstrip("/").rsplit("/", 1)[-1].split("?")[0].lower() or None

    have = {att(a) for a in existing}
    have.discard(None)

    # Deduped against itself as well as against `existing`. BSE lists a filing
    # once for every instrument it applies to, so one interest-rate change from
    # a company with forty listed debentures is forty entries pointing at one
    # document: 8,527 feed items on 3 September were about 750 documents. The
    # first version of this checked only against `existing` and added all
    # 7,117 of the leftovers.
    added = []
    for a in extra:
        k = att(a)
        if not k or k in have:
            continue
        have.add(k)
        added.append(a)

    if added:
        log(f"  RSS added {len(added)} filings the APIs did not return")
    return existing + added

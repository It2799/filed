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
        try:
            r = requests.get(BSE_API, params=params, headers=headers, timeout=45)
            rows = r.json().get("Table", []) or []
        except Exception as e:
            log(f"  BSE {day:%d %b} page {page} failed: {type(e).__name__}: {e}")
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

        # TotalPageCnt is often missing, so also stop on a short page.
        total_pages = rows[0].get("TotalPageCnt")
        if len(rows) < 40 or (total_pages and page >= int(total_pages)):
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


def fetch_nse(from_date, to_date, log=print):
    try:
        s = _nse_session()
    except Exception as e:
        log(f"  NSE handshake failed: {type(e).__name__}: {e}")
        return []

    params = {
        "index": "equities",
        "from_date": from_date.strftime("%d-%m-%Y"),
        "to_date": to_date.strftime("%d-%m-%Y"),
    }
    data = None
    for attempt in range(3):
        try:
            r = s.get(NSE_API, params=params, timeout=60, headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": NSE_PAGE,
                "X-Requested-With": "XMLHttpRequest",
            })
            if r.status_code == 200:
                data = r.json()
                break
            log(f"  NSE attempt {attempt + 1}: HTTP {r.status_code}")
        except Exception as e:
            log(f"  NSE attempt {attempt + 1}: {type(e).__name__}: {e}")
        time.sleep(2)
        try:
            s = _nse_session()
        except Exception:
            pass

    if not isinstance(data, list):
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

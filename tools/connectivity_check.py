"""
Can this machine reach NSE and BSE?

Run this on any server you're thinking of deploying to. Home broadband almost
always works; data-centre addresses (any cloud server, including GitHub Actions)
often get blocked, and that's the difference between paying nothing for proxies
and paying a few thousand rupees a month.

    python tools/connectivity_check.py

Exits 0 if both exchanges answered with real data, 1 otherwise.
"""

import datetime
import io
import json
import sys
import zipfile

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

results = {}


def line(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:<34} {detail}")
    return ok


def where_am_i():
    print("WHERE THIS IS RUNNING")
    try:
        r = requests.get("https://ipinfo.io/json", timeout=20)
        d = r.json()
        print(f"  ip       {d.get('ip')}")
        print(f"  org      {d.get('org')}")
        print(f"  location {d.get('city')}, {d.get('country')}")
        results["network"] = d.get("org", "")
    except Exception as e:
        print(f"  (couldn't determine: {e})")
    print()


def check_bse():
    print("BSE")
    day = datetime.date.today()
    ok_any = False
    for back in range(0, 5):                 # walk back for a weekday with filings
        d = day - datetime.timedelta(days=back)
        try:
            r = requests.get(
                "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w",
                params={"pageno": 1, "strCat": "-1", "strPrevDate": d.strftime("%Y%m%d"),
                        "strScrip": "", "strSearch": "P", "strToDate": d.strftime("%Y%m%d"),
                        "strType": "C", "subcategory": "-1"},
                headers={"User-Agent": UA, "Referer": "https://www.bseindia.com/",
                         "Origin": "https://www.bseindia.com",
                         "Accept": "application/json, text/plain, */*"},
                timeout=45)
            rows = r.json().get("Table", []) or []
        except Exception as e:
            line(f"announcements {d:%d %b}", False, f"{type(e).__name__}: {e}")
            continue
        if rows:
            ok_any = line(f"announcements {d:%d %b}", True,
                          f"HTTP {r.status_code}, {len(rows)} rows")
            att = (rows[0].get("ATTACHMENTNAME") or "").strip()
            if att:
                try:
                    p = requests.get(
                        "https://www.bseindia.com/xml-data/corpfiling/AttachLive/" + att,
                        headers={"User-Agent": UA, "Referer": "https://www.bseindia.com/"},
                        timeout=60)
                    line("PDF download", p.status_code == 200 and p.content[:4] == b"%PDF",
                         f"HTTP {p.status_code}, {len(p.content):,} bytes")
                except Exception as e:
                    line("PDF download", False, f"{type(e).__name__}: {e}")
            break
        line(f"announcements {d:%d %b}", False, f"HTTP {r.status_code}, 0 rows")
    results["bse"] = ok_any
    print()


def check_nse():
    print("NSE")
    s = requests.Session()
    s.headers.update({"User-Agent": UA,
                      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                      "Accept-Language": "en-US,en;q=0.9"})
    try:
        h = s.get("https://www.nseindia.com/", timeout=45)
        line("homepage handshake", h.status_code == 200,
             f"HTTP {h.status_code}, {len(s.cookies)} cookies")
    except Exception as e:
        line("homepage handshake", False, f"{type(e).__name__}: {e}")
        results["nse"] = False
        print()
        return

    ok = False
    try:
        r = s.get("https://www.nseindia.com/api/corporate-announcements",
                  params={"index": "equities"},
                  headers={"Accept": "application/json",
                           "Referer": "https://www.nseindia.com/companies-listing/"
                                      "corporate-filings-announcements"},
                  timeout=60)
        data = r.json() if r.status_code == 200 else []
        ok = line("announcements API", bool(data),
                  f"HTTP {r.status_code}, {len(data) if isinstance(data, list) else 0} rows")
        if ok:
            att = (data[0].get("attchmntFile") or "").strip()
            if att:
                p = s.get(att, headers={"Referer": "https://www.nseindia.com/"}, timeout=60)
                good = p.status_code == 200 and p.content[:4] in (b"%PDF", b"PK\x03\x04")
                line("attachment download", good,
                     f"HTTP {p.status_code}, {len(p.content):,} bytes")
    except Exception as e:
        line("announcements API", False, f"{type(e).__name__}: {e}")
    results["nse"] = ok
    print()


if __name__ == "__main__":
    print("=" * 66)
    where_am_i()
    check_bse()
    check_nse()
    print("=" * 66)

    both = results.get("bse") and results.get("nse")
    if both:
        print("VERDICT: both exchanges reachable from here. No proxies needed.")
    elif results.get("bse") or results.get("nse"):
        print("VERDICT: PARTIAL - one exchange is blocked from this address.")
        print("         You'd need a proxy for that one, or a different host.")
    else:
        print("VERDICT: BLOCKED. This address can't read either exchange.")
        print("         Deploying here would need residential proxies.")
    sys.exit(0 if both else 1)

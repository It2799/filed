"""
Market capitalisation lookup.

The announcement feeds don't carry market cap, but BSE publishes it per scrip:

    /api/StockTrading/w?quotetype=EQ&scripcode=500325  ->  MktCapFull, in crores

BSE filings already carry their scrip code. NSE-only filings don't, so we match
them to a BSE scrip by company name using the BSE feed we already fetched -
almost every listed company files on both exchanges, so the map is close to
complete and costs no extra requests to build.

Results are cached on disk. Market caps move daily but we only ever show a
rounded figure, so a cache that is a few days old is fine and saves several
hundred requests per run.
"""

import concurrent.futures as cf
import json
import os
import re
import threading
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "mcap.json")
MAX_AGE = 60 * 60 * 24 * 5          # refresh anything older than 5 days

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://www.bseindia.com/",
           "Origin": "https://www.bseindia.com",
           "Accept": "application/json, text/plain, */*"}
URL = "https://api.bseindia.com/BseIndiaAPI/api/StockTrading/w"

_lock = threading.Lock()


def norm(name):
    """Company names differ slightly between exchanges, so flatten them."""
    n = (name or "").lower()
    n = re.sub(r"\b(limited|ltd|private|pvt|the|and|company|co|corporation|corp|"
               r"india|indian|\(i\)|inc)\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)
    os.replace(tmp, CACHE)


def _fetch(scrip):
    """Market cap in crores for one BSE scrip code, or None."""
    try:
        r = requests.get(URL, params={"flag": "", "quotetype": "EQ",
                                      "scripcode": str(scrip)},
                         headers=HEADERS, timeout=30)
        if r.status_code != 200 or not r.text.strip().startswith("{"):
            return None
        raw = (r.json() or {}).get("MktCapFull") or ""
        raw = str(raw).replace(",", "").strip()
        if not raw:
            return None
        val = float(raw)
        return val if val > 0 else None
    except Exception:
        return None


def scrip_index(records):
    """company-name -> BSE scrip code, built from the BSE records we already have."""
    idx = {}
    for r in records:
        if r.get("exchange", "").startswith("BSE") or r.get("exchange") == "NSE + BSE":
            code = str(r.get("ticker") or "").strip()
            if code.isdigit():
                idx.setdefault(norm(r.get("company")), code)
    return idx


def attach(records, workers=8, log=print):
    """
    Put `mcap` (crores, float) on every record we can identify.

    Only looks up each company once, and only if the cache entry is missing or
    stale, so a normal run makes very few requests.
    """
    idx = scrip_index(records)
    cache = load_cache()
    now = time.time()

    # Which companies do we actually need?
    wanted = {}
    for r in records:
        key = norm(r.get("company"))
        if not key or key in wanted:
            continue
        code = str(r.get("ticker") or "").strip()
        if not code.isdigit():
            code = idx.get(key, "")
        if code:
            wanted[key] = code

    stale = [(k, c) for k, c in wanted.items()
             if k not in cache or (now - cache[k].get("at", 0)) > MAX_AGE]

    log(f"Market cap: {len(wanted)} companies, {len(stale)} need a lookup "
        f"({len(wanted) - len(stale)} cached)")

    if stale:
        done = [0]

        def work(item):
            key, code = item
            val = _fetch(code)
            with _lock:
                done[0] += 1
                if val:
                    cache[key] = {"cr": val, "code": code, "at": now}
                if done[0] % 100 == 0:
                    log(f"  ...{done[0]}/{len(stale)}")

        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, stale))
        save_cache(cache)

    hits = 0
    for r in records:
        e = cache.get(norm(r.get("company")))
        if e and e.get("cr"):
            r["mcap"] = round(e["cr"], 1)
            hits += 1

    log(f"Market cap attached to {hits}/{len(records)} filings")
    return records

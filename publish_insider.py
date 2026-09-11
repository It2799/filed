"""
Put the day's insider trades where the website can read them.

Kept apart from the announcements. A filing under Regulation 7(2) is a
different kind of thing from a company announcement - it is a person, a
quantity and a price, not prose - and it earns its own section rather than a
row in a list of announcements about something else.

Stored the way publish.py stores days, so there is one storage service and one
shape to understand:

    mt:insider:2026-09-11        the day's trades, as JSON
    mt:insider:2026-09-11:parts  how many pieces it was split into
    mt:insider:index             the days held, newest first
    mt:insider:meta              when it last ran, and what it found

ACCUMULATES, rather than replacing. NSE's feed holds only what has been filed
so far today and empties overnight, so a pass at eleven in the morning sees
less than one at six in the evening. Writing the day fresh each time would
delete the morning's trades every afternoon. Each pass merges what it finds
into what is already there, keyed on the trade.

    python publish_insider.py            # today, write it
    python publish_insider.py --dry-run  # today, print it
"""

import argparse
import datetime
import json
import os
import re
import sys

import requests

import insider
import mcap

TTL_DAYS = 400
TTL_SECONDS = TTL_DAYS * 24 * 3600
MAX_BYTES = 900_000
KEEP_DAYS = 90


def creds():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    tok = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return url, tok


def redis(url, token, command):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"},
                      json=command, timeout=60)
    r.raise_for_status()
    return r.json().get("result")


def read_day(url, token, key):
    """Whatever is already stored for this day, across however many parts."""
    try:
        parts = int(redis(url, token, ["GET", f"{key}:parts"]) or 0)
    except (TypeError, ValueError):
        parts = 0
    if not parts:
        raw = redis(url, token, ["GET", key])
        try:
            return json.loads(raw) if raw else []
        except Exception:
            return []

    rows = []
    for i in range(parts):
        raw = redis(url, token, ["GET", f"{key}:{i}"])
        if not raw:
            continue
        try:
            rows.extend(json.loads(raw))
        except Exception:
            pass
    return rows


def write_day(url, token, key, rows):
    """One day's trades, split if they will not fit in a single request."""
    blob = json.dumps(rows, ensure_ascii=False)
    if len(blob.encode("utf-8")) <= MAX_BYTES:
        redis(url, token, ["SET", key, blob, "EX", str(TTL_SECONDS)])
        redis(url, token, ["SET", f"{key}:parts", "0", "EX", str(TTL_SECONDS)])
        return 1

    n = (len(blob.encode("utf-8")) // MAX_BYTES) + 1
    size = (len(rows) // n) + 1
    chunks = [rows[i:i + size] for i in range(0, len(rows), size)]
    for i, chunk in enumerate(chunks):
        redis(url, token, [
            "SET", f"{key}:{i}", json.dumps(chunk, ensure_ascii=False),
            "EX", str(TTL_SECONDS)])
    redis(url, token, ["SET", f"{key}:parts", str(len(chunks)),
                       "EX", str(TTL_SECONDS)])
    return len(chunks)


def with_mcap(rows, log=print):
    """Put the company's market cap on every trade we can identify.

    A promoter putting Rs 2 crore into a Rs 60 crore company is a different
    piece of news from the same Rs 2 crore going into a Rs 60,000 crore one,
    and without the size there is no way to tell them apart.

    mcap.attach matches on the BSE scrip code, which the XBRL filing carries -
    so these rows are handed over looking like BSE records, which is what they
    are: the code is the company's own.
    """
    if not rows:
        return rows
    shaped = [{"company": r.get("company"), "ticker": r.get("scrip") or "",
               "exchange": "BSE" if r.get("scrip") else "NSE"} for r in rows]
    try:
        mcap.attach(shaped, log=lambda *a, **k: None)
    except Exception as e:
        log(f"  insider: market caps unavailable ({type(e).__name__})")
        return rows

    got = 0
    for r, sh in zip(rows, shaped):
        if sh.get("mcap"):
            r["mcap"] = sh["mcap"]
            got += 1
    log(f"  insider: market cap on {got} of {len(rows)} trades")
    return rows


def trade_key(row):
    """What makes two rows the same trade.

    Not the id: that carries the filing's file name, and a company filing a
    revision produces a new file for a trade already shown.
    """
    key = "|".join(str(row.get(k, "")) for k in
                   ("symbol", "who", "shares", "value", "mode", "traded_on"))
    if key.strip("|0"):
        return key

    # A row read from the document has none of those - no share count in a
    # field, no named person, no mode - so every one of them collapsed to the
    # same key and a day of sixty-eight filings stored as one. For those, the
    # company and the sentence are what make it distinct.
    return "FIL|" + "|".join(str(row.get(k, "")) for k in
                             ("company", "filed_on"))[:200] + \
           "|" + (row.get("headline") or "")[:120]


def merge(old, new):
    """Today's trades so far, plus whatever this pass found.

    A later filing wins on a key it shares with an earlier one, because a
    revision is filed to correct something.
    """
    by_key = {trade_key(r): r for r in old}
    added = 0
    for r in new:
        k = trade_key(r)
        if k not in by_key:
            added += 1
        by_key[k] = r
    rows = list(by_key.values())
    rows.sort(key=lambda r: (-(r.get("value") or 0), -(r.get("shares") or 0)))
    return rows, added


def store_days(url, token, by_day, log=print):
    """Merge each day's trades into whatever is already stored for it."""
    written = 0
    for day, found in sorted(by_day.items()):
        key = f"mt:insider:{day}"
        rows, added = merge(read_day(url, token, key), found)
        write_day(url, token, key, rows)
        written += added
        log(f"  insider: {day} now holds {len(rows)} trades (+{added})")
    return written


def refresh_index(url, token, days_seen):
    raw = redis(url, token, ["GET", "mt:insider:index"])
    try:
        days = json.loads(raw) if raw else []
    except Exception:
        days = []
    days = sorted(set(list(days_seen) + [x for x in days if isinstance(x, str)]),
                  reverse=True)[:KEEP_DAYS]
    redis(url, token, ["SET", "mt:insider:index",
                       json.dumps(days), "EX", str(TTL_SECONDS)])
    return days


# Tags that ARE insider activity, in the announcements we already store.
#
# This is the source that works today. NSE's XBRL feed is same-day only and
# empties overnight, so on a Saturday - or before the market opens - there is
# nothing in it at all, and a section with nothing in it is not a section.
#
# Our own scrape has been reading these filings from BOTH exchanges all along,
# as prose rather than as fields: "promoter Dr. Krishna Prasad Chigurupati sold
# 1.2 lakh shares". Less than the XBRL gives, and a great deal more than an
# empty page.
#
# Inter-se Transfer is deliberately absent - Ishan's rule, and the same one the
# XBRL reader applies.
FILING_TAGS = {"Promoter Buy/Sell", "Stake Change"}


def from_filings(days, log=print):
    """Insider activity out of the announcements we already hold."""
    rows, page, seen = [], 1, set()
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              + datetime.timedelta(hours=5, minutes=30)).date() -         datetime.timedelta(days=days - 1)

    while page <= 80:
        u = ("https://www.markettide.in/api/announcements"
             f"?scope=important&page={page}")
        try:
            d = requests.get(u, timeout=45,
                             headers={"User-Agent": "markettide-insider"}).json()
        except Exception as e:
            log(f"  insider filings: {type(e).__name__}")
            break

        for r in d.get("items") or []:
            if r.get("tag") not in FILING_TAGS:
                continue
            day = r.get("day") or ""
            if day and day < cutoff.isoformat():
                continue
            text = (r.get("summary") or r.get("headline") or "").strip()
            if not text:
                continue
            # The same exclusions, judged on the prose rather than on fields.
            if insider.SKIP_NAME.search(insider._letters(text)):
                continue
            if re.search(r"\besop\b|employee stock option|inter-?se transfer",
                         text, re.I):
                continue

            key = (r.get("company"), day, text[:80])
            if key in seen:
                continue
            seen.add(key)

            rows.append({
                "id": f"FIL-{r.get('id') or len(rows)}",
                "source": "filing",
                "exchange": r.get("exchange") or "",
                "symbol": "", "scrip": "",
                "company": r.get("company") or "",
                "mcap": r.get("mcap"),
                "who": "", "category": "",
                "side": "", "mode": "",
                "shares": 0, "value": 0,
                "before_n": 0, "before_pct": "",
                "after_n": 0, "after_pct": "",
                "traded_on": "", "filed_on": day,
                "headline": text,
                "regulation": "", "revised": False,
                "url": r.get("pdf_url") or r.get("page_url") or "",
            })

        if not d.get("hasMore"):
            break
        page += 1

    log(f"  insider: {len(rows)} insider filings from our own scrape")
    return rows


def symbols_from_site(days=7, log=print):
    """Companies that filed anything recently, as NSE symbols.

    The history API answers per symbol, so it needs a list to ask about. The
    site already knows which companies have been active - that is what it is
    for - and asking about two thousand listed companies to find fifty with
    insider trades would be rude as well as slow.
    """
    seen, page = {}, 1
    while page <= 80:
        u = ("https://www.markettide.in/api/announcements"
             f"?scope=all&page={page}")
        try:
            d = requests.get(u, timeout=45,
                             headers={"User-Agent": "markettide-insider"}).json()
        except Exception:
            break
        for r in d.get("items") or []:
            t = (r.get("ticker") or "").strip()
            if t and not t.isdigit():            # NSE symbols, not BSE codes
                seen[t] = True
        if not d.get("hasMore"):
            break
        page += 1
    log(f"  insider: {len(seen)} NSE symbols to ask about")
    return list(seen)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day", help="YYYY-MM-DD; default is today in India")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--from-filings", type=int, metavar="DAYS",
                   help="seed from the insider filings our own scrape already "
                        "holds, both exchanges, for the last DAYS days")
    p.add_argument("--backfill", type=int, metavar="DAYS",
                   help="fill the last DAYS days from the per-symbol history "
                        "API instead of today's feed")
    args = p.parse_args()

    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=5, minutes=30)
    day = args.day or ist.strftime("%Y-%m-%d")
    d = datetime.datetime.strptime(day, "%Y-%m-%d").date()

    if args.from_filings:
        found = from_filings(args.from_filings)
        if args.dry_run:
            print()
            print(f"{len(found)} insider filings (nothing written)")
            for r in found[:25]:
                print(f"  {r['filed_on']}  [{r['exchange']}] "
                      f"{r['company'][:22]:<24}{r['headline'][:70]}")
            return 0
        url, token = creds()
        if not (url and token):
            print("No KV credentials, so nothing was stored.")
            return 0
        by_day = {}
        for r in found:
            by_day.setdefault(r["filed_on"], []).append(r)
        store_days(url, token, by_day)
        refresh_index(url, token, by_day.keys())
        print(f"  insider: seeded {len(found)} filings across {len(by_day)} days")
        return 0

    if args.backfill:
        start = d - datetime.timedelta(days=args.backfill - 1)
        syms = symbols_from_site()
        found = insider.fetch_history(syms, start, d)
        found = with_mcap(found)
        if args.dry_run:
            print()
            print(f"{len(found)} trades from {start} to {d} (nothing written)")
            for r in sorted(found, key=lambda x: -(x.get("value") or 0))[:25]:
                print(f"  {r['filed_on']}  {r['company'][:22]:<24}"
                      f"{r['headline'][:88]}")
            return 0
        url, token = creds()
        if not (url and token):
            print("No KV credentials, so nothing was stored.")
            return 0
        by_day = {}
        for r in found:
            by_day.setdefault(r["filed_on"], []).append(r)
        store_days(url, token, by_day)
        refresh_index(url, token, by_day.keys())
        print(f"  insider: backfilled {len(found)} trades across "
              f"{len(by_day)} days")
        return 0

    found = with_mcap(insider.fetch(d, d))
    if args.dry_run:
        print(f"\n{len(found)} trades for {day} (nothing written)")
        for r in found[:25]:
            print(f"  {r['company'][:24]:<26}{r['headline'][:96]}")
        return 0

    url, token = creds()
    if not (url and token):
        print("No KV credentials, so nothing was stored.")
        return 0

    key = f"mt:insider:{day}"
    before = read_day(url, token, key)
    rows, added = merge(before, found)

    # Nothing new and nothing stored means an empty day - before the market
    # opens, or a holiday. Writing an empty day over an empty day is harmless;
    # writing one over a day that has trades is not, and merge() cannot do it.
    write_day(url, token, key, rows)

    raw = redis(url, token, ["GET", "mt:insider:index"])
    try:
        days = json.loads(raw) if raw else []
    except Exception:
        days = []
    days = sorted(set([day] + [x for x in days if isinstance(x, str)]),
                  reverse=True)[:KEEP_DAYS]
    redis(url, token, ["SET", "mt:insider:index",
                       json.dumps(days), "EX", str(TTL_SECONDS)])

    buys = sum(1 for r in rows if (r.get("side") or "").lower() == "buy")
    sells = sum(1 for r in rows if (r.get("side") or "").lower() == "sell")
    redis(url, token, ["SET", "mt:insider:meta", json.dumps({
        "updated": datetime.datetime.now(datetime.timezone.utc)
                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "day": day, "trades": len(rows), "buys": buys, "sells": sells,
        "days": days,
    }), "EX", str(TTL_SECONDS)])

    print(f"  insider: {len(rows)} trades stored for {day} "
          f"({added} new this pass, {buys} buys, {sells} sells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

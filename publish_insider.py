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
import sys

import requests

import insider

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


def trade_key(row):
    """What makes two rows the same trade.

    Not the id: that carries the filing's file name, and a company filing a
    revision produces a new file for a trade already shown.
    """
    return "|".join(str(row.get(k, "")) for k in
                    ("symbol", "who", "shares", "value", "mode", "traded_on"))


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day", help="YYYY-MM-DD; default is today in India")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=5, minutes=30)
    day = args.day or ist.strftime("%Y-%m-%d")
    d = datetime.datetime.strptime(day, "%Y-%m-%d").date()

    found = insider.fetch(d, d)
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

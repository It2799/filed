"""
Bulk and block deals, from the four reports the two exchanges publish.

    NSE  /api/historicalOR/bulk-block-short-deals?optionType=bulk_deals
         ...&optionType=block_deals             - a date range, both work
    BSE  /BulkDeal_Beta/w  and  /BlockDeal_Beta/w    - the latest day only,
         whatever dates it is given, so history builds up a day at a time

A bulk deal is any single client trading more than 0.5% of a company's shares
in a day, reported after the close. A block deal is a negotiated trade of at
least Rs 10 crore done in a separate window, reported the same day. Both are
somebody large taking a position, which is the only reason to read them.

Two things are deliberately thrown away.

INTRADAY. The exchanges report a bulk deal on the way in AND on the way out,
so a trader who bought 18 lakh shares and sold them the same afternoon appears
twice - as a buyer and as a seller - and reads like two large investors
disagreeing about the company. It is one person who ended the day owning
nothing. Every client's rows for one scrip on one day are netted, and if the
net is nothing, the deal is nothing.

SMALL. A bulk deal is 0.5% of a company, and in a company worth Rs 40 crore
that is Rs 20 lakh. Most of the report by row count is penny-stock churn.
"""

import csv
import datetime
import io
import re

import requests

import mcap
import sources

CRORE = 10 ** 7

NSE_DEALS = "https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
NSE_PAGE = "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"
BSE_API = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_HDR = {"User-Agent": mcap.UA, "Referer": "https://www.bseindia.com/",
           "Origin": "https://www.bseindia.com",
           "Accept": "application/json, text/plain, */*"}

# What counts as worth reading.
#
# Rs 25 crore is large in any company on either exchange, so it is kept on its
# own. Below that it has to be large RELATIVE to the company - half a percent
# of the market capitalisation - which is what makes a Rs 3 crore deal in a
# small company news and the same Rs 3 crore in Reliance a rounding error.
#
# When the company could not be matched to a market cap, Rs 5 crore is the
# line. That is the honest middle: it lets through the genuinely large deals
# in companies we could not identify, and keeps out the churn.
BIG_ANYWHERE = 25 * CRORE
NEVER_BELOW = 1 * CRORE
SHARE_OF_COMPANY = 0.005
UNKNOWN_SIZE_FLOOR = 5 * CRORE


def _who(name):
    """The same trader, written two ways, reduced to one key.

    "ANANTHARAMAN JANAKI" and "Anantharaman Janaki ." are one person, and the
    netting below only works if the two meet.
    """
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _date(v, *formats):
    for fmt in formats:
        try:
            return datetime.datetime.strptime(str(v).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _num(v):
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def _nse_session():
    """A session NSE will answer, or a plain one if the handshake failed."""
    s = requests.Session()
    s.headers.update({"User-Agent": sources.UA,
                      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                      "Accept-Language": "en-GB,en;q=0.9"})
    try:
        s.get("https://www.nseindia.com/", timeout=45)
        s.get(NSE_PAGE, timeout=45)
    except Exception:
        pass
    return s


# The CSV, not the JSON. Both live at the same URL.
#
# This is not a preference, it is the difference between a week of deals and
# one day of them. The JSON answer:
#
#   - IGNORES the date range. Asked for 5 to 12 September it returned 70 rows
#     all dated the 7th, and the block report 39 rows all dated the 11th.
#   - CAPS at 70 rows. Every single day asked for on its own came back with
#     exactly 70, which is a page size, not a day's trading. No page, start,
#     length, limit or size parameter moved it.
#
# The same request with csv=true honours the range and returns everything:
# 924 bulk deals across the five trading days where the JSON gave 70 on one.
# Four days out of five had been missing from the site since this was written,
# and the day that did arrive was two thirds short.
#
# The CSV column names are the human ones, so they are mapped rather than
# guessed at, and both spellings of each are accepted - NSE has changed the
# header text before.
_NSE_CSV_COLS = {
    "date": ("date",),
    "symbol": ("symbol",),
    "company": ("security name", "securityname", "security"),
    "who": ("client name", "clientname", "client"),
    "side": ("buy / sell", "buy/sell", "buysell"),
    "qty": ("quantity traded", "quantitytraded", "quantity"),
    "price": ("trade price / wght. avg. price", "trade price",
              "tradeprice", "price"),
    "remarks": ("remarks",),
}


def _nse_col_map(fieldnames):
    """Header text -> the field we want, however NSE has spelled it today."""
    found = {}
    for raw in fieldnames or []:
        key = (raw or "").strip().lower()
        squashed = key.replace(" ", "")
        for want, spellings in _NSE_CSV_COLS.items():
            if key in spellings or squashed in spellings:
                found[want] = raw
                break
    return found


def fetch_nse(from_date, to_date, log=print, session=None):
    """Both NSE reports, over a date range that is actually honoured."""
    s = session or _nse_session()
    hdr = {"Accept": "*/*", "Referer": NSE_PAGE,
           "X-Requested-With": "XMLHttpRequest"}
    fmt = "%d-%m-%Y"
    out = []
    for kind, option in (("Bulk", "bulk_deals"), ("Block", "block_deals")):
        try:
            r = s.get(NSE_DEALS, timeout=90, headers=hdr,
                      params={"optionType": option,
                              "from": from_date.strftime(fmt),
                              "to": to_date.strftime(fmt),
                              "csv": "true"})
            text = r.content.decode("utf-8-sig", "replace")
            reader = csv.DictReader(io.StringIO(text))
            col = _nse_col_map(reader.fieldnames)
            if not {"date", "who", "qty", "price"} <= set(col):
                log(f"  deals NSE {kind}: unexpected columns "
                    f"{reader.fieldnames}")
                continue
            rows = list(reader)
        except Exception as e:
            log(f"  deals NSE {kind}: {type(e).__name__}: {e}")
            continue

        def get(row, want):
            name = col.get(want)
            return (row.get(name) or "").strip() if name else ""

        kept = 0
        for row in rows:
            day = _date(get(row, "date"), "%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y")
            if not day:
                continue
            qty = _num(get(row, "qty"))
            price = _num(get(row, "price"))
            out.append({
                "day": str(day), "kind": kind, "exchange": "NSE",
                "symbol": get(row, "symbol"), "scrip": "",
                "company": get(row, "company"),
                "who": get(row, "who"),
                "side": ("Buy" if get(row, "side").upper().startswith("B")
                         else "Sell"),
                "shares": qty, "price": price, "value": qty * price,
                "remarks": get(row, "remarks").strip(" -") or "",
            })
            kept += 1
        days = len({r["day"] for r in out if r["kind"] == kind})
        log(f"  deals NSE {kind}: {kept} rows across {days} days")
    return out


def fetch_bse(log=print, session=None):
    """Both BSE reports. The latest trading day only - see the module note."""
    s = session or requests.Session()
    out = []
    for kind, endpoint in (("Bulk", "BulkDeal_Beta"),
                           ("Block", "BlockDeal_Beta")):
        try:
            r = s.get(f"{BSE_API}/{endpoint}/w", timeout=45, headers=BSE_HDR,
                      params={"pageno": 1, "scripcode": "", "flag": 1,
                              "Fdate": "", "Tdate": ""})
            rows = (r.json() or {}).get("Table") or []
        except Exception as e:
            log(f"  deals BSE {kind}: {type(e).__name__}: {e}")
            continue
        for row in rows:
            day = _date(row.get("DEAL_DATE"), "%d/%m/%Y", "%Y-%m-%d")
            if not day:
                continue
            qty = _num(row.get("QUANTITY"))
            price = _num(row.get("PRICE"))
            out.append({
                "day": str(day), "kind": kind, "exchange": "BSE",
                "symbol": (row.get("ScripName") or "").strip(),
                "scrip": str(row.get("SCRIP_CODE") or "").strip(),
                "company": (row.get("ScripName") or "").strip(),
                "who": (row.get("CLIENT_NAME") or "").strip(),
                "side": ("Buy" if (row.get("TRANSACTION_TYPE") or "").strip()
                         .upper().startswith("B") else "Sell"),
                "shares": qty, "price": price, "value": qty * price,
                "remarks": "",
            })
        log(f"  deals BSE {kind}: {len(rows)} rows")
    return out


# How much of a round trip still counts as a round trip.
#
# Not zero. A trader who buys 10,00,000 and sells 9,99,000 has taken a position
# in nothing; the 1,000 left over is an artefact of how the day filled, not a
# view on the company.
ROUND_TRIP = 0.02


# The same trade, printed in both reports.
#
# A block deal is a negotiated trade in its own window; a bulk deal is any
# client crossing 0.5% of a company in a day. A block deal that big is BOTH,
# so the exchange prints it twice - once in each report, same client, same
# day, same quantity, same price. Twelve of them in one week.
#
# Counted twice, Granules on 11 September read as the promoter selling
# Rs 1,160 crore in a block AND another Rs 1,160 crore in bulk. He sold it
# once.
#
# The bulk report is the one kept, because it is the day's whole position for
# that client - the block window plus anything else they did. The block row is
# dropped and the bulk row remembers it came through the block window, which
# is the part worth saying.
def drop_double_reported(rows, log=print):
    """Remove the block row when the bulk report already carries that trade."""
    bulk = {}
    for r in rows:
        if r["kind"] != "Bulk":
            continue
        key = (r["day"], r["exchange"], r["symbol"] or r["scrip"],
               _who(r["who"]), r["side"], round(r["shares"]),
               round(r["price"], 2))
        bulk[key] = r

    out, dropped = [], 0
    for r in rows:
        if r["kind"] == "Block":
            key = (r["day"], r["exchange"], r["symbol"] or r["scrip"],
                   _who(r["who"]), r["side"], round(r["shares"]),
                   round(r["price"], 2))
            twin = bulk.get(key)
            if twin is not None:
                twin["via_block"] = True
                dropped += 1
                continue
        out.append(r)

    if dropped:
        log(f"  deals: {dropped} block rows already in the bulk report")
    return out


def net_out_intraday(rows, log=print):
    """One row per client per scrip per day, with the day trade taken out."""
    groups = {}
    for r in rows:
        key = (r["day"], r["exchange"], r["kind"],
               r["symbol"] or r["scrip"], _who(r["who"]))
        groups.setdefault(key, []).append(r)

    out, dropped, netted = [], 0, 0
    for part in groups.values():
        buys = [r for r in part if r["side"] == "Buy"]
        sells = [r for r in part if r["side"] == "Sell"]
        bq = sum(r["shares"] for r in buys)
        sq = sum(r["shares"] for r in sells)
        bv = sum(r["value"] for r in buys)
        sv = sum(r["value"] for r in sells)

        net = bq - sq
        if bq and sq and abs(net) <= ROUND_TRIP * max(bq, sq):
            dropped += 1
            continue

        keep = buys if net > 0 else sells
        gross_q, gross_v = (bq, bv) if net > 0 else (sq, sv)
        shares = abs(net)
        price = (gross_v / gross_q) if gross_q else 0.0

        row = dict(keep[0] if keep else part[0])
        row.update({
            "side": "Buy" if net > 0 else "Sell",
            "shares": shares,
            "price": round(price, 2),
            "value": shares * price,
            "rows": len(part),
            "netted": bool(bq and sq),
            "gross_buy": bq,
            "gross_sell": sq,
            # True when any part of this position came through the block
            # window. Worth saying: a block is negotiated off the order book.
            "via_block": any(r.get("via_block") for r in part),
        })
        if row["netted"]:
            netted += 1
        out.append(row)

    log(f"  deals: {len(rows)} reported rows -> {len(out)} positions "
        f"({dropped} pure day trades dropped, {netted} netted)")
    return out


def important(row):
    """Is this deal large enough to be worth a reader's time?"""
    value = row.get("value") or 0
    if value >= BIG_ANYWHERE:
        return True
    if value < NEVER_BELOW:
        return False
    size = (row.get("mcap") or 0) * CRORE
    if size:
        return value >= SHARE_OF_COMPANY * size
    return value >= UNKNOWN_SIZE_FLOOR


def deal_id(row):
    """Stable across runs, so the same deal is stored once."""
    who = _who(row.get("who"))[:20]
    code = re.sub(r"[^A-Za-z0-9]", "",
                  row.get("symbol") or row.get("scrip") or "")[:12]
    return "-".join(["DL", row["day"], row["exchange"][:1],
                     row["kind"][:2], code, who, row["side"][:1]])


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
    if v >= CRORE:
        return f"Rs {v / CRORE:,.2f} crore"
    if v >= 10 ** 5:
        return f"Rs {v / 10 ** 5:,.2f} lakh"
    return "Rs " + _indian(round(v))


def _each(price):
    """A share price, with the paise where a reader would look for them."""
    price = float(price or 0)
    if not price:
        return ""
    if price < 1000:
        return f"Rs {price:,.2f}"
    return "Rs " + _indian(round(price))


def headline(row):
    """One sentence, written the way the insider page writes one.

    Same two habits: lakhs and crores rather than a nine-digit number, and
    digits grouped 78,12,500 rather than 7,812,500, because that is how
    everybody who will read this writes it.
    """
    verb = "bought" if row["side"] == "Buy" else "sold"
    who = (row.get("who") or "").strip() or "A large investor"
    text = f"{who} {verb} {_indian(row.get('shares'))} shares"
    if row.get("company"):
        text += f" of {row['company']}"
    each = _each(row.get("price"))
    if each:
        text += f" at {each} each"
    if row.get("value"):
        text += f" - {_rupees(row['value'])} in all"
    text += "."
    if row.get("netted"):
        gross = (row.get("gross_sell") if row["side"] == "Buy"
                 else row.get("gross_buy"))
        other = "sold" if row["side"] == "Buy" else "bought"
        # Only when we know the other side's size. A netted row with no figure
        # for it would read "also sold 0 shares", which is worse than silence.
        if gross:
            text += (f" This is the net: they also {other} "
                     f"{_indian(gross)} shares the same day.")
        else:
            text += " This is the net of the same day's trades on both sides."
    return text


def fetch(from_date, to_date, log=print):
    """Every bulk and block deal worth reading in the window."""
    rows = fetch_nse(from_date, to_date, log=log) + fetch_bse(log=log)
    rows = [r for r in rows
            if from_date <= datetime.date.fromisoformat(r["day"]) <= to_date]
    # Before netting: a trade printed in both reports must not be netted as
    # two separate positions and then shown twice.
    rows = drop_double_reported(rows, log=log)
    rows = net_out_intraday(rows, log=log)

    # Market cap before the filter, because the filter is mostly about it.
    # BSE rows carry the scrip code, which mcap looks up directly; NSE rows
    # are matched on the company name.
    for r in rows:
        r["ticker"] = r.get("scrip") or ""
    mcap.attach(rows, log=log)

    kept = [r for r in rows if important(r)]
    for r in kept:
        r["id"] = deal_id(r)
        r["headline"] = headline(r)
    log(f"  deals: {len(kept)} of {len(rows)} positions are worth showing")
    return sorted(kept, key=lambda r: -(r.get("value") or 0))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--show", type=int, default=30)
    a = ap.parse_args()
    today = datetime.date.today()
    found = fetch(today - datetime.timedelta(days=a.days - 1), today)
    print()
    for r in found[:a.show]:
        print(f"  {r['day']}  {r['exchange']} {r['kind']:<5} "
              f"Rs {r['value'] / CRORE:>8,.1f} cr  {r['headline'][:96]}")

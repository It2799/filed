"""
Checks for the bulk and block deal reader.

Run:  python tests/test_deals.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deals                                               # noqa: E402

CHECKS = [0]
FAILURES = []
CRORE = deals.CRORE


def check(ok, what, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(f"{what}\n      {detail}" if detail else what)


def row(**kw):
    base = {"day": "2026-09-11", "kind": "Bulk", "exchange": "NSE",
            "symbol": "ACME", "scrip": "", "company": "Acme Ltd",
            "who": "A TRADER", "side": "Buy", "shares": 0.0, "price": 0.0,
            "value": 0.0, "remarks": ""}
    base.update(kw)
    if not base["value"]:
        base["value"] = base["shares"] * base["price"]
    return base


# ---------------------------------------------------------------------------
# 1. The day trade Ishan asked to be left out
#
# The exchanges report a bulk deal on the way in AND on the way out. On
# 7 September, MICROCURVES TRADING PRIVATE LIMITED appears in NSE's report
# twice for ANDHRA PAPER: bought 18,18,411 at Rs 73.88, sold 18,18,411 at
# Rs 73.95. Read as filed, that is two large investors taking opposite views
# of the same company on the same day. It is one trader who went home flat.
# ---------------------------------------------------------------------------

ROUND_TRIP = [
    row(symbol="ANDHRAPAP", company="ANDHRA PAPER LIMITED",
        who="MICROCURVES TRADING PRIVATE LIMITED", side="Buy",
        shares=1818411, price=73.88),
    row(symbol="ANDHRAPAP", company="ANDHRA PAPER LIMITED",
        who="MICROCURVES TRADING PRIVATE LIMITED", side="Sell",
        shares=1818411, price=73.95),
]
out = deals.net_out_intraday(ROUND_TRIP, log=lambda *a: None)
check(out == [], "a pure day trade survived the netting", f"{len(out)} rows")

# Nearly flat is still flat. Buying 10,00,000 and selling 9,99,000 leaves a
# position in nothing; the 1,000 is an artefact of how the day filled.
NEARLY_FLAT = [
    row(who="SOMEBODY", side="Buy", shares=1000000, price=100.0),
    row(who="SOMEBODY", side="Sell", shares=999000, price=100.2),
]
out = deals.net_out_intraday(NEARLY_FLAT, log=lambda *a: None)
check(out == [], "a near-flat round trip was kept", f"{len(out)} rows")

# A real position that happened to have a sale in it is NOT a day trade. The
# net is what the investor actually did.
ACCUMULATED = [
    row(who="A FUND", side="Buy", shares=1000000, price=100.0),
    row(who="A FUND", side="Sell", shares=100000, price=101.0),
]
out = deals.net_out_intraday(ACCUMULATED, log=lambda *a: None)
check(len(out) == 1, "a net purchase was dropped as a day trade", f"{out}")
if out:
    check(out[0]["side"] == "Buy", "the net came out on the wrong side")
    check(out[0]["shares"] == 900000,
          "the net quantity is wrong", str(out[0]["shares"]))
    check(out[0]["netted"] is True,
          "a netted row did not say it had been netted")
    check(out[0]["gross_sell"] == 100000,
          "the gross sale was lost", str(out[0].get("gross_sell")))

# The same investor written two ways is one investor. Netting is the whole
# feature, and it only works if the names meet.
SPELLED_TWO_WAYS = [
    row(who="ANANTHARAMAN JANAKI", side="Buy", shares=500000, price=10.0),
    row(who="Anantharaman Janaki .", side="Sell", shares=500000, price=10.1),
]
out = deals.net_out_intraday(SPELLED_TWO_WAYS, log=lambda *a: None)
check(out == [], "the same trader spelled two ways was not matched", f"{out}")

# Different people trading the same scrip on the same day are NOT a round
# trip. A block deal is a buyer and a seller by definition - Abakkus bought
# 27 lakh BlackBuck shares from Accel on 11 September - and netting those two
# together would delete the deal.
TWO_PEOPLE = [
    row(kind="Block", symbol="BLACKBUCK", company="BLACKBUCK LIMITED",
        who="ABAKKUS INVESTMENT MANAGERS PRIVATE LIMITED", side="Buy",
        shares=2700000, price=576.05),
    row(kind="Block", symbol="BLACKBUCK", company="BLACKBUCK LIMITED",
        who="ACCEL INDIA IV (MAURITIUS) LIMITED", side="Sell",
        shares=2700000, price=576.05),
]
out = deals.net_out_intraday(TWO_PEOPLE, log=lambda *a: None)
check(len(out) == 2, "a block deal's two sides were netted against each other",
      f"{len(out)} rows")

# Nor are the same person's trades on two different days, or in two different
# companies, or on two different exchanges.
SEPARATE = [
    row(day="2026-09-10", side="Buy", shares=100000, price=100.0),
    row(day="2026-09-11", side="Sell", shares=100000, price=100.0),
    row(symbol="OTHER", company="Other Ltd", side="Buy", shares=100000, price=100.0),
    row(exchange="BSE", scrip="500001", side="Sell", shares=100000, price=100.0),
]
out = deals.net_out_intraday(SEPARATE, log=lambda *a: None)
check(len(out) == 4, "unrelated deals were netted together", f"{len(out)} rows")

# The price kept is the weighted average of the side that survived, not the
# first row's price.
SPLIT_FILL = [
    row(who="A FUND", side="Buy", shares=100000, price=100.0),
    row(who="A FUND", side="Buy", shares=300000, price=200.0),
]
out = deals.net_out_intraday(SPLIT_FILL, log=lambda *a: None)
check(len(out) == 1 and out[0]["shares"] == 400000,
      "two fills of one purchase were not combined", f"{out}")
if out:
    check(abs(out[0]["price"] - 175.0) < 0.01,
          "the combined price is not the weighted average",
          str(out[0]["price"]))
    check(out[0]["netted"] is False,
          "a purchase with no sale in it was marked as netted")


# ---------------------------------------------------------------------------
# 2. "Only which are imp"
#
# A bulk deal is 0.5% of a company. In a company worth Rs 40 crore that is
# Rs 20 lakh, and most of the report by row count is exactly that. What makes
# a deal worth reading is its size relative to the company - which is why the
# market cap is fetched BEFORE the filter rather than for display.
# ---------------------------------------------------------------------------

check(deals.important({"value": 300 * CRORE}),
      "a Rs 300 crore deal was filtered out")
check(deals.important({"value": 26 * CRORE, "mcap": 200000}),
      "a Rs 26 crore deal was filtered out even in a huge company")
check(not deals.important({"value": 20 * 100000}),
      "a Rs 20 lakh deal was kept")

# Relative to the company is the point.
check(deals.important({"value": 3 * CRORE, "mcap": 100}),
      "Rs 3 crore in a Rs 100 crore company was filtered out")
check(not deals.important({"value": 3 * CRORE, "mcap": 200000}),
      "Rs 3 crore in a Rs 2 lakh crore company was kept")

# And when we could not identify the company, Rs 5 crore is the line.
check(deals.important({"value": 6 * CRORE}),
      "Rs 6 crore with no known company size was filtered out")
check(not deals.important({"value": 4 * CRORE}),
      "Rs 4 crore with no known company size was kept")

# Nothing under Rs 1 crore, however small the company. A market cap we
# matched wrongly must not be able to let through a trivial trade.
check(not deals.important({"value": 50000, "mcap": 1}),
      "a Rs 50,000 trade was kept because the company looked tiny")


# ---------------------------------------------------------------------------
# 3. Reading each exchange's own words
#
# NSE says BUY/SELL in BD_BUY_SELL; BSE says B/S in TRANSACTION_TYPE. Both
# have to come out as the same word or the page's filters lie.
# ---------------------------------------------------------------------------

check(deals._who("ANANTHARAMAN JANAKI") == deals._who("Anantharaman Janaki ."),
      "name flattening is not doing its job")
check(deals._who("") == "", "an empty name did not flatten to nothing")

check(deals._date("07-SEP-2026", "%d-%b-%Y").isoformat() == "2026-09-07",
      "NSE's date format was not read")
check(deals._date("11/09/2026", "%d/%m/%Y").isoformat() == "2026-09-11",
      "BSE's date format was not read")
check(deals._date("rubbish", "%d/%m/%Y") is None,
      "a bad date did not come back as nothing")

check(deals._num("1,818,411") == 1818411, "a number with commas was not read")
check(deals._num("") == 0, "an empty number was not read as zero")
check(deals._num("-") == 0, "a dash was not read as zero")


# ---------------------------------------------------------------------------
# 4. One deal, one row, however many times it is read
#
# BSE hands over the same day again on every pass, so the id has to be the
# same each time or a day would grow a copy of itself every half hour.
# ---------------------------------------------------------------------------

a = row(who="ABAKKUS INVESTMENT MANAGERS PRIVATE LIMITED", side="Buy",
        shares=2700000, price=576.05)
b = row(who="Abakkus Investment Managers Private Limited", side="Buy",
        shares=2700000, price=576.10)
check(deals.deal_id(a) == deals.deal_id(b),
      "the same deal read twice produced two ids",
      f"{deals.deal_id(a)}\n      {deals.deal_id(b)}")

c = row(who="ABAKKUS INVESTMENT MANAGERS PRIVATE LIMITED", side="Sell",
        shares=2700000, price=576.05)
check(deals.deal_id(a) != deals.deal_id(c),
      "a buy and a sell by the same investor share an id")


# ---------------------------------------------------------------------------
# 5. A sentence a person can read
# ---------------------------------------------------------------------------

said = deals.headline(row(who="DSP MUTUAL FUND", company="Jamna Auto Ind Ltd",
                          side="Buy", shares=7812500, price=128.0))
# 78,12,500, not 7,812,500. That is how everybody who will read this writes it.
check("DSP MUTUAL FUND bought 78,12,500 shares" in said,
      "the headline does not say who did what, in Indian digits", said)
check("Jamna Auto" in said and "Rs 128.00 each" in said,
      "the headline lost the company or the price each", said)
check("Rs 100.00 crore in all" in said,
      "the headline did not put the total in crores", said)

check(deals._indian(7812500) == "78,12,500",
      "digits are not grouped the Indian way", deals._indian(7812500))
check(deals._rupees(1160000000) == "Rs 116.00 crore",
      "a crore was not written as a crore", deals._rupees(1160000000))
check(deals._each(872.5) == "Rs 872.50",
      "a block price lost its paise", deals._each(872.5))
check(deals._each(2651) == "Rs 2,651",
      "a four-figure price kept pointless paise", deals._each(2651))

netted = deals.headline(row(who="A FUND", side="Buy", shares=900000,
                            price=100.0, netted=True, gross_sell=100000))
check("also sold 1,00,000 shares the same day" in netted,
      "a netted row does not say what was sold the same day", netted)

# ...and when the other side's size is missing, it must not say "0 shares".
vague = deals.headline(row(who="A FUND", side="Buy", shares=900000,
                           price=100.0, netted=True))
check(" 0 shares" not in vague,
      "a netted row with no figure claimed zero shares", vague)
check("net" in vague.lower(),
      "a netted row did not say it had been netted", vague)


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 5. The same trade, printed in both reports
#
# A block deal is a negotiated trade in its own window; a bulk deal is any
# client crossing 0.5% of a company in a day. A block that big is BOTH, so the
# exchange prints it twice - same client, same day, same quantity, same price.
# Twelve of them in the week of 7 September.
#
# Counted twice, Granules read as the promoter selling Rs 1,160 crore in a
# block AND another Rs 1,160 crore in bulk. He sold it once.
# ---------------------------------------------------------------------------

BOTH_REPORTS = [
    row(kind="Bulk", symbol="GRANULES", company="Granules India Limited",
        who="KRISHNA PRASAD CHIGURUPATI", side="Sell",
        shares=13295129, price=872.50),
    row(kind="Block", symbol="GRANULES", company="Granules India Limited",
        who="KRISHNA PRASAD CHIGURUPATI", side="Sell",
        shares=13295129, price=872.50),
]
out = deals.drop_double_reported(BOTH_REPORTS, log=lambda *a: None)
check(len(out) == 1, "a trade printed in both reports was counted twice",
      f"{len(out)} rows")
if out:
    check(out[0]["kind"] == "Bulk",
          "the wrong report survived - bulk is the day's whole position",
          out[0]["kind"])
    check(out[0].get("via_block") is True,
          "the surviving row forgot it came through the block window")

# A block deal by somebody who did NOT cross the bulk threshold has no twin,
# and must be kept.
ONLY_BLOCK = [
    row(kind="Block", symbol="ACME", who="A FUND", side="Buy",
        shares=500000, price=100.0),
]
out = deals.drop_double_reported(ONLY_BLOCK, log=lambda *a: None)
check(len(out) == 1, "a block deal with no bulk twin was thrown away")

# Same client and scrip, DIFFERENT quantity, is not the same trade.
DIFFERENT = [
    row(kind="Bulk", symbol="ACME", who="A FUND", side="Buy",
        shares=500000, price=100.0),
    row(kind="Block", symbol="ACME", who="A FUND", side="Buy",
        shares=300000, price=100.0),
]
out = deals.drop_double_reported(DIFFERENT, log=lambda *a: None)
check(len(out) == 2, "two different trades were collapsed into one",
      f"{len(out)} rows")

# Opposite sides are not the same trade either.
OPPOSITE = [
    row(kind="Bulk", symbol="ACME", who="A FUND", side="Buy",
        shares=500000, price=100.0),
    row(kind="Block", symbol="ACME", who="A FUND", side="Sell",
        shares=500000, price=100.0),
]
out = deals.drop_double_reported(OPPOSITE, log=lambda *a: None)
check(len(out) == 2, "a buy and a sell were treated as one trade",
      f"{len(out)} rows")

# And the flag survives netting, because that is where the row a reader sees
# is actually built.
NETTED = deals.net_out_intraday(
    deals.drop_double_reported(BOTH_REPORTS, log=lambda *a: None),
    log=lambda *a: None)
check(len(NETTED) == 1 and NETTED[0].get("via_block") is True,
      "the block-window flag was lost in netting", str(NETTED))


# ---------------------------------------------------------------------------
# 6. NSE's CSV columns
#
# The JSON answer ignores the date range and caps at 70 rows - asked for five
# days it returned 70 rows from one of them, and four days were missing from
# the site entirely. The CSV at the same URL honours the range: 924 bulk deals
# across those five days.
#
# Its headers are the human ones, and NSE has reworded them before, so the
# mapping is pinned here rather than trusted.
# ---------------------------------------------------------------------------

TODAYS_HEADERS = ["Date", "Symbol", "Security Name", "Client Name",
                  "Buy / Sell", "Quantity Traded",
                  "Trade Price / Wght. Avg. Price", "Remarks"]
col = deals._nse_col_map(TODAYS_HEADERS)
for want, header in [("date", "Date"), ("symbol", "Symbol"),
                     ("company", "Security Name"), ("who", "Client Name"),
                     ("side", "Buy / Sell"), ("qty", "Quantity Traded"),
                     ("price", "Trade Price / Wght. Avg. Price"),
                     ("remarks", "Remarks")]:
    check(col.get(want) == header,
          f"the CSV column for {want!r} was not recognised", str(col))

# Spacing and case are NSE's to change; the meaning is not.
col = deals._nse_col_map(["DATE", "symbol", "SECURITYNAME", "clientname",
                          "Buy/Sell", "quantitytraded", "TRADEPRICE",
                          "REMARKS"])
check({"date", "symbol", "company", "who", "side", "qty", "price"}
      <= set(col),
      "a respaced header row was not understood", str(col))

# A header row we do not recognise must be reported, not silently read as
# empty rows - that is how four days of deals went missing quietly.
check(not ({"date", "who", "qty", "price"}
           <= set(deals._nse_col_map(["a", "b", "c"]))),
      "an unrecognisable header row looked fine")


print(f"{CHECKS[0]} checks")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED\n")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("all pass")

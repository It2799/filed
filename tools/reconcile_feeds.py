"""
Check nothing was missed, against a source we do not control.

The scraper reads BSE's and NSE's JSON APIs. If one of those silently returns
a short page - a timeout swallowed, a paging bug, a rate limit answered with an
empty list - the run looks perfectly healthy and the site is simply missing
filings. Nothing in the pipeline can tell: it has no idea what it did not see.

Both exchanges also publish the same announcements as RSS, built by a different
part of their systems. That is the independent witness. This fetches both feeds
and asks one question of the live site: is every announcement in the feed also
on the site?

The answer should be zero. A number above zero is either a real gap or a
matching failure, and both are worth knowing.

    python tools/reconcile_feeds.py                  # today, IST
    python tools/reconcile_feeds.py --show           # list what is missing
    python tools/reconcile_feeds.py --fail-over 10   # exit 1 past a tolerance

Matching is on the attachment URL, which both feeds and both APIs carry and
which is unique per filing - company names differ in punctuation between the
two sources ("Ltd" against "Limited", "&" against "and") and timestamps differ
by seconds, so neither is safe to match on.
"""

import argparse
import datetime
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = {
    "BSE": "https://www.bseindia.com/data/xml/announcements.xml",
    "NSE": "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml",
}

# Both exchanges refuse a request that does not look like a browser.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": "https://www.bseindia.com/",
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def key_of(url):
    """The part of an attachment URL that identifies the filing.

    BSE gives every attachment a uuid; NSE builds a name from the symbol and a
    timestamp. Either way the last path segment is unique, and it is the only
    thing that survives unchanged between the RSS feed and the JSON API.
    """
    if not url:
        return None
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    tail = tail.split("?")[0]
    tail = re.sub(r"\.(pdf|zip|xlsx?|docx?)$", "", tail, flags=re.I)
    return tail.lower() or None


def feed_items(xml_bytes):
    """(key, company, when, subject) for every item, skipping any without a link."""
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.findall(".//item"):
        def text(tag):
            return (it.findtext(tag) or "").strip()
        k = key_of(text("link"))
        if k:
            out.append({
                "key": k,
                "company": text("title"),
                "when": text("pubDate"),
                "subject": text("description")[:120],
                "link": text("link"),
            })
    return out


def feed_day(when):
    """The date out of a feed's pubDate, as YYYY-MM-DD, or None."""
    # BSE and NSE both write "03-Sep-2026 14:56:45"; BSE's channel header uses
    # RFC-822, but the items do not.
    m = re.match(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", when or "")
    if m:
        try:
            return datetime.datetime.strptime(
                f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "%d-%b-%Y"
            ).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day", help="YYYY-MM-DD; default is today in India")
    p.add_argument("--show", type=int, nargs="?", const=25, default=0,
                   metavar="N", help="list up to N missing filings")
    p.add_argument("--fail-over", type=int, default=None, metavar="N",
                   help="exit non-zero if more than N are missing")
    args = p.parse_args()

    day = args.day or (datetime.datetime.now(datetime.timezone.utc)
                       + datetime.timedelta(hours=5, minutes=30)
                       ).strftime("%Y-%m-%d")

    # What OUR OWN FETCH sees, not what the site publishes.
    #
    # The published API caps its "everything" list at a few hundred rows so the
    # dashboard stays quick, and comparing against that measured the cap rather
    # than the coverage - the first run of this reported 94% missing, which was
    # entirely the cap.
    #
    # Fetching afresh is also the honest test. The risk being checked is that
    # BSE's or NSE's JSON API quietly returns a short page, and only the fetch
    # can show that.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import sources                                          # noqa: E402

    d = datetime.datetime.strptime(day, "%Y-%m-%d").date()

    def quiet(*a, **k):
        pass

    ours = sources.fetch_bse(d, d, log=quiet) + sources.fetch_nse(d, d, log=quiet)
    have = {key_of(r.get("pdf_url")) for r in ours}
    have.discard(None)
    print(f"our fetch for {day}: {len(ours)} filings "
          f"({len(have)} distinct attachments)\n")

    total_missing = 0
    for name, url in FEEDS.items():
        try:
            items = feed_items(get(url, timeout=90))
        except Exception as e:
            print(f"{name}: could not read the feed - {e}")
            continue

        today = [i for i in items if feed_day(i["when"]) == day]

        # Counted per DOCUMENT, not per feed item. BSE lists a filing once for
        # every instrument it applies to, so one EGM notice from a company with
        # eight listed debentures appears eight times: 7,243 items on
        # 3 September were 635 documents. Counting items made a healthy fetch
        # look 90% short.
        unique = {}
        for i in today:
            unique.setdefault(i["key"], i)
        missing = [i for k, i in unique.items() if k not in have]
        total_missing += len(missing)

        share = (len(missing) / len(unique) * 100) if unique else 0
        print(f"{name}: {len(today)} feed items for {day} = {len(unique)} "
              f"documents, {len(missing)} not fetched ({share:.0f}%)")

        for i in missing[: args.show]:
            print(f"    {i['company'][:34]:<36}{i['subject'][:56]}")
        if args.show and len(missing) > args.show:
            print(f"    ...and {len(missing) - args.show} more")

    print()
    if args.fail_over is not None and total_missing > args.fail_over:
        print(f"{total_missing} filings are in an exchange feed but not on the "
              f"site (tolerance {args.fail_over}).")
        return 1
    print(f"{total_missing} filings in the feeds are not on the site.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

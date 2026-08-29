"""
Check the live site is actually sane. Runs after every scrape.

Every bug that reached the dashboard so far would have been caught by one of
these. They are deliberately blunt assertions about things a user would notice
within seconds - how many days are showing, whether a category you can click
actually returns anything, whether the numbers on the page add up.

    python tools/verify_live.py [--url https://...]

Exits non-zero if anything is wrong, so a scheduled run fails loudly instead of
quietly publishing a broken dashboard.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

DEFAULT_URL = "https://filed-omega.vercel.app"
EXPECT_DAYS = 7

fails, warns = [], []


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "market-tide-verify"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def check(ok, label, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)
    return ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    args = p.parse_args()
    base = args.url.rstrip("/")

    print(f"Verifying {base}\n")

    # ---- the pages load at all --------------------------------------------
    print("PAGES")
    for path in ("", "/dashboard", "/join", "/terms", "/refund", "/privacy", "/contact"):
        try:
            req = urllib.request.Request(base + path,
                                         headers={"User-Agent": "market-tide-verify"})
            with urllib.request.urlopen(req, timeout=45) as r:
                code = r.status
        except Exception as e:
            code = getattr(e, "code", 0)
        check(code == 200, f"{path or '/'} responds", f"HTTP {code}")

    # ---- the data ---------------------------------------------------------
    print("\nDATA")
    try:
        d = get(f"{base}/api/announcements?scope=important")
    except Exception as e:
        print(f"  [FAIL] the API did not answer: {e}")
        sys.exit(1)

    days = d.get("days") or []
    check(len(days) >= EXPECT_DAYS, f"{EXPECT_DAYS} days are listed",
          f"got {len(days)}: {days}")

    total = d.get("total") or 0
    check(total > 0, "there are filings to show", f"total={total}")

    summarised = d.get("summarised") or 0
    check(summarised > 0, "filings carry summaries",
          f"{summarised}/{total} summarised")

    # The window must be seven consecutive dates ending today. A weekend day
    # with no filings still belongs in it - dropping it would quietly shorten
    # the window - but a gap in the middle means a day failed to scrape.
    if days:
        import datetime
        got = sorted(days, reverse=True)
        expected = [(datetime.date.fromisoformat(got[0]) - datetime.timedelta(days=i))
                    .isoformat() for i in range(EXPECT_DAYS)]
        check(got[:EXPECT_DAYS] == expected, "the days are consecutive, no gaps",
              f"got {got[:EXPECT_DAYS]}")

        per_day = {}
        for it in d.get("items", []):
            per_day[it.get("day")] = per_day.get(it.get("day"), 0) + 1
        with_filings = sum(1 for x in days if per_day.get(x, 0) > 0)
        check(with_filings >= 4, "most days actually hold filings",
              f"{with_filings}/{len(days)} days have filings")

    # ---- every category you can click must actually return something ------
    print("\nCATEGORIES")
    counts = d.get("tagCounts") or {}
    check(len(counts) > 5, "categories are present", f"{len(counts)} categories")

    broken = []
    for tag, n in sorted(counts.items(), key=lambda x: -x[1])[:12]:
        try:
            r = get(f"{base}/api/announcements?scope=important&tag="
                    + urllib.parse.quote(tag), timeout=45)
            served = r.get("count", 0)
            if served != n:
                broken.append(f"{tag} says {n} serves {served}")
        except Exception as e:
            broken.append(f"{tag} errored: {e}")
    check(not broken, "sidebar counts match what each category serves",
          "; ".join(broken) if broken else "")

    # ---- freshness --------------------------------------------------------
    print("\nFRESHNESS")
    updated = (d.get("meta") or {}).get("updated")
    check(bool(updated), "the store records when it last ran", str(updated))

    print()
    if fails:
        print(f"{len(fails)} CHECK(S) FAILED: {fails}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()

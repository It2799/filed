"""The morning brief: one PDF, the fifty filings worth knowing about.

Reads the same data the website serves and covers everything filed from the
start of yesterday up to 06:45 this morning, so an announcement made overnight
reaches the reader at breakfast rather than a day later. The issue goes out at
07:30 IST.

Left out: concalls, investor presentations and investor meets (a diary entry is
not news), and dividends and splits (routine, and frequent enough to crowd out
everything else). What remains is picked across categories so one busy results
day cannot fill the whole issue.

    python newsletter.py                    # today's issue
    python newsletter.py --day 2026-09-01   # rebuild a particular issue
    python newsletter.py --count 30
    python newsletter.py --html-only        # skip the PDF step
    python newsletter.py --publish          # put it on the site

The PDF is printed by headless Chrome, which every runner already has and
which is the only renderer that makes CSS look the way a browser does.
"""

import argparse
import datetime
import html
import json
import os
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "brief")
API = "https://markettide.in/api/announcements?scope=important"

# A call, a slide deck and a meeting invitation are things an investor puts in
# a diary, not things that happened. Dividends and splits are left out too -
# they are routine enough, and frequent enough, to crowd out the news.
SKIP_TAGS = {"Concall", "Investor Presentation", "Investor Meet",
             "Dividend", "Split"}

# The issue goes out at 7:30am IST and covers everything filed since the start
# of yesterday up to 06:45 that morning - so an announcement made overnight is
# in the reader's hands at breakfast rather than a day later.
CUTOFF_HOUR, CUTOFF_MIN = 6, 45

# The order sections appear in. Anything not named here follows, alphabetically.
SECTION_ORDER = [
    "Results", "Acquisition", "Scheme Of Arrangement", "Order", "Buyback",
    "Bonus", "Rights Issue", "Open Offer", "Delisting",
    "Qip", "Qip Allotment", "Pref", "Warrants", "Fund Raising",
    "Capacity Increase", "Business Update", "Operations", "Ratings Update",
    "Nclt", "Legal/Reg", "Change In Management",
]

# The same details as web/app/site.js. Kept here rather than imported because
# that file is JavaScript; if one changes, change the other.
CONTACT = {
    "site": "markettide.in",
    "email": "market.tide27@gmail.com",
    "phone": "+91 82004 40146",
    "community": "join at markettide.in/subscribe",
}

CHROME_CANDIDATES = [
    os.environ.get("CHROME_PATH"),
    "/c/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


# --------------------------------------------------------------------- data

def fetch(day=None, source=None):
    if source:
        with open(source, encoding="utf-8") as f:
            data = json.load(f)
    else:
        req = urllib.request.Request(API, headers={"User-Agent": "markettide-brief"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    rows = data.get("items") or []
    if day:
        rows = [r for r in rows if r.get("day") == day]
    return rows, data.get("meta") or {}


def pick(rows, count):
    """The `count` biggest filings, with no category allowed to swallow the issue.

    Strict importance order would hand a heavy results day all fifty slots to
    results. Strict round-robin does the opposite and gives a lone bonus issue
    the same billing as the quarter's numbers. So: work down by importance,
    but stop taking from a category once it has had its share, and only relax
    that if there is not enough news to fill the brief without it.
    """
    rows = [r for r in rows
            if r.get("tag") not in SKIP_TAGS and (r.get("summary") or "").strip()]
    rows.sort(key=lambda r: (-(r.get("score") or 0), -(r.get("mcap") or 0)))

    cap = max(3, round(count / 8))
    out, taken = [], {}
    for limit in (cap, cap * 2, count):          # widen only if short
        for r in rows:
            if len(out) >= count:
                break
            if r in out:
                continue
            t = r.get("tag") or "Other"
            if taken.get(t, 0) >= limit:
                continue
            out.append(r)
            taken[t] = taken.get(t, 0) + 1
        if len(out) >= count:
            break
    return out


IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def filed_at(row):
    """The clock time on a filing, as minutes past midnight, or None.

    The feed gives it as a display string - "31 Aug, 23:40" - so the date part
    is already covered by `day` and only the clock is wanted here.
    """
    t = (row.get("time") or "").strip()
    if "," in t:
        t = t.split(",")[-1].strip()
    try:
        h, m = t.split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return None


def window(rows, issue_date=None):
    """Everything filed from the start of yesterday to 06:45 this morning.

    A newsletter that stopped at midnight would hold anything filed overnight
    for a further twenty-four hours. Running to 06:45, three quarters of an
    hour before the issue goes out, means the reader gets it the same morning.

    Returns (rows in the window, the issue's date). The issue is dated the day
    it is published, not the day it reports on, because it spans both.
    """
    today = issue_date or datetime.datetime.now(IST).date()
    if isinstance(today, str):
        today = datetime.date.fromisoformat(today)
    yesterday = today - datetime.timedelta(days=1)
    cutoff = CUTOFF_HOUR * 60 + CUTOFF_MIN

    keep = []
    for r in rows:
        day = r.get("day")
        if day == yesterday.isoformat():
            keep.append(r)
        elif day == today.isoformat():
            mins = filed_at(r)
            if mins is None or mins <= cutoff:
                keep.append(r)
    return keep, today.isoformat()


def group(picked):
    secs = {}
    for r in picked:
        secs.setdefault(r.get("tag") or "Other", []).append(r)
    for v in secs.values():
        v.sort(key=lambda r: (-(r.get("mcap") or 0), -(r.get("score") or 0)))
    order = [t for t in SECTION_ORDER if t in secs]
    order += sorted(t for t in secs if t not in SECTION_ORDER)
    return [(t, secs[t]) for t in order]


# --------------------------------------------------------------- formatting

def crore(v):
    if not v:
        return ""
    v = float(v)
    if v >= 100000:
        return f"\u20b9{v/100000:.2f} L Cr"
    return f"\u20b9{v:,.0f} Cr".replace(",", ",")


def indian(n):
    s = f"{int(n):,}"                      # 1,234,567
    if len(s.replace(",", "")) <= 3:
        return s
    d = s.replace(",", "")
    head, tail = d[:-3], d[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def e(s):
    return html.escape(str(s or ""))


def pretty_day(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%d %B %Y").lstrip("0")


# ------------------------------------------------------------------ styling

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm; }
@page :first { margin-top: 0; }

* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  margin: 0;
  font-family: "Inter", -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 9.6pt; line-height: 1.5; color: #14161a;
  font-variant-numeric: tabular-nums;
}
h1, h2, h3 { margin: 0; font-weight: 600; }
.serif { font-family: "Instrument Serif", Georgia, "Times New Roman", serif;
         font-weight: 400; letter-spacing: -0.01em; }

/* ---------- cover ---------- */
.cover {
  height: 297mm; padding: 26mm 18mm 20mm;
  background: linear-gradient(150deg, #4f9cff 0%, #6a7dff 46%, #7c5cff 100%);
  color: #fff; page-break-after: always; position: relative;
}
.cover .mark { display: flex; align-items: center; gap: 9px;
               font-size: 12pt; font-weight: 600; letter-spacing: -0.01em; }
.cover .mark i { width: 9px; height: 9px; border-radius: 50%;
                 background: #fff; display: inline-block; }
.cover h1 { font-size: 46pt; line-height: 1.02; margin: 34mm 0 0; max-width: 15ch; }
.cover .rule { width: 46mm; height: 2px; background: rgba(255,255,255,.55);
               margin: 9mm 0 7mm; }
.cover .date { font-size: 13pt; font-weight: 500; letter-spacing: .01em; }
.cover .blurb { margin: 4mm 0 0; font-size: 10.8pt; line-height: 1.62;
                max-width: 58ch; color: rgba(255,255,255,.93); }
.cover .blurb b { font-weight: 600; color: #fff; }
.cover .figs { position: absolute; left: 18mm; right: 18mm; bottom: 20mm;
               display: flex; gap: 0; border-top: 1px solid rgba(255,255,255,.35);
               padding-top: 6mm; }
.cover .fig { flex: 1; }
.cover .fig b { display: block; font-size: 21pt; font-weight: 600;
                letter-spacing: -0.02em; line-height: 1; }
.cover .fig span { font-size: 8.6pt; color: rgba(255,255,255,.85);
                   display: block; margin-top: 2mm; }

/* ---------- running header ---------- */
.masthead {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 1.4px solid #14161a; padding-bottom: 2.5mm; margin-bottom: 6mm;
}
.masthead .n { font-size: 11pt; font-weight: 600; letter-spacing: -0.01em; }
.masthead .d { font-size: 8.6pt; color: #6b7280; }

/* ---------- contents ---------- */
.toc { margin-bottom: 8mm; page-break-after: always; }
.toc h2 { font-size: 20pt; margin-bottom: 5mm; }
.toc ol { margin: 0; padding: 0; list-style: none; columns: 2; column-gap: 12mm; }
.toc li { display: flex; justify-content: space-between; gap: 4mm;
          padding: 2.1mm 0; border-bottom: 1px solid #eceef1;
          break-inside: avoid; font-size: 9.4pt; }
.toc li span { color: #6b7280; font-size: 8.8pt; }

/* ---------- sections ---------- */
.sec { margin-bottom: 7mm; break-inside: auto; }
.sec-h { display: flex; align-items: baseline; gap: 4mm; margin-bottom: 3.5mm;
         break-after: avoid; }
.sec-h h2 { font-size: 15pt; letter-spacing: -0.01em; }
.sec-h .n { font-size: 8.4pt; color: #8a9099; font-weight: 500; }
.sec-h .line { flex: 1; height: 1px; background: #e4e7eb; }

/* ---------- one filing ---------- */
.item { break-inside: avoid; padding: 3.4mm 0 3.6mm;
        border-bottom: 1px solid #eceef1; }
.item:last-child { border-bottom: 0; }
.item .top { display: flex; align-items: baseline; gap: 3mm; margin-bottom: 1.6mm; }
.item .co { font-size: 10.6pt; font-weight: 600; letter-spacing: -0.012em;
            line-height: 1.25; }
.item .mcap { font-size: 8pt; font-weight: 600; color: #4b5563;
              background: #f1f3f6; border-radius: 3px; padding: 0.6mm 1.6mm;
              white-space: nowrap; }
.item .ex { margin-left: auto; font-size: 7.8pt; color: #9aa1ab;
            white-space: nowrap; letter-spacing: .02em; }
.item p { margin: 0; font-size: 9.5pt; line-height: 1.58; color: #23262c; }
.item .nums { margin-top: 2.2mm; display: flex; flex-wrap: wrap; gap: 1.6mm; }
.item .nums span { font-size: 8.1pt; color: #3d4350; background: #f6f7f9;
                   border: 1px solid #e9ebef; border-radius: 3px;
                   padding: 0.7mm 2mm; }
.item .why { margin-top: 2.2mm; font-size: 8.9pt; color: #5b6270;
             border-left: 2px solid #cfd4dc; padding-left: 3mm; line-height: 1.5; }

/* ---------- closing ---------- */
.end { margin-top: 9mm; padding-top: 5mm; border-top: 1.4px solid #14161a;
       font-size: 8.6pt; color: #6b7280; line-height: 1.65;
       break-inside: avoid; }
.end b { color: #14161a; }
.end-top { display: flex; gap: 12mm; align-items: flex-start; }
.end-top > div:first-child { flex: 1; }
.end-contact { display: flex; flex-direction: column; gap: 0.8mm;
               min-width: 52mm; }
.end-contact .end-h { font-size: 7.6pt; font-weight: 700; color: #14161a;
                      letter-spacing: 0.06em; text-transform: uppercase;
                      margin-bottom: 1mm; }
.end-note { margin-top: 5mm; padding-top: 3mm; border-top: 1px solid #e4e7eb;
            font-size: 8pt; color: #8a9099; }
"""


# ------------------------------------------------------------------- render

FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&"
         "family=Instrument+Serif&display=swap")


def render(rows, day_iso, meta, count):
    picked = pick(rows, count)
    sections = group(picked)
    day_txt = pretty_day(day_iso)
    companies = len({r.get("company") for r in picked})

    out = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>Market Tide - the morning brief, {e(day_txt)}</title>",
        f"<link rel='stylesheet' href='{FONTS}'>",
        f"<style>{CSS}</style></head><body>",
    ]

    # ---- cover
    out.append(f"""
<div class="cover">
  <div class="mark"><i></i> Market Tide</div>
  <h1 class="serif">The morning brief</h1>
  <div class="rule"></div>
  <div class="date">{e(day_txt)}</div>
  <p class="blurb">Every day, we sift through all the announcements filed with
     NSE &amp; BSE.</p>
  <p class="blurb">In this newsletter, we bring you the Top {len(picked)} most
     important announcements from yesterday &mdash; what happened, the key
     numbers, and why it matters.</p>
  <p class="blurb">To read all the important announcements, visit
     <b>markettide.in</b>.</p>
  <div class="figs">
    <div class="fig"><b>{indian(meta.get('scanned') or 0)}</b><span>filed on NSE &amp; BSE</span></div>
    <div class="fig"><b>{indian(len(rows))}</b><span>worth reading</span></div>
    <div class="fig"><b>{len(picked)}</b><span>in this brief</span></div>
    <div class="fig"><b>{companies}</b><span>companies</span></div>
  </div>
</div>""")

    # ---- contents
    out.append(f"""
<div class="masthead"><div class="n serif">The morning brief</div>
  <div class="d">{e(day_txt)}</div></div>
<div class="toc"><h2 class="serif">What's inside</h2><ol>""")
    for tag, items in sections:
        out.append(f"<li>{e(tag)} <span>{len(items)}</span></li>")
    out.append("</ol></div>")

    # ---- the filings
    out.append(f"""<div class="masthead"><div class="n serif">The morning brief</div>
  <div class="d">{e(day_txt)}</div></div>""")

    for tag, items in sections:
        out.append('<div class="sec"><div class="sec-h">'
                   f'<h2 class="serif">{e(tag)}</h2>'
                   f'<span class="n">{len(items)}</span><span class="line"></span></div>')
        for r in items:
            mcap = crore(r.get("mcap"))
            out.append('<div class="item"><div class="top">'
                       f'<span class="co">{e(r.get("company"))}</span>')
            if mcap:
                out.append(f'<span class="mcap">{e(mcap)}</span>')
            out.append(f'<span class="ex">{e(r.get("exchange"))}</span></div>')
            out.append(f'<p>{e(r.get("summary"))}</p>')
            nums = [n for n in (r.get("key_numbers") or []) if n][:6]
            if nums:
                out.append('<div class="nums">'
                           + "".join(f"<span>{e(n)}</span>" for n in nums)
                           + "</div>")
            if r.get("why_it_matters"):
                out.append(f'<div class="why">{e(r["why_it_matters"])}</div>')
            out.append("</div>")
        out.append("</div>")

    out.append(f"""
<div class="end">
  <div class="end-top">
    <div>
      <b>Market Tide</b> reads every corporate announcement filed with NSE and
      BSE and summarises the ones that matter. The full searchable archive,
      including the filings left out of this brief, is at
      <b>{e(CONTACT['site'])}</b>.
    </div>
    <div class="end-contact">
      <span class="end-h">Get in touch</span>
      <span>{e(CONTACT['email'])}</span>
      <span>{e(CONTACT['phone'])}</span>
      <span>{e(CONTACT['site'])}</span>
      <span>WhatsApp community &middot; {e(CONTACT['community'])}</span>
    </div>
  </div>
  <div class="end-note">
    Summaries are written from the original filing and are for information only.
    They are not investment advice, and Market Tide is not a registered
    investment adviser. Always read the filing itself before acting.
  </div>
</div></body></html>""")
    return "\n".join(out), picked


# ------------------------------------------------------------------ storage

# Kept for two months. Long enough that a link shared in the group still opens
# weeks later, short enough that the store never grows without bound.
BRIEF_TTL = 60 * 86400
MAX_CHARS = 600_000        # inside Upstash's REST request limit, as publish.py


def _redis(url, token, command):
    import requests
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"},
                      json=command, timeout=90)
    if not r.ok:
        raise RuntimeError(f"Redis {r.status_code}: {r.text[:200]}")
    return r.json().get("result")


def store(day_iso, pdf_path, url, token):
    """Put the PDF where the website can serve it.

    Base64 in chunks, the same shape publish.py already uses for a heavy day,
    so there is no second storage service to pay for or keep alive.
    """
    import base64
    blob = base64.b64encode(open(pdf_path, "rb").read()).decode()
    key = f"mt:brief:{day_iso}"
    chunks = [blob[i:i + MAX_CHARS] for i in range(0, len(blob), MAX_CHARS)]
    for i, c in enumerate(chunks):
        _redis(url, token, ["SET", f"{key}:{i}", c, "EX", str(BRIEF_TTL)])
    _redis(url, token, ["SET", f"{key}:parts", str(len(chunks)), "EX", str(BRIEF_TTL)])

    try:
        raw = _redis(url, token, ["GET", "mt:brief:index"])
        days = json.loads(raw) if raw else []
    except Exception:
        days = []
    days = sorted({day_iso, *days}, reverse=True)[:60]
    _redis(url, token, ["SET", "mt:brief:index", json.dumps(days),
                        "EX", str(BRIEF_TTL)])
    return len(chunks), len(days)


# -------------------------------------------------------------------- email

# The waitlist, as web/lib/store.js writes it: one hash, email -> JSON record.
WAITLIST_KEY = "waitlist"


def subscribers(url, token):
    flat = _redis(url, token, ["HGETALL", WAITLIST_KEY]) or []
    out = []
    for i in range(0, len(flat), 2):
        addr = flat[i]
        try:
            rec = json.loads(flat[i + 1])
            addr = rec.get("email") or addr
        except Exception:
            pass
        if addr and "@" in addr:
            out.append(addr.strip().lower())
    return sorted(set(out))


def email_body(day_txt, count, day_iso):
    link = f"https://markettide.in/brief/{day_iso}"
    return (
        f"The morning brief for {day_txt} is attached.\n\n"
        f"Every day we sift through all the announcements filed with NSE & BSE. "
        f"This issue carries the top {count} from yesterday - what happened, the "
        f"key numbers, and why it matters.\n\n"
        f"Read it online: {link}\n"
        f"Every important announcement, searchable: https://markettide.in\n\n"
        f"Market Tide summarises public exchange filings. It is not investment "
        f"advice. Always read the filing itself before acting.\n"
    )


def send_email(pdf_path, day_iso, count, to, api_key, from_addr):
    """One Resend call per recipient, so one bad address cannot sink the batch."""
    import base64
    import requests

    day_txt = pretty_day(day_iso)
    attachment = {
        "filename": f"market-tide-brief-{day_iso}.pdf",
        "content": base64.b64encode(open(pdf_path, "rb").read()).decode(),
    }
    ok, failed = 0, []
    for addr in to:
        try:
            r = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"from": from_addr, "to": [addr],
                      "subject": f"The morning brief - {day_txt}",
                      "text": email_body(day_txt, count, day_iso),
                      "attachments": [attachment]},
                timeout=45)
            if r.ok:
                ok += 1
            else:
                failed.append(f"{addr}: {r.status_code} {r.text[:120]}")
        except Exception as exc:
            failed.append(f"{addr}: {type(exc).__name__}")
    return ok, failed


# ---------------------------------------------------------------------- pdf

def find_chrome():
    for c in CHROME_CANDIDATES:
        if not c:
            continue
        if os.path.exists(c):
            return c
        found = shutil.which(c)
        if found:
            return found
    return None


def to_pdf(html_path, pdf_path):
    chrome = find_chrome()
    if not chrome:
        print("  no Chrome found - set CHROME_PATH. HTML written, PDF skipped.")
        return False
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", "--virtual-time-budget=12000",
           f"--print-to-pdf={os.path.abspath(pdf_path)}", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not os.path.exists(pdf_path):
        print("  Chrome did not write a PDF:", (r.stderr or "")[:300])
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="issue date (YYYY-MM-DD). Default: today in IST.")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--source", help="read a saved API response instead of the network")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--html-only", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="put the PDF in the KV store so the site can serve it")
    args = ap.parse_args()

    rows, meta = fetch(None, args.source)
    if not rows:
        sys.exit("the API returned no filings")

    rows, day_iso = window(rows, args.day)
    if not rows:
        sys.exit(f"nothing filed in the window ending {day_iso} 06:45")

    doc, picked = render(rows, day_iso, meta, args.count)
    os.makedirs(args.out, exist_ok=True)
    html_path = os.path.join(args.out, f"brief-{day_iso}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"{len(picked)} filings from {len(rows)} -> {html_path}")

    if args.html_only:
        return

    pdf_path = os.path.join(args.out, f"brief-{day_iso}.pdf")
    if not to_pdf(html_path, pdf_path):
        sys.exit("could not print the PDF")
    kb = os.path.getsize(pdf_path) // 1024
    print(f"  PDF: {pdf_path}  ({kb} KB)")

    if args.publish:
        url = os.environ.get("KV_REST_API_URL")
        token = os.environ.get("KV_REST_API_TOKEN")
        if not (url and token):
            sys.exit("  --publish needs KV_REST_API_URL and KV_REST_API_TOKEN")
        parts, held = store(day_iso, pdf_path, url, token)
        print(f"  published as {parts} part(s); {held} issues now available")
        print(f"  https://markettide.in/brief/{day_iso}")


if __name__ == "__main__":
    main()

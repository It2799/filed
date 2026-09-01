"""Downloads the announcement PDF and gets it summarised."""

import base64
import io
import threading
import zipfile

import requests
from pypdf import PdfReader, PdfWriter

import providers

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

MAX_PAGES = 14          # trim long PDFs before sending them off
MAX_PDF_BYTES = 12_000_000
# Nothing larger is downloaded at all. The biggest attachment seen in a
# normal day is 26 MB, and no summary needs it.
MAX_DOWNLOAD_BYTES = 14_000_000
MAX_TEXT_CHARS = 26_000

SYSTEM = """You read official corporate announcements filed with Indian stock exchanges
and explain them to retail investors who have ten seconds.

Rules:
- summary: 2 to 3 short sentences on what the company actually announced. Plain English.
- key_numbers: the concrete figures that matter - order value, revenue, profit, dividend
  per share, percentages, ratios, dates. Short phrases like "Order value Rs 412 crore".
  Empty list if the filing has none.
- impact: how a shareholder would read this news.
- why_it_matters: one short line on the practical significance.

Never invent a number that is not in the document. If the document is unreadable or
says nothing of substance, say so plainly and set impact to "Unclear"."""


def _context(item):
    return (f"Company: {item['company']}\n"
            f"Filing category: {item['category']}\n"
            f"Headline as filed: {item['headline']}\n")


# ------------------------------------------------------------------ PDF

# One session per thread, reused for every download that thread makes.
#
# requests.get() opens a fresh TCP and TLS connection each call. Reading a
# day's filings means hundreds of downloads from a US runner to servers in
# India, where a handshake costs three round trips before a single byte of PDF
# moves. Measured over the same 14 attachments, reusing the connection took
# the small ones from 0.85s to 0.17s.
_local = threading.local()


def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        adapter = requests.adapters.HTTPAdapter(pool_connections=4,
                                                pool_maxsize=4)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _local.s = s
    return s


# (connect, read). Ninety seconds was one timeout for both, so a throttled
# request held a worker for a minute and a half. A filing that has not started
# arriving within 20s is not worth the thread.
TIMEOUTS = (5, 20)


def _get(url, referer):
    """Download, but stop reading once the file is clearly too big to use.

    Attachments run to 26 MB - annual reports filed as a "press release". The
    whole thing used to come down before anything checked the size, and for
    triage all that is wanted is the text on the first few pages.
    """
    r = _session().get(url, timeout=TIMEOUTS, stream=True,
                       headers={"Referer": referer})
    try:
        if r.status_code != 200:
            return None
        size = int(r.headers.get("Content-Length") or 0)
        if size > MAX_DOWNLOAD_BYTES:
            return None
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) > MAX_DOWNLOAD_BYTES:
                return None
        return bytes(buf)
    finally:
        r.close()


def fetch_pdf(item):
    """Return raw PDF bytes, or None. Handles NSE's zipped attachments."""
    urls = [u for u in (item.get("pdf_url"), item.get("pdf_alt")) if u]
    referer = "https://www.nseindia.com/" if item["exchange"].startswith("NSE") \
        else "https://www.bseindia.com/"

    for url in urls:
        try:
            blob = _get(url, referer)
        except Exception:
            continue
        if not blob:
            continue

        if blob[:4] == b"%PDF":
            return blob

        if blob[:2] == b"PK":                      # zip -> find the pdf inside
            try:
                zf = zipfile.ZipFile(io.BytesIO(blob))
                for n in zf.namelist():
                    if n.lower().endswith(".pdf"):
                        inner = zf.read(n)
                        if inner[:4] == b"%PDF":
                            return inner
            except Exception:
                pass
    return None


def pdf_text(blob):
    try:
        pages = PdfReader(io.BytesIO(blob)).pages
        return "\n".join((p.extract_text() or "") for p in pages[:40]).strip()
    except Exception:
        return ""


def trim_pdf(blob):
    """Keep the first few pages so we don't ship a 200-page annual report."""
    try:
        reader = PdfReader(io.BytesIO(blob))
        if len(reader.pages) <= MAX_PAGES and len(blob) <= MAX_PDF_BYTES:
            return blob
        w = PdfWriter()
        for p in reader.pages[:MAX_PAGES]:
            w.add_page(p)
        buf = io.BytesIO()
        w.write(buf)
        return buf.getvalue()
    except Exception:
        return blob


# ------------------------------------------------------------------ main

def summarize(item, provider_list):
    """Read the filing and summarise it. Sets item['source_used']."""
    ctx = _context(item)
    blob = fetch_pdf(item) if item.get("pdf_url") else None

    if not blob:
        item["source_used"] = "headline only"
        return providers.run(
            provider_list, SYSTEM,
            ctx + "\nNo document is available. Summarise from the headline alone "
                  "and stay cautious.")

    text = pdf_text(blob)

    if len(text) >= 500:
        item["source_used"] = "pdf-text"
        return providers.run(
            provider_list, SYSTEM,
            ctx + "\n--- DOCUMENT TEXT ---\n" + text[:MAX_TEXT_CHARS])

    # No extractable text: it's a scan. Only a provider that can see images can help.
    small = trim_pdf(blob)
    if len(small) > MAX_PDF_BYTES:
        item["source_used"] = "headline (pdf too big)"
        return providers.run(
            provider_list, SYSTEM,
            ctx + "\nThe document was too large to read. Summarise from the headline alone.")

    item["source_used"] = "pdf-scan"
    return providers.run(
        provider_list, SYSTEM,
        ctx + "\nThe scanned document is attached. Read it and answer from it.",
        pdf_b64=base64.b64encode(small).decode())

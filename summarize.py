"""Downloads the announcement PDF and gets it summarised."""

import base64
import io
import zipfile

import requests
from pypdf import PdfReader, PdfWriter

import providers

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

MAX_PAGES = 14          # trim long PDFs before sending them off
MAX_PDF_BYTES = 12_000_000
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

def _get(url, referer):
    return requests.get(url, timeout=90, headers={"User-Agent": UA, "Referer": referer})


def fetch_pdf(item):
    """Return raw PDF bytes, or None. Handles NSE's zipped attachments."""
    urls = [u for u in (item.get("pdf_url"), item.get("pdf_alt")) if u]
    referer = "https://www.nseindia.com/" if item["exchange"].startswith("NSE") \
        else "https://www.bseindia.com/"

    for url in urls:
        try:
            r = _get(url, referer)
        except Exception:
            continue
        if r.status_code != 200 or not r.content:
            continue
        blob = r.content

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

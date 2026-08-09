# NSE + BSE announcement filter

Pulls every corporate announcement filed with NSE and BSE, throws away the routine
paperwork, reads the PDFs of what's left, and puts plain-English summaries on a
dashboard you open in your browser.

## Setup

```bash
pip install requests pypdf
```

Copy `config.example.json` to `config.json` and put your own keys in. Get a free
Groq key at [console.groq.com](https://console.groq.com) and a free Gemini key at
[aistudio.google.com](https://aistudio.google.com).

`config.json` is gitignored — keep it that way, it holds your keys.

There's also a waitlist landing page in [`web/`](web/) with its own README.

## Running it

Double-click `run.bat`, or from a terminal:

```bash
python run.py
```

That does today. Some other useful ways to run it:

```bash
python run.py --days 3
```

```bash
python run.py --min-score 65
```

```bash
python run.py --no-summary
```

- `--days N` — look back N days as well as today.
- `--min-score N` — how strict the filter is. Default 55. Lower it to ~45 to also
  see investor presentations and board-meeting notices; raise it to ~65 for only
  buybacks, bonus issues, takeovers and big M&A.
- `--max-summaries N` — how many filings get an AI summary. Default 40.
- `--no-summary` — skip the AI entirely. Free and instant, filter only.
- `--no-open` — don't launch the browser.

Output lands in `dashboard.html` in this folder.

## What counts as important

`rules.py` holds the lists, and they're meant to be edited. In short:

- **Thrown out completely** — trading window notices, newspaper clippings,
  duplicate share certificates, shareholding patterns, compliance certificates,
  ESOP allotments, AGM notices.
- **Kept and ranked** — results, dividends, bonus/split, buybacks, acquisitions
  and mergers, order wins, fund raising, open offers, credit ratings, insolvency
  and court orders, plant/capacity news, monthly business updates.
- **Deliberately pushed down** — things that only *refer* to big news, like an
  audio recording of an earnings call, or a notice that the board *will meet* to
  consider results. Those aren't the news itself.

Each filing gets a score out of 100. The filing category is trusted more than the
headline, because the exchanges use a fixed list of categories while headlines are
free text and often misleading.

## The AI summaries

Two services do the work, and they're picked per filing:

- **Groq** is very fast — under a second per filing — but text only.
- **Gemini** is slower but can *look* at a page.

About 97% of announcements are PDFs with real text inside. Those go to Groq. The
rest are scans — a photo of a signed letter, no extractable text — and those can
only be handled by Gemini, which reads the page visually.

Both are on free plans with tight per-minute token limits, so `providers.py`
keeps a running budget for each model. When one model is busy the next one in the
list picks up the filing instead of everything queueing behind it. When a model
runs out for the day it's dropped for the rest of the run.

At the end of each run you'll see who did what:

```
Who did the work:
    16  gemini-flash-lite-latest
     7  openai/gpt-oss-120b
     7  openai/gpt-oss-20b
```

To use only one service, delete the other from the `providers` list in
`config.json` — but if you delete Gemini, scanned filings will be skipped, because
nothing left can read them.

Only some filings get summarised, since there can be 500+ important ones on a busy
results day. They're picked by going round the categories in turn and taking each
one's highest-scoring filing, so you get a spread rather than 40 acquisitions.

Summaries are cached in `cache.json` by filing ID, so re-running the same day
costs nothing extra.

### About quota

Both keys are on free plans, and the limits are tighter than they look:

| | Free limit | Roughly |
|---|---|---|
| Groq `gpt-oss-120b` | 8,000 tokens/min, 200k/day | ~50 filings/day |
| Groq `gpt-oss-20b` | 8,000 tokens/min | another ~50/day |
| `gemini-2.5-flash` | 20 requests/**day** | almost nothing |
| `gemini-flash-lite-latest` | much higher | the workhorse |

A filing costs about 4,000 tokens, which is what makes the per-minute caps bite.
Between all the models you can do roughly 100–150 filings a day for free. Beyond
that, enable billing on either key — at real prices this costs a few dollars a
month, not hundreds.

Summaries are cached, so re-running never spends quota twice.

## Files

| File | What it does |
|---|---|
| `run.py` | The one you run. Ties everything together. |
| `sources.py` | Talks to the NSE and BSE announcement APIs. |
| `rules.py` | Decides what's important. Edit this to tune the filter. |
| `summarize.py` | Downloads PDFs and works out how to read each one. |
| `providers.py` | Talks to Groq and Gemini, and rations the free quota. |
| `dashboard.py` | Builds `dashboard.html`. |
| `config.json` | API key and default settings. |
| `cache.json` | Saved summaries so you don't pay twice. Safe to delete. |

## Two things worth knowing

- BSE only answers one calendar day per request, so `--days 3` means three separate
  passes. It's slower than it looks.
- NSE blocks plain scripted requests, so `sources.py` visits the homepage first to
  pick up a session cookie. If NSE starts returning nothing, that handshake is the
  first thing to check.

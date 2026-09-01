"""
Talks to the AI services. Two of them, used for different jobs.

  Groq   - very fast, but text only. Gets the ~97% of filings whose PDF has
           real text in it.
  Gemini - slower, but it can LOOK at a page. Gets the scanned filings that
           are just a photo of a signed letter, plus anything Groq couldn't take.

Both are on free plans with tight limits, so every model has its own token
budget here and we wait rather than get rejected. When a model runs out for
the day we stop using it and move down the list.
"""

import json
import threading
import time

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# OpenRouter speaks the same dialect as Groq, so one function serves both.
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_numbers": {"type": "array", "items": {"type": "string"}},
        "impact": {"type": "string", "enum": ["Positive", "Negative", "Neutral", "Unclear"]},
        "why_it_matters": {"type": "string"},
    },
    "required": ["summary", "key_numbers", "impact", "why_it_matters"],
    "additionalProperties": False,
}

# Gemini wants the same shape but in its own dialect.
GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "key_numbers": {"type": "ARRAY", "items": {"type": "STRING"}},
        "impact": {"type": "STRING", "enum": ["Positive", "Negative", "Neutral", "Unclear"]},
        "why_it_matters": {"type": "STRING"},
    },
    "required": ["summary", "key_numbers", "impact", "why_it_matters"],
}

_lock = threading.Lock()
_spent = {}        # model -> list of (when, tokens) in the last minute
_dead = set()      # models finished for the day
stats = {}         # model -> how many filings it summarised


def _note(model, n=1):
    with _lock:
        stats[model] = stats.get(model, 0) + n


def report():
    return dict(stats)


def dead():
    return sorted(_dead)


def _try_reserve(model, tpm, tokens):
    """Take `tokens` from this model's per-minute budget if there's room. Never blocks."""
    with _lock:
        now = time.time()
        recent = [(t, n) for t, n in _spent.get(model, []) if now - t < 60]
        _spent[model] = recent
        used = sum(n for _, n in recent)
        if used + tokens <= tpm or not recent:
            _spent[model].append((now, tokens))
            return True
        return False


def _wait_for(model, tpm, tokens):
    """Block until this model has room. Used only when every model is busy."""
    while not _try_reserve(model, tpm, tokens):
        with _lock:
            recent = _spent.get(model, [])
            wait = 61 - (time.time() - recent[0][0]) if recent else 1
        time.sleep(max(1.0, min(wait, 61)))


def _estimate(text, pdf_bytes):
    n = len(text) / 4
    if pdf_bytes:
        n += 3000          # a trimmed scan is worth roughly this much
    return int(n) + 300


# ---------------------------------------------------------------- Groq

def _is_daily(body):
    """Is this 429 the daily cap, or just this minute's?

    It matters enormously: a per-minute limit means wait, a per-day limit means
    stop using this model until tomorrow. Both providers return the same
    message for either, and the only thing telling them apart is a marker deep
    in the JSON - Gemini puts "GenerateRequestsPerDayPerProjectPerModel" in a
    quotaId at around character 430.

    This used to read `r.text[:300]`, so that marker was always cut off and the
    daily cap was never once detected. The model stayed in the rotation, and
    every later filing walked five exhausted models twice over with a 20 second
    sleep between each - about ten minutes per filing, achieving nothing. One
    run spent two hours and seventeen minutes on a single day's filings that
    way, and blocked every scheduled run behind it for five and a half hours.
    """
    low = (body or "").lower()
    return ("perday" in low or "per day" in low or "per-day" in low
            or "requests_per_day" in low or '"rpd"' in low or '"tpd"' in low
            or "daily limit" in low or "quota_exceeded_per_day" in low)


def _groq(key, model, system, user, url=GROQ_URL):
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.2,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "filing_summary",
                                            "strict": True, "schema": SCHEMA}},
    }
    r = requests.post(url, headers={"Authorization": "Bearer " + key,
                                         "Content-Type": "application/json"},
                      json=body, timeout=180)
    if r.status_code == 200:
        return json.loads(r.json()["choices"][0]["message"]["content"]), None

    # Groq says "rate_limit_exceeded" for both the per-minute and per-day caps.
    # Judge on the WHOLE body and only shorten it for the log line - see
    # _is_daily below for what truncating it used to cost.
    daily = _is_daily(r.text)
    return None, (f"{model} HTTP {r.status_code}: {r.text[:300]}",
                  r.status_code == 429, daily)


# ---------------------------------------------------------------- Gemini

def _gemini(key, model, parts):
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseSchema": GEMINI_SCHEMA, "temperature": 0.2},
    }
    r = requests.post(GEMINI_URL.format(model=model),
                      headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                      json=body, timeout=240)
    if r.status_code == 200:
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(txt), None
    daily = _is_daily(r.text)
    return None, (f"{model} HTTP {r.status_code}: {r.text[:300]}",
                  r.status_code == 429, daily)


# ---------------------------------------------------------------- routing

def run(providers, system, user, pdf_b64=None):
    """
    Try each provider's models in order until one answers.

    `pdf_b64` is set only for scanned filings - those skip any provider that
    cannot look at an image.
    """
    last = "no provider available"
    tokens = _estimate(user, pdf_b64)

    # Every model we're allowed to use, in preference order.
    lineup = [(p, m) for p in providers
              if p.get("key") and (p.get("vision") or not pdf_b64)
              for m in p.get("models", [])]
    if not lineup:
        return {"error": "no provider can handle this filing "
                         "(scanned PDFs need a provider with vision)"}

    # Take the first model with room right now. Only wait if they are all busy.
    ready = []
    for p, m in lineup:
        if m not in _dead and _try_reserve(m, p.get("tpm", 8000), tokens):
            ready = [(p, m)]
            break

    if not ready:
        p, m = next(((p, m) for p, m in lineup if m not in _dead), (None, None))
        if m is None:
            return {"error": "every model has used up its free quota for today"}
        _wait_for(m, p.get("tpm", 8000), tokens)
        ready = [(p, m)]

    # The one we reserved goes first, then the rest as fallbacks.
    picked = {m for _, m in ready}
    order = ready + [(p, m) for p, m in lineup if m not in _dead and m not in picked]

    for p, model in order:
        for attempt in range(2):
            try:
                if p["kind"] in ("groq", "openrouter"):
                    out, err = _groq(
                        p["key"], model, system, user,
                        OPENROUTER_URL if p["kind"] == "openrouter" else GROQ_URL)
                else:
                    parts = [{"text": system + "\n\n" + user}]
                    if pdf_b64:
                        parts.append({"inline_data": {"mime_type": "application/pdf",
                                                      "data": pdf_b64}})
                    out, err = _gemini(p["key"], model, parts)
            except Exception as e:
                last = f"{model}: {type(e).__name__}: {e}"
                time.sleep(4)
                continue

            if out is not None:
                _note(model)
                return out

            last, is_429, is_daily = err
            if is_daily:
                with _lock:
                    _dead.add(model)
                break
            if is_429:
                time.sleep(20)     # per-minute cap - breathe, then retry once
                continue
            break                  # a real error, this model is no good here

    return {"error": last}

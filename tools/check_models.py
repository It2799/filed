"""
Ask every configured model to summarise a filing, and report which can.

A model list rots. On 9 September three of the four OpenRouter models in
config.json were unusable - one had been withdrawn from OpenRouter entirely
and 404'd on every call, two were rate limited off the shared free pool - and
nothing anywhere said so. The pipeline just fell through to the next provider,
which is exactly what it is designed to do, so the failure was invisible.

This is the check that would have caught it. It sends a real filing and
insists on the real schema, because a model can be listed, answer 200, and
still refuse to produce structured output - and that is the failure that
matters.

    python tools/check_models.py                 # every provider
    python tools/check_models.py --kind openrouter
    python tools/check_models.py --fail-if-none  # exit 1 if a provider is dead

Keys come from the environment first, then config.json, the same way
publish.load_providers finds them.
"""

import argparse
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import providers                                            # noqa: E402
import publish                                              # noqa: E402

# A real filing with a real number in it, so a model that answers with
# plausible-looking nothing is visible.
FILING = (
    "Bondada Engineering Limited has informed the Exchange that the Board of "
    "Directors at its meeting held today approved the acquisition of a 74% "
    "equity stake in PhotonicGrid Networks Private Limited for a "
    "consideration of Rs 260 crore, payable in cash."
)

PROMPT = ("Summarise this Indian stock exchange filing for an investor. "
          "Reply only with JSON matching the schema.\n\nFILING:\n" + FILING)


def try_openai_style(url, key, model):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "filing_summary", "strict": True,
                            "schema": providers.SCHEMA},
        },
        "temperature": 0.2,
    }
    r = requests.post(url, json=body, timeout=90, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if r.status_code != 200:
        return None, f"http {r.status_code} {r.text[:60]}"
    try:
        return json.loads(r.json()["choices"][0]["message"]["content"]), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:50]}"


def try_gemini(key, model):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    body = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseSchema": providers.GEMINI_SCHEMA,
                             "temperature": 0.2},
    }
    r = requests.post(url, json=body, timeout=90)
    if r.status_code != 200:
        return None, f"http {r.status_code} {r.text[:60]}"
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text), None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:50]}"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kind", help="only this provider")
    p.add_argument("--fail-if-none", action="store_true",
                   help="exit 1 if any provider has no working model")
    args = p.parse_args()

    provider_list = publish.load_providers()
    if not provider_list:
        print("No providers configured.")
        return 1

    required = providers.SCHEMA.get("required", [])
    dead_providers = []

    for prov in provider_list:
        kind = prov.get("kind")
        if args.kind and kind != args.kind:
            continue
        print(f"\n{kind}")
        working = 0
        for model in prov.get("models") or []:
            t0 = time.time()
            try:
                if kind == "gemini":
                    parsed, err = try_gemini(prov["key"], model)
                else:
                    url = (providers.OPENROUTER_URL if kind == "openrouter"
                           else providers.GROQ_URL)
                    parsed, err = try_openai_style(url, prov["key"], model)
            except Exception as e:
                parsed, err = None, f"{type(e).__name__}: {str(e)[:50]}"
            took = time.time() - t0

            if parsed is None:
                print(f"  DEAD {model:46} {err}")
                continue
            missing = [k for k in required if k not in parsed]
            if missing:
                print(f"  PART {model:46} {took:5.1f}s missing {missing}")
                continue
            working += 1
            print(f"  OK   {model:46} {took:5.1f}s "
                  f"{str(parsed.get('summary', ''))[:44]}")

        print(f"  -> {working} of {len(prov.get('models') or [])} usable")
        if not working:
            dead_providers.append(kind)

    if dead_providers:
        print(f"\nNo usable model for: {', '.join(dead_providers)}")
        if args.fail_if_none:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

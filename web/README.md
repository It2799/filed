# Waitlist site

A one-page Next.js site that collects email signups. Deploys to Vercel.

## Run it locally

```bash
npm install --prefix web
```

```bash
npm run dev --prefix web
```

Then open http://localhost:3000. Locally, signups append to
`web/waitlist.local.jsonl` — that file is gitignored.

## Deploy to Vercel

Import the repo at [vercel.com/new](https://vercel.com/new) and set
**Root Directory** to `web`. Everything else is detected automatically.

## Where the emails go

Out of the box nothing is stored in production — signups are accepted and
logged so the page works while you decide. Pick one of these:

**Upstash Redis (recommended).** In your Vercel project go to Storage → Upstash
Redis → Create. It injects `UPSTASH_REDIS_REST_URL` and
`UPSTASH_REDIS_REST_TOKEN` for you. Free tier is far more than a waitlist needs,
and it de-duplicates emails automatically.

**Any webhook.** Set `WAITLIST_WEBHOOK_URL` to a Google Apps Script, Zapier,
Make, Slack or Discord endpoint. Each signup is POSTed as JSON.

## Getting your list out

Set an `ADMIN_KEY` environment variable, then visit:

```
https://yoursite.vercel.app/api/waitlist/export?key=YOUR_ADMIN_KEY
```

That downloads a CSV. Without `ADMIN_KEY` set the endpoint returns 404, so it's
off by default rather than open to the world.

`GET /api/waitlist` returns the signup count — handy if you want to show
"join 400 others" on the page later.

## Changing the copy

Everything you'd want to edit is at the top of `app/page.jsx`:

- `SITE` — the name and the headline numbers.
- `SAMPLES` — the example summary cards. These are real output from the
  scraper; swap in fresher ones as you go.

The name lives in `SITE.name` in `app/page.jsx` and in the
`metadata` block in `app/layout.jsx`.

## Spam handling

There's a hidden honeypot field. Bots fill it in, people can't see it, and
anything that fills it gets a success response without being stored. Emails are
lowercased and trimmed before saving, so `A@B.com` and `a@b.com` are one person.

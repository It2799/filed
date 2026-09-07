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

### Member access

Dashboard and Daily Brief use passwordless email verification. Configure these
private environment variables in Vercel for Production, Preview and Development:

- `MONGODB_URI` — MongoDB connection string used for reader profiles
- `MONGODB_DB` — optional database name; defaults to `market_tide`
- `AUTH_SECRET` — a long random value used to sign sessions and OTP hashes
- `RESEND_API_KEY` — current transactional provider key; this will be replaced by Brevo for OTP
- `RESEND_FROM` — verified sender; defaults to `Market Tide <brief@markettide.in>`
- `REPLY_TO_EMAIL` — reply destination; defaults to `market.tide27@gmail.com`
- `NEXT_PUBLIC_SUBSTACK_URL` — publication URL, for example `https://markettide.substack.com`
- `NEWSLETTER_DELIVERY` — use `substack` to prevent the worker from sending through Kit
- `KV_REST_API_URL` and `KV_REST_API_TOKEN` — Upstash Redis used for short-lived OTPs
- `CRON_SECRET` — random value of at least 16 characters; Vercel sends it to the cron route
- `GITHUB_DISPATCH_TOKEN` — GitHub token with Actions write access, used only to start the PDF worker
- `ADMIN_PATH_TOKEN` — long random token used in the private `/control/<token>` URL
- `ADMIN_PASSWORD` — password required before any admin data is returned
- `ADMIN_SESSION_SECRET` — optional separate secret for the 12-hour admin session; falls back to `AUTH_SECRET`

New readers enter email and mobile number, then verify the email with a six-digit
code. Their normalized mobile number is stored in MongoDB only after successful
verification. Returning readers enter only their email, and a signed session
keeps them logged in for 30 days.

When `NEXT_PUBLIC_SUBSTACK_URL` is set, the Daily Brief page uses Substack's
official embedded signup form. New newsletter subscribers therefore go directly
to Substack. Market Tide login and community records remain in MongoDB and are
not silently treated as newsletter consent. The morning worker generates and
publishes the PDF, while the final Substack post is reviewed and scheduled for
08:00 IST in Substack.

To create a one-time CSV containing only explicit Daily Brief subscribers, run:

```bash
npm run export:substack
```

The default export includes only records whose subscription source is `brief`.
After manually confirming that an older landing form clearly promised the Daily
Brief, include those records with `SUBSTACK_IMPORT_SOURCES=brief,landing`.

### Morning brief schedule

Vercel Cron calls `/api/cron/brief` at `02:00 UTC`, which is `07:30 IST`.
GitHub Actions no longer owns the schedule; it remains only the PDF-building
worker dispatched by that Vercel endpoint. Cron jobs become active after a
production deployment containing `vercel.json`.

Vercel Pro invokes cron jobs with per-minute precision. On Vercel Hobby, a
daily cron may run anywhere within the scheduled hour, so an exact 07:30
delivery requires Pro or another precise clock.

### Analytics

The root layout includes Vercel Web Analytics. Enable Web Analytics once in the
Vercel project dashboard, then redeploy to begin collecting anonymous page-view
statistics.

## Where the emails go

MongoDB is the durable user/profile database. Upstash Redis remains the mailing
list read by the Daily Brief sender, so both stores are updated on subscription.

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

import crypto from "node:crypto";

export const dynamic = "force-dynamic";

/**
 * Start a scrape, from outside GitHub.
 *
 * GitHub's `schedule` event is best effort and drops runs under load - their
 * documentation says so, and on 1 September it dropped 16 of 23 slots, leaving
 * the site unchanged for nearly four hours over the middle of the day. Every
 * run that GitHub did create finished fine; the problem is that most were
 * never created.
 *
 * `workflow_dispatch` has no such behaviour: it starts within seconds, every
 * time. So an external clock calls this, and this dispatches the workflow.
 *
 *   GET/POST /api/cron/scrape      header:  x-cron-key: <CRON_SECRET>
 *   ...or                          query:   ?key=<CRON_SECRET>
 *
 * Needs two environment variables:
 *   CRON_SECRET            any long random string, shared with the caller
 *   GITHUB_DISPATCH_TOKEN  a fine-grained PAT for It2799/filed with
 *                          Actions: read and write. Nothing else.
 */

const OWNER = "It2799";
const REPO = "filed";
const WORKFLOW = "scrape.yml";

// How stale the published data must be before a new run is worth starting.
// Longer than the 30-minute tick, so an in-flight run that is still writing
// days is never mistaken for a dead one.
const STALE_MINUTES = 40;

/**
 * Minutes since publish.py last wrote mt:meta, or null if that cannot be read.
 *
 * Null means "no opinion" and the dispatch goes ahead. Being unable to reach
 * Redis is not a reason to stop refreshing the site.
 */
async function minutesSincePublish() {
  const url =
    process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token =
    process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(["GET", "mt:meta"]),
      cache: "no-store",
    });
    if (!res.ok) return null;
    const raw = (await res.json()).result;
    const updated = raw && JSON.parse(raw).updated;
    if (!updated) return null;
    const ms = Date.now() - Date.parse(updated);
    if (!Number.isFinite(ms) || ms < 0) return null;
    return Math.round(ms / 60000);
  } catch {
    return null;
  }
}

function sameSecret(given, expected) {
  // Compare hashes so the strings are always the same length, and so the
  // comparison cannot be timed to reveal the secret a character at a time.
  const a = crypto.createHash("sha256").update(String(given || "")).digest();
  const b = crypto.createHash("sha256").update(String(expected)).digest();
  return crypto.timingSafeEqual(a, b);
}

async function trigger(request) {
  const secret = process.env.CRON_SECRET;
  const token = process.env.GITHUB_DISPATCH_TOKEN;

  if (!secret || !token) {
    return Response.json(
      { error: "Not configured. Set CRON_SECRET and GITHUB_DISPATCH_TOKEN." },
      { status: 503 }
    );
  }

  const url = new URL(request.url);
  const given = request.headers.get("x-cron-key") || url.searchParams.get("key");
  if (!sameSecret(given, secret)) {
    // 404 rather than 401: an endpoint that admits it exists invites guessing.
    return new Response("Not found.", { status: 404 });
  }

  // Blank means the workflow decides for itself - today only during the day,
  // the full seven days on the last pass of the night.
  const days = url.searchParams.get("days") || "";

  // Only start a run if the site actually needs one.
  //
  // The workflow cancels whatever is already running when a new run starts,
  // so an unconditional dispatch every 30 minutes means no run may ever take
  // longer than 30 minutes. A full seven-day rescrape takes about 35, and on
  // 3 September three consecutive attempts at one were each killed at the
  // half hour - which is also how a fix to the scoring rules could be pushed
  // three times without ever reaching the whole week.
  //
  // Freshness of the published data is the honest test, not the age of the
  // run: it is what "refreshes every 30 minutes" actually means, and a long
  // run keeps it fresh because publish.py writes mt:meta after every day it
  // finishes, not once at the end.
  //
  // So a healthy run is left alone, and one that has gone quiet is replaced.
  // ?force=1 skips the check.
  const force = url.searchParams.get("force") === "1";
  if (!force) {
    const age = await minutesSincePublish();
    if (age !== null && age < STALE_MINUTES) {
      return Response.json({
        ok: true,
        dispatched: null,
        skipped: `the site was updated ${age} minutes ago`,
        at: new Date().toISOString(),
      });
    }
  }

  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ref: "main",
        ...(days ? { inputs: { days } } : {}),
      }),
    }
  );

  if (res.status !== 204) {
    const detail = (await res.text()).slice(0, 300);
    return Response.json(
      { error: `GitHub refused the dispatch (${res.status})`, detail },
      { status: 502 }
    );
  }

  return Response.json({
    ok: true,
    dispatched: WORKFLOW,
    days: days || "workflow decides",
    at: new Date().toISOString(),
  });
}

export async function GET(request) {
  return trigger(request);
}

export async function POST(request) {
  return trigger(request);
}

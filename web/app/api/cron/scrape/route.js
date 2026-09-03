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
const BRIEF_WORKFLOW = "brief.yml";

// The brief is promised for 07:30 IST. IST is UTC+5:30.
const BRIEF_HOUR_IST = 7;
const BRIEF_MINUTE_IST = 30;

// How stale the published data must be before a new run is worth starting.
// Longer than the 30-minute tick, so an in-flight run that is still writing
// days is never mistaken for a dead one.
const STALE_MINUTES = 40;

/** One Redis command, or null if the store is unreachable or unconfigured. */
async function redis(command) {
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
      body: JSON.stringify(command),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()).result;
  } catch {
    return null;
  }
}

/** Today's date in India, as YYYY-MM-DD. */
function todayIST(now = Date.now()) {
  return new Date(now + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
}

/** Minutes past midnight, India time. */
function minutesIntoDayIST(now = Date.now()) {
  const d = new Date(now + 5.5 * 3600 * 1000);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}

/**
 * Make sure today's morning brief exists, and start it if it does not.
 *
 * The brief has its own `schedule` in brief.yml, and GitHub treated it exactly
 * the way it treats the scraper's: the 02:00 UTC slot ran at 07:03 UTC on
 * 1 September and 06:41 on 2 September, so a newsletter promised for half past
 * seven in the morning arrived at half past twelve. On 3 September the slot had
 * not fired at all forty-five minutes after it was due.
 *
 * The scraper was moved off `schedule` for this reason. The brief was not, and
 * nothing noticed, because a late newsletter still looks like a newsletter.
 *
 * Now the same thirty-minute clock that keeps the site fresh also asks whether
 * today's issue has been published, and starts it if it has not. Worst case the
 * brief is half an hour late instead of five hours.
 */
async function ensureBrief(token) {
  if (minutesIntoDayIST() < BRIEF_HOUR_IST * 60 + BRIEF_MINUTE_IST) {
    return "not due yet";
  }

  const raw = await redis(["GET", "mt:brief:index"]);
  if (raw === null) return "could not check";
  let newest = null;
  try {
    const days = JSON.parse(raw);
    if (Array.isArray(days) && days.length) newest = days[0];
  } catch {
    /* treat an unreadable index as "no issue today" */
  }
  if (newest === todayIST()) return "already published";

  // brief.yml does not cancel a run in progress, it queues behind it, so a
  // build that is simply slow must not be dispatched again every half hour.
  const running = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/` +
      `${BRIEF_WORKFLOW}/runs?status=in_progress&per_page=1`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      cache: "no-store",
    }
  )
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (running && running.total_count > 0) return "already building";

  const res = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/` +
      `${BRIEF_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  return res.status === 204 ? "started" : `GitHub refused it (${res.status})`;
}

/**
 * Minutes since publish.py last wrote mt:meta, or null if that cannot be read.
 *
 * Null means "no opinion" and the dispatch goes ahead. Being unable to reach
 * Redis is not a reason to stop refreshing the site.
 */
async function minutesSincePublish() {
  const raw = await redis(["GET", "mt:meta"]);
  if (!raw) return null;
  try {
    const updated = JSON.parse(raw).updated;
    if (!updated) return null;
    const ms = Date.now() - Date.parse(updated);
    if (!Number.isFinite(ms) || ms < 0) return null;
    return Math.round(ms / 60000);
  } catch {
    return null;
  }
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

  // Checked on every tick, and before the scrape decision returns early -
  // otherwise the brief would only ever be looked at on the ticks that
  // happened to start a scrape, which is most of them but not all.
  const brief = await ensureBrief(token);

  if (!force) {
    const age = await minutesSincePublish();
    if (age !== null && age < STALE_MINUTES) {
      return Response.json({
        ok: true,
        dispatched: null,
        skipped: `the site was updated ${age} minutes ago`,
        brief,
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
    brief,
    at: new Date().toISOString(),
  });
}

export async function GET(request) {
  return trigger(request);
}

export async function POST(request) {
  return trigger(request);
}

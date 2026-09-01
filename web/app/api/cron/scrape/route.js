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

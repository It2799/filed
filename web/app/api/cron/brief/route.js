export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const OWNER = "It2799";
const REPO = "filed";
const WORKFLOW = "brief.yml";

function todayIST() {
  return new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
}

async function newestBrief() {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  const response = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(["GET", "mt:brief:index"]),
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Redis ${response.status}`);
  const raw = (await response.json()).result;
  try {
    const days = JSON.parse(raw || "[]");
    return Array.isArray(days) ? days[0] || null : null;
  } catch {
    return null;
  }
}

export async function GET(request) {
  const cronSecret = process.env.CRON_SECRET;
  if (!cronSecret || request.headers.get("authorization") !== `Bearer ${cronSecret}`) {
    return new Response("Not found.", { status: 404 });
  }

  const githubToken = process.env.GITHUB_DISPATCH_TOKEN;
  if (!githubToken) {
    return Response.json({ error: "GITHUB_DISPATCH_TOKEN is not configured." }, { status: 503 });
  }

  try {
    const newest = await newestBrief();
    if (newest === todayIST()) {
      return Response.json({ ok: true, dispatched: false, reason: "already published", day: newest });
    }

    const response = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${githubToken}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
        cache: "no-store",
      }
    );
    if (response.status !== 204) {
      return Response.json(
        { error: `GitHub refused the brief dispatch (${response.status}).` },
        { status: 502 }
      );
    }
    return Response.json({ ok: true, dispatched: true, day: todayIST() });
  } catch (error) {
    console.error("[brief cron] dispatch failed:", error.message || error);
    return Response.json({ error: "Could not start the morning brief." }, { status: 502 });
  }
}

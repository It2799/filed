/**
 * Where waitlist signups go.
 *
 * Tries each option in order, so you can pick whichever you set up:
 *
 *  1. Upstash Redis  - set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN.
 *                      Two clicks from the Vercel dashboard (Storage tab), free tier,
 *                      and it needs no npm package because it speaks plain HTTP.
 *  2. A webhook      - set WAITLIST_WEBHOOK_URL. Point it at a Google Sheet script,
 *                      Zapier, Make, Slack, Discord - anything that takes a POST.
 *  3. A local file   - only when running on your own machine. Vercel's filesystem is
 *                      read-only, so this never fires in production.
 *
 * If none are set the signup is accepted and logged, so the page still works while
 * you decide. Nothing is silently lost - the response tells you which one was used.
 */

const KEY = "waitlist";

// Vercel names these KV_REST_API_* when you add Upstash from its dashboard, but
// UPSTASH_REDIS_REST_* if you bring your own. Accept either.
function redisUrl() {
  return process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
}
function redisToken() {
  return process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;
}

function upstashConfigured() {
  return Boolean(redisUrl() && redisToken());
}

async function upstash(command) {
  const res = await fetch(redisUrl(), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${redisToken()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Upstash ${res.status}: ${await res.text()}`);
  return (await res.json()).result;
}

/** Returns { ok, backend, alreadyJoined } */
export async function addEmail(email, meta = {}) {
  const record = JSON.stringify({ email, ...meta, at: new Date().toISOString() });

  if (upstashConfigured()) {
    // A sorted set keyed by email keeps it de-duplicated automatically.
    const added = await upstash(["HSETNX", KEY, email, record]);
    return { ok: true, backend: "upstash", alreadyJoined: added === 0 };
  }

  if (process.env.WAITLIST_WEBHOOK_URL) {
    const res = await fetch(process.env.WAITLIST_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: record,
    });
    if (!res.ok) throw new Error(`Webhook ${res.status}`);
    return { ok: true, backend: "webhook", alreadyJoined: false };
  }

  // Local development only. De-duplicates so it behaves like the real backend.
  if (process.env.NODE_ENV !== "production") {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const file = path.join(process.cwd(), "waitlist.local.jsonl");

    const existing = await listEmails();
    if (existing.some((r) => r.email === email)) {
      return { ok: true, backend: "local-file", alreadyJoined: true };
    }

    await fs.appendFile(file, record + "\n", "utf8");
    return { ok: true, backend: "local-file", alreadyJoined: false };
  }

  console.log("[waitlist] no storage configured, signup was:", record);
  return { ok: true, backend: "none-configured", alreadyJoined: false };
}

export async function listEmails() {
  if (upstashConfigured()) {
    const all = await upstash(["HGETALL", KEY]);
    const out = [];
    for (let i = 0; i < all.length; i += 2) {
      try {
        out.push(JSON.parse(all[i + 1]));
      } catch {
        out.push({ email: all[i] });
      }
    }
    return out;
  }

  if (process.env.NODE_ENV !== "production") {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    try {
      const txt = await fs.readFile(
        path.join(process.cwd(), "waitlist.local.jsonl"), "utf8");
      return txt.trim().split("\n").filter(Boolean).map((l) => JSON.parse(l));
    } catch {
      return [];
    }
  }

  return [];
}

export async function count() {
  if (upstashConfigured()) return Number(await upstash(["HLEN", KEY])) || 0;
  return (await listEmails()).length;
}

import { isAdmin } from "../../../../lib/admin-auth";
import { listEmails } from "../../../../lib/store";
import { listUsersForAdmin } from "../../../../lib/users";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function privateJson(body, status = 200) {
  return Response.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private, max-age=0" },
  });
}

function iso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function newest(...values) {
  return values.filter(Boolean).sort().at(-1) || null;
}

async function traffic() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return { total: 0, unique: 0, live: 0 };
  const now = Math.floor(Date.now() / 1000);
  try {
    const response = await fetch(`${url}/pipeline`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify([
        ["GET", "mt:visits:total"],
        ["PFCOUNT", "mt:visits:uniq"],
        ["ZCOUNT", "mt:visits:live", now - 300, "+inf"],
      ]),
      cache: "no-store",
    });
    const result = await response.json();
    const values = Array.isArray(result) ? result.map((item) => item.result) : [];
    return {
      total: Number(values[0] || 0),
      unique: Number(values[1] || 0),
      live: Number(values[2] || 0),
    };
  } catch {
    return { total: 0, unique: 0, live: 0 };
  }
}

export async function GET(request) {
  if (!isAdmin(request)) return privateJson({ error: "Unauthorized." }, 401);

  try {
    const [mongoRows, waitlistRows, visitTotals] = await Promise.all([
      listUsersForAdmin(),
      listEmails(),
      traffic(),
    ]);

    const members = new Map();
    const ensure = (email) => {
      const clean = String(email || "").trim().toLowerCase();
      if (!clean) return null;
      if (!members.has(clean)) {
        members.set(clean, {
          email: clean,
          phone: null,
          sources: new Set(),
          verified: false,
          subscribed: false,
          createdAt: null,
          lastLoginAt: null,
          lastActivityAt: null,
        });
      }
      return members.get(clean);
    };

    for (const row of mongoRows) {
      const member = ensure(row.email);
      if (!member) continue;
      member.phone = row.phone || member.phone;
      member.verified = Boolean(row.emailVerifiedAt);
      member.subscribed = Boolean(row.briefSubscribed);
      member.createdAt = iso(row.createdAt);
      member.lastLoginAt = iso(row.lastLoginAt);
      if (member.verified) member.sources.add("Login");
      if (member.subscribed) {
        const source = String(row.briefSubscriptionSource || "brief").toLowerCase();
        member.sources.add(source === "club" ? "Join page" : source === "brief" ? "Newsletter" : source);
      }
      member.lastActivityAt = newest(
        member.createdAt,
        member.lastLoginAt,
        iso(row.emailVerifiedAt),
        iso(row.updatedAt),
        iso(row.briefSubscribedAt),
        iso(row.briefSubscriptionUpdatedAt)
      );
    }

    for (const row of waitlistRows) {
      const member = ensure(row.email);
      if (!member) continue;
      member.phone = member.phone || row.phone || null;
      member.subscribed = true;
      const source = String(row.source || "waitlist").toLowerCase();
      member.sources.add(source === "club" ? "Join page" : source === "brief" ? "Newsletter" : source);
      member.createdAt = member.createdAt || iso(row.at);
      member.lastActivityAt = newest(member.lastActivityAt, iso(row.at));
    }

    const rows = [...members.values()].map((member) => ({
      ...member,
      sources: [...member.sources],
    })).sort((a, b) => String(b.lastActivityAt || b.createdAt || "")
      .localeCompare(String(a.lastActivityAt || a.createdAt || "")));

    const sourceCounts = {};
    for (const member of rows) {
      for (const source of member.sources) sourceCounts[source] = (sourceCounts[source] || 0) + 1;
    }
    return privateJson({
      generatedAt: new Date().toISOString(),
      traffic: visitTotals,
      totals: {
        members: rows.length,
        verified: rows.filter((row) => row.verified).length,
        subscribed: rows.filter((row) => row.subscribed).length,
        withPhone: rows.filter((row) => row.phone).length,
      },
      sourceCounts,
      members: rows,
    });
  } catch (error) {
    console.error("[admin] dashboard load failed:", error.message || error);
    return privateJson({ error: "Could not load admin data." }, 503);
  }
}

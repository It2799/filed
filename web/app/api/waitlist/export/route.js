import { listEmails } from "../../../../lib/store";

export const dynamic = "force-dynamic";

/**
 * Download the list as CSV:  /api/waitlist/export?key=YOUR_ADMIN_KEY
 * Set ADMIN_KEY in your Vercel environment variables. Without it, this is off.
 */
export async function GET(request) {
  const expected = process.env.ADMIN_KEY;
  if (!expected) {
    return new Response("Export is disabled. Set ADMIN_KEY to turn it on.",
                        { status: 404 });
  }

  const given = new URL(request.url).searchParams.get("key") || "";
  if (given !== expected) {
    return new Response("Not found.", { status: 404 });
  }

  const rows = await listEmails();
  rows.sort((a, b) => String(a.at).localeCompare(String(b.at)));

  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = ["email,joined_at,source",
               ...rows.map((r) => [r.email, r.at, r.source].map(esc).join(","))].join("\n");

  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="waitlist.csv"',
    },
  });
}

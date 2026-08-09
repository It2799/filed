import { addEmail, count } from "../../../lib/store";

export const dynamic = "force-dynamic";

// Deliberately loose - it only needs to catch typos, not police what a valid
// address looks like. Real validation happens when you actually email them.
const LOOKS_LIKE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Bad request." }, { status: 400 });
  }

  // Honeypot: a field hidden from people but filled in by simple bots.
  if (body.company) return Response.json({ ok: true, joined: true });

  const email = String(body.email || "").trim().toLowerCase();

  if (!LOOKS_LIKE_EMAIL.test(email) || email.length > 254) {
    return Response.json(
      { error: "That doesn't look like an email address." }, { status: 400 });
  }

  try {
    const result = await addEmail(email, {
      source: String(body.source || "landing").slice(0, 40),
    });
    return Response.json({
      ok: true,
      joined: true,
      alreadyJoined: result.alreadyJoined,
      backend: result.backend,
    });
  } catch (err) {
    console.error("[waitlist] save failed:", err);
    return Response.json(
      { error: "Couldn't save that. Please try again in a moment." }, { status: 500 });
  }
}

export async function GET() {
  try {
    return Response.json({ count: await count() });
  } catch {
    return Response.json({ count: 0 });
  }
}

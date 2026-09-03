/**
 * Step two: check the code and sign them in.
 *
 *   POST /api/auth/verify   { channel, identifier, code }
 *
 * On success this sets the session cookie. Nothing else in the app has to know
 * how sign-in works - it only has to read that cookie.
 */

import { normalisePhone } from "../../../../lib/phone";
import { check } from "../../../../lib/otp";
import { make, cookieHeader } from "../../../../lib/session";
import { addEmail } from "../../../../lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function tidy(channel, raw) {
  const given = String(raw || "").trim();
  if (channel === "email") {
    const email = given.toLowerCase();
    return EMAIL.test(email) && email.length <= 254 ? `email:${email}` : null;
  }
  if (channel === "whatsapp") {
    const phone = normalisePhone(given);
    return phone ? `whatsapp:${phone}` : null;
  }
  return null;
}

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Send JSON." }, { status: 400 });
  }

  const channel = body.channel === "whatsapp" ? "whatsapp" : "email";
  const id = tidy(channel, body.identifier);
  if (!id) return Response.json({ error: "Start again." }, { status: 400 });

  const verdict = await check(id, body.code);

  if (!verdict.ok) {
    if (verdict.reason === "not_configured") {
      return Response.json(
        { error: "Signing in is not switched on yet.", missing: verdict.missing },
        { status: 503 }
      );
    }
    if (verdict.reason === "too_many_attempts") {
      return Response.json(
        { error: "Too many wrong codes. Ask for a new one." },
        { status: 429 }
      );
    }
    return Response.json(
      {
        error: "That code is wrong or has expired.",
        attemptsLeft: verdict.attemptsLeft,
      },
      { status: 401 }
    );
  }

  const cookie = make({ id, channel });
  if (!cookie) {
    return Response.json({ error: "Signing in is not switched on yet." }, { status: 503 });
  }

  // Somebody who has just proved they own an address belongs on the list, and
  // this is the only moment we know the address is real. Failing to record it
  // must not fail the sign-in, though - they proved who they are either way.
  if (channel === "email") {
    try {
      await addEmail(id.slice(6), { via: "otp-login" });
    } catch (e) {
      console.error("[auth] could not record the signup:", e.message || e);
    }
  }

  return new Response(
    JSON.stringify({ ok: true, id: id.slice(id.indexOf(":") + 1), channel }),
    {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Set-Cookie": cookieHeader(cookie),
      },
    }
  );
}

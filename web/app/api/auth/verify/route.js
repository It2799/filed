/** Verify the email OTP, persist the reader profile, and start a session. */

import { check } from "../../../../lib/otp";
import { make, cookieHeader } from "../../../../lib/session";
import { addEmail } from "../../../../lib/store";
import { saveVerifiedUser } from "../../../../lib/users";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Send JSON." }, { status: 400 });
  }

  const email = String(body.email || body.identifier || "").trim().toLowerCase();
  if (!EMAIL.test(email) || email.length > 254) {
    return Response.json({ error: "Start again with your email address." }, { status: 400 });
  }

  const id = `email:${email}`;
  const verdict = await check(id, body.code);
  if (!verdict.ok) {
    if (verdict.reason === "not_configured") {
      return Response.json({ error: "Email verification is not configured yet." }, { status: 503 });
    }
    if (verdict.reason === "too_many_attempts") {
      return Response.json({ error: "Too many wrong codes. Ask for a new one." }, { status: 429 });
    }
    return Response.json(
      { error: "That code is wrong or has expired.", attemptsLeft: verdict.attemptsLeft },
      { status: 401 }
    );
  }

  const phone = verdict.metadata?.phone || null;
  try {
    await saveVerifiedUser({ email, phone });
  } catch (error) {
    console.error("[auth] could not save the account:", error.message || error);
    return Response.json(
      { error: "Your email was verified, but we could not save the account. Try again." },
      { status: 503 }
    );
  }

  const cookie = make({ id, channel: "email" });
  if (!cookie) {
    return Response.json({ error: "Signing in is not configured yet." }, { status: 503 });
  }

  try {
    await addEmail(email, { via: "otp-login" });
  } catch (error) {
    console.error("[auth] could not record the signup:", error.message || error);
  }

  return new Response(JSON.stringify({ ok: true, id: email, channel: "email" }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": cookieHeader(cookie),
    },
  });
}

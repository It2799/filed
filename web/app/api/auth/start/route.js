/** Start email verification for a protected-page sign-in.
 * New reader: email -> phone -> OTP.
 * Returning reader: email -> OTP; the saved phone is not requested again.
 */

import { normalisePhone } from "../../../../lib/phone";
import { issue } from "../../../../lib/otp";
import { sendEmailCode } from "../../../../lib/notify";
import { configured as usersConfigured, findByEmail } from "../../../../lib/users";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function tidyEmail(raw) {
  const email = String(raw || "").trim().toLowerCase();
  return EMAIL.test(email) && email.length <= 254 ? email : null;
}

export async function POST(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Send JSON." }, { status: 400 });
  }

  const email = tidyEmail(body.email || body.identifier);
  if (!email) {
    return Response.json({ error: "Enter a valid email address." }, { status: 400 });
  }
  if (!usersConfigured()) {
    return Response.json({ error: "Account storage is not connected yet." }, { status: 503 });
  }

  let existing;
  try {
    existing = await findByEmail(email);
  } catch (error) {
    console.error("[auth] could not read the account database:", error.message || error);
    return Response.json(
      { error: "We could not check your account just now. Please try again." },
      { status: 503 }
    );
  }

  const returning = Boolean(existing?.phone);
  let phone = existing?.phone || null;
  if (!returning) {
    phone = normalisePhone(body.phone);
    if (!phone) {
      return Response.json({
        ok: false,
        needsPhone: true,
        error: body.phone
          ? "Enter a valid 10-digit Indian mobile number."
          : "Add your mobile number once to finish creating your account.",
      }, { status: 409 });
    }
  }

  const id = `email:${email}`;
  const made = await issue(id, { email, phone, returning });
  if (!made.ok && made.reason === "not_configured") {
    return Response.json({ error: "Email verification is not configured yet." }, { status: 503 });
  }
  if (!made.ok && made.reason === "too_many") {
    const mins = Math.ceil((made.retryInSeconds || 900) / 60);
    return Response.json(
      { error: `Too many codes requested. Try again in ${mins} minute(s).` },
      { status: 429 }
    );
  }
  if (!made.ok) {
    return Response.json({ error: "Could not start sign-in." }, { status: 500 });
  }

  try {
    const sent = await sendEmailCode(email, made.code);
    if (!sent.sent) {
      return Response.json({ error: "Email verification is not connected yet." }, { status: 503 });
    }
  } catch (error) {
    console.error("[auth] could not send the code:", error.message || error);
    return Response.json(
      { error: "We could not send the email just now. Please try again." },
      { status: 502 }
    );
  }

  return Response.json({
    ok: true,
    email,
    returning,
    expiresInSeconds: made.expiresInSeconds,
  });
}

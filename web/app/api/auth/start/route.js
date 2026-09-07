/** Start a temporary OTP-free protected-page sign-in.
 * New reader: email -> phone -> session. Returning reader: email -> session.
 */

import { normalisePhone } from "../../../../lib/phone";
import { make, cookieHeader } from "../../../../lib/session";
import { configured as usersConfigured, findByEmail, saveDirectUser } from "../../../../lib/users";

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
  try {
    await saveDirectUser({ email, phone });
  } catch (error) {
    console.error("[auth] could not save the account:", error.message || error);
    return Response.json(
      { error: "We could not finish signing you in. Please try again." },
      { status: 503 }
    );
  }

  const cookie = make({ id, channel: "email" });
  if (!cookie) return Response.json({ error: "Signing in is not configured yet." }, { status: 503 });

  return new Response(JSON.stringify({
    ok: true,
    authenticated: true,
    email,
    returning,
    id: email,
    channel: "email",
    user: { id: email, channel: "email", phone },
  }), {
    status: 200,
    headers: { "Content-Type": "application/json", "Set-Cookie": cookieHeader(cookie) },
  });
}

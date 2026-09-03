/**
 * Step one of signing in: send a code.
 *
 *   POST /api/auth/start   { channel: "email" | "whatsapp", identifier }
 *
 * The reply never says whether that address or number has been here before.
 * "We sent a code" is the answer either way, because anything else turns this
 * endpoint into a way of asking whether a given person has an account.
 */

import { normalisePhone } from "../../../../lib/phone";
import { issue } from "../../../../lib/otp";
import { sendEmailCode, sendWhatsAppCode } from "../../../../lib/notify";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** The identifier in the one shape we store it in, or null if it is not valid. */
function tidy(channel, raw) {
  const given = String(raw || "").trim();
  if (channel === "email") {
    // Lower-cased, so Ishan@x.com and ishan@x.com are one person and cannot
    // each hold their own code.
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
  if (!id) {
    return Response.json(
      {
        error:
          channel === "email"
            ? "That does not look like an email address."
            : "That does not look like an Indian mobile number.",
      },
      { status: 400 }
    );
  }

  const made = await issue(id);

  if (!made.ok && made.reason === "not_configured") {
    return Response.json(
      {
        error: "Signing in is not switched on yet.",
        missing: made.missing,
      },
      { status: 503 }
    );
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

  const value = id.slice(id.indexOf(":") + 1);
  let result;
  try {
    result =
      channel === "email"
        ? await sendEmailCode(value, made.code)
        : await sendWhatsAppCode(value, made.code);
  } catch (e) {
    console.error("[auth] could not send the code:", e.message || e);
    return Response.json(
      {
        error:
          channel === "email"
            ? "We could not send the email just now. Try WhatsApp instead."
            : "We could not send the WhatsApp message just now. Try email instead.",
      },
      { status: 502 }
    );
  }

  // The channel exists in code but has no credentials in this deployment.
  // Say so plainly rather than claiming a code is on its way.
  if (!result.sent) {
    return Response.json(
      {
        error:
          channel === "email"
            ? "Email sign-in is not connected yet. Try WhatsApp."
            : "WhatsApp sign-in is not connected yet. Try email.",
        reason: result.reason,
      },
      { status: 503 }
    );
  }

  return Response.json({
    ok: true,
    channel,
    expiresInSeconds: made.expiresInSeconds,
  });
}

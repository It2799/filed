import { addEmail, count } from "../../../lib/store";
import { normalisePhone } from "../../../lib/phone";
import { confirm } from "../../../lib/notify";
import { configured as usersConfigured, subscribeUser } from "../../../lib/users";
import { configured as kitConfigured, upsertSubscriber } from "../../../lib/kit";

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

  // WhatsApp number is optional, but if given it has to be a real one.
  const rawPhone = String(body.phone || "").trim();
  let phone = null;
  if (rawPhone) {
    phone = normalisePhone(rawPhone);
    if (!phone) {
      return Response.json(
        { error: "That doesn't look like an Indian mobile number. 10 digits, starting 6-9." },
        { status: 400 });
    }
  }

  let result;
  try {
    if (usersConfigured()) {
      await subscribeUser({
        email,
        phone,
        source: String(body.source || "landing").slice(0, 40),
      });
    }
    result = await addEmail(email, {
      phone,
      wantsWhatsApp: Boolean(phone),
      source: String(body.source || "landing").slice(0, 40),
    });
  } catch (err) {
    console.error("[waitlist] save failed:", err);
    return Response.json(
      { error: "Couldn't save that. Please try again in a moment." }, { status: 500 });
  }

  let kitSynced = false;
  try {
    kitSynced = Boolean((await upsertSubscriber(email)).ok);
  } catch (error) {
    console.error("[waitlist] Kit sync failed:", error.message || error);
  }

  // Confirmations are best-effort. A failure here must never lose the signup,
  // so this is deliberately after the save and never throws.
  let notified = {};
  if (!result.alreadyJoined) {
    notified = await confirm({ email, phone });
  }

  return Response.json({
    ok: true,
    joined: true,
    alreadyJoined: result.alreadyJoined,
    backend: result.backend,
    profileSaved: usersConfigured(),
    kitConfigured: kitConfigured(),
    kitSynced,
    gaveWhatsApp: Boolean(phone),
    emailSent: Boolean(notified.email?.sent),
    whatsappSent: Boolean(notified.whatsapp?.sent),
  });
}

export async function GET() {
  try {
    return Response.json({ count: await count() });
  } catch {
    return Response.json({ count: 0 });
  }
}

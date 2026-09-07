import { addEmail, count } from "../../../lib/store";
import { normalisePhone } from "../../../lib/phone";
import { configured as usersConfigured, saveLeadUser, subscribeUser } from "../../../lib/users";

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
  const source = String(body.source || "landing").slice(0, 40).toLowerCase();
  const isNewsletterSignup = source === "brief" || source === "landing";

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
      if (isNewsletterSignup) await subscribeUser({ email, phone, source });
      else await saveLeadUser({ email, phone, source });
    }
    result = await addEmail(email, {
      phone,
      wantsWhatsApp: Boolean(phone),
      source,
    });
  } catch (err) {
    console.error("[waitlist] save failed:", err);
    return Response.json(
      { error: "Couldn't save that. Please try again in a moment." }, { status: 500 });
  }

  return Response.json({
    ok: true,
    joined: true,
    alreadyJoined: result.alreadyJoined,
    backend: result.backend,
    profileSaved: usersConfigured(),
    newsletterSignup: isNewsletterSignup,
    gaveWhatsApp: Boolean(phone),
    emailSent: false,
    whatsappSent: false,
  });
}

export async function GET() {
  try {
    return Response.json({ count: await count() });
  } catch {
    return Response.json({ count: 0 });
  }
}

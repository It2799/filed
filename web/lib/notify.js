/**
 * Confirmation messages. Both channels are optional and both fail quietly:
 * a signup is never lost because a message didn't go out.
 *
 * EMAIL - set RESEND_API_KEY and FROM_EMAIL.
 *   Free key at resend.com, 3,000 emails/month. Until you've verified your own
 *   domain you can send from "onboarding@resend.dev", but only to your own
 *   address - so it's fine for testing, not for real signups.
 *
 * WHATSAPP - set WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID.
 *   This needs a Meta WhatsApp Business account, a phone number that has never
 *   been used on normal WhatsApp, and a message template Meta has approved.
 *   Until all that is done this stays switched off, and the site instead shows
 *   a "confirm on WhatsApp" button that needs no API at all.
 */

const TIMEOUT_MS = 6000;

function timeout() {
  return AbortSignal.timeout(TIMEOUT_MS);
}

// ---------------------------------------------------------------- email

export async function sendEmail(to) {
  const key = process.env.RESEND_API_KEY;
  const from = process.env.FROM_EMAIL;
  if (!key || !from) return { sent: false, reason: "email not configured" };

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    signal: timeout(),
    body: JSON.stringify({
      from,
      to: [to],
      subject: "You're on the Market Tide waitlist",
      text:
        "Thanks for joining Market Tide.\n\n"
        + "Every trading day NSE and BSE publish about 3,600 corporate announcements. "
        + "Roughly 250 of them matter. We read those and send you what they actually say, "
        + "in plain English.\n\n"
        + "We'll email you once when it opens up. Nothing else, and we won't pass your "
        + "address to anyone.\n\n"
        + "Market Tide summarises public exchange filings. It is not investment advice.\n",
    }),
  });

  if (!res.ok) throw new Error(`Resend ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return { sent: true };
}

// ---------------------------------------------------------------- whatsapp

export async function sendWhatsApp(phone) {
  const token = process.env.WHATSAPP_TOKEN;
  const fromId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  if (!token || !fromId) return { sent: false, reason: "whatsapp not configured" };

  // Meta only allows pre-approved templates for the first message to someone.
  const template = process.env.WHATSAPP_TEMPLATE_NAME || "waitlist_confirmation";
  const lang = process.env.WHATSAPP_TEMPLATE_LANG || "en";

  const res = await fetch(`https://graph.facebook.com/v21.0/${fromId}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    signal: timeout(),
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to: phone.replace(/^\+/, ""),        // Meta wants digits only
      type: "template",
      template: { name: template, language: { code: lang } },
    }),
  });

  if (!res.ok) throw new Error(`WhatsApp ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return { sent: true };
}

// ---------------------------------------------------------------- both

/** Never throws. Returns what happened on each channel so the API can report it. */
export async function confirm({ email, phone }) {
  const jobs = [];
  jobs.push(sendEmail(email).then((r) => ["email", r]).catch((e) => ["email", { sent: false, error: String(e.message || e) }]));
  if (phone) {
    jobs.push(sendWhatsApp(phone).then((r) => ["whatsapp", r]).catch((e) => ["whatsapp", { sent: false, error: String(e.message || e) }]));
  }

  const out = {};
  for (const [channel, result] of await Promise.all(jobs)) {
    out[channel] = result;
    if (result.error) console.error(`[notify] ${channel} failed:`, result.error);
  }
  return out;
}

// ---------------------------------------------------------------- sign-in codes

/**
 * The six-digit code that signs somebody in.
 *
 * Kept apart from the waitlist messages above because the rules are different:
 * a confirmation that does not arrive is a small disappointment, and a sign-in
 * code that does not arrive is a locked door. So these THROW on failure, and
 * the route tells the reader to try the other channel rather than leaving them
 * waiting for something that is never coming.
 */
export async function sendEmailCode(to, code) {
  const key = process.env.RESEND_API_KEY;
  const from = process.env.FROM_EMAIL;
  if (!key || !from) return { sent: false, reason: "email not configured" };

  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
    signal: timeout(),
    body: JSON.stringify({
      from,
      to: [to],
      subject: `${code} is your Market Tide sign-in code`,
      text:
        `Your sign-in code is ${code}\n\n`
        + "It works for the next 10 minutes and can be used once.\n\n"
        + "If you didn't ask to sign in, ignore this email - somebody typed "
        + "your address by mistake, and without this code they cannot get in.\n",
    }),
  });

  if (!res.ok) {
    throw new Error(`Resend ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  return { sent: true };
}

/**
 * The same code over WhatsApp.
 *
 * Meta requires an AUTHENTICATION-category template for this, which is a
 * different thing from the marketing template the waitlist uses: it renders
 * with a copy-code button, it may not carry any other text, and the code goes
 * in both the body variable and the button. Sending a one-time code through a
 * marketing template is against Meta's rules and gets a number blocked.
 */
export async function sendWhatsAppCode(phone, code) {
  const token = process.env.WHATSAPP_TOKEN;
  const fromId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  if (!token || !fromId) return { sent: false, reason: "whatsapp not configured" };

  const template = process.env.WHATSAPP_OTP_TEMPLATE_NAME || "login_code";
  const lang = process.env.WHATSAPP_OTP_TEMPLATE_LANG || "en";

  const res = await fetch(`https://graph.facebook.com/v21.0/${fromId}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    signal: timeout(),
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to: phone.replace(/^\+/, ""),
      type: "template",
      template: {
        name: template,
        language: { code: lang },
        components: [
          { type: "body", parameters: [{ type: "text", text: code }] },
          {
            type: "button",
            sub_type: "url",
            index: "0",
            parameters: [{ type: "text", text: code }],
          },
        ],
      },
    }),
  });

  if (!res.ok) {
    throw new Error(`WhatsApp ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  return { sent: true };
}

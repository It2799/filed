/**
 * Who is signed in, and whether signing in works at all.
 *
 *   GET  /api/auth/me      -> { user, channels }
 *   POST /api/auth/logout  -> clears the cookie (see ../logout)
 *
 * `channels` lets the sign-in page offer only what this deployment can
 * actually deliver, instead of presenting a WhatsApp button that fails after
 * the reader has typed their number.
 */

import { currentUser } from "../../../../lib/session";
import { configured } from "../../../../lib/otp";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request) {
  const user = currentUser(request);

  return Response.json({
    user: user ? { id: user.id.slice(user.id.indexOf(":") + 1), channel: user.channel } : null,
    channels: {
      email: Boolean(process.env.RESEND_API_KEY && process.env.FROM_EMAIL),
      whatsapp: Boolean(
        process.env.WHATSAPP_TOKEN && process.env.WHATSAPP_PHONE_NUMBER_ID
      ),
    },
    ready: configured(),
  });
}

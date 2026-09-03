/**
 * Sign out: throw the cookie away.
 *
 * POST, not GET. A GET would let any page on the internet sign a reader out
 * by embedding an image pointing at this URL.
 */

import { clearHeader } from "../../../../lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": clearHeader(),
    },
  });
}

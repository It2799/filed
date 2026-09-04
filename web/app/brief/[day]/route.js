import { briefPdf } from "../../../lib/brief";
import { currentUser } from "../../../lib/session";
import { authReady } from "../../../lib/auth-ready";

export const dynamic = "force-dynamic";

/**
 * The brief for one day:  /brief/2026-09-01
 *
 * A dated issue is part of member access. Direct links therefore return to the
 * sign-in modal instead of bypassing the protected Daily Brief page.
 */
export async function GET(request, { params }) {
  if (authReady() && !currentUser(request)) {
    return Response.redirect(new URL("/brief?signin=1", request.url), 307);
  }
  const { day } = await params;
  const iso = String(day || "").replace(/\.pdf$/, "");

  const pdf = await briefPdf(iso);
  if (!pdf) {
    return new Response("No brief for that day.", {
      status: 404,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  // ?download=1 saves the file instead of opening it in the browser's viewer.
  // Both are wanted: reading it in a tab is the common case, but people share
  // this in WhatsApp groups and need the file itself to do that.
  const wantsFile = new URL(request.url).searchParams.has("download");

  return new Response(pdf, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition":
        `${wantsFile ? "attachment" : "inline"}; ` +
        `filename="market-tide-brief-${iso}.pdf"`,
      "Cache-Control": "private, no-store",
    },
  });
}

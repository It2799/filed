import { briefPdf } from "../../../lib/brief";
import { currentUser } from "../../../lib/session";
import { authReady } from "../../../lib/auth-ready";
import { validBriefAccess } from "../../../lib/brief-access.js";

export const dynamic = "force-dynamic";

/**
 * The brief for one day:  /brief/2026-09-01
 *
 * A dated issue is part of member access. Direct links therefore return to the
 * sign-in modal instead of bypassing the protected Daily Brief page.
 */
export async function GET(request, { params }) {
  const { day } = await params;
  const iso = String(day || "").replace(/\.pdf$/, "");
  const requestUrl = new URL(request.url);
  const emailAccess = validBriefAccess(iso, requestUrl.searchParams.get("access"));
  if (authReady() && !emailAccess && !currentUser(request)) {
    return Response.redirect(new URL("/brief?signin=1", request.url), 307);
  }

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
  const wantsFile = requestUrl.searchParams.has("download");
  // Kit links contain a signed access token and are safe to cache by their
  // complete URL. This lets hundreds of recipients reuse one PDF response
  // instead of pulling the same base64 chunks through Vercel Compute each
  // time. A member who opens the route with a login cookie still receives a
  // private, uncached response.
  const cacheControl = emailAccess
    ? "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"
    : "private, no-store";

  return new Response(pdf, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition":
        `${wantsFile ? "attachment" : "inline"}; ` +
        `filename="market-tide-brief-${iso}.pdf"`,
      "Cache-Control": cacheControl,
    },
  });
}

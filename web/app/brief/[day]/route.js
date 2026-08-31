import { briefPdf } from "../../../lib/brief";

export const dynamic = "force-dynamic";

/**
 * The brief for one day:  /brief/2026-09-01
 *
 * A dated issue never changes once written, so it is cached hard. Anyone can
 * read it - this is the free brief, and a link that asks for a login is a link
 * nobody forwards.
 */
export async function GET(request, { params }) {
  const { day } = await params;
  const iso = String(day || "").replace(/\.pdf$/, "");

  const pdf = await briefPdf(iso);
  if (!pdf) {
    return new Response("No brief for that day.", {
      status: 404,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  return new Response(pdf, {
    headers: {
      "Content-Type": "application/pdf",
      // inline: opens in the browser's viewer rather than dropping a file in
      // Downloads. The filename is still used if the reader chooses to save.
      "Content-Disposition":
        `inline; filename="market-tide-brief-${iso}.pdf"`,
      "Cache-Control": "public, max-age=3600, s-maxage=86400, immutable",
    },
  });
}

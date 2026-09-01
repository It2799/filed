import { briefDays } from "../../../../lib/brief";

export const dynamic = "force-dynamic";

/** The most recent issue we hold, or null. Used by the brief page. */
export async function GET() {
  const days = await briefDays();
  return Response.json(
    { day: days[0] || null },
    { headers: { "Cache-Control": "no-store" } }
  );
}

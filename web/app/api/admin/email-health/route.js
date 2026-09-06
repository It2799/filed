import { correctAdminPassword } from "../../../../lib/admin-auth";
import { diagnoseEmailConnection } from "../../../../lib/notify";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request) {
  if (!correctAdminPassword(request.headers.get("x-admin-password"))) {
    return Response.json({ error: "Not found." }, { status: 404 });
  }
  const result = await diagnoseEmailConnection();
  return Response.json(result, {
    status: result.connected ? 200 : 503,
    headers: { "Cache-Control": "no-store, private, max-age=0" },
  });
}

import crypto from "node:crypto";
import { notFound } from "next/navigation";
import AdminDashboard from "../../mt-ops-7k2p9x/AdminDashboard";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Market Tide Operations",
  robots: { index: false, follow: false, noarchive: true, nocache: true },
};

function sameToken(given, expected) {
  const a = crypto.createHash("sha256").update(String(given || "")).digest();
  const b = crypto.createHash("sha256").update(String(expected || "")).digest();
  return crypto.timingSafeEqual(a, b);
}

export default async function AdminPage({ params }) {
  const { token } = await params;
  const expected = process.env.ADMIN_PATH_TOKEN;
  if (!expected || !sameToken(token, expected)) notFound();
  return <AdminDashboard />;
}

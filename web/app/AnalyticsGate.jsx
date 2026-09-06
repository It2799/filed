"use client";

import { Analytics } from "@vercel/analytics/next";
import { usePathname } from "next/navigation";

export default function AnalyticsGate() {
  const pathname = usePathname();
  if (pathname?.startsWith("/control/")) return null;
  return <Analytics />;
}

"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

const VISITOR_KEY = "mt_visitor_id";
const SESSION_KEY = "mt_visit_session";

function storedId(storage, key) {
  try {
    let id = storage.getItem(key);
    if (!id) {
      id = (crypto.randomUUID?.() || String(Math.random()).slice(2))
        .replace(/-/g, "")
        .slice(0, 32);
      storage.setItem(key, id);
    }
    return id;
  } catch {
    return "";
  }
}

export default function EngagementTracker() {
  const pathname = usePathname();

  useEffect(() => {
    if (!pathname || pathname.startsWith("/control/") || pathname.startsWith("/mt-ops-")) {
      return undefined;
    }

    const payload = (event) => JSON.stringify({
      id: storedId(localStorage, VISITOR_KEY),
      sessionId: storedId(sessionStorage, SESSION_KEY),
      path: pathname,
      event,
    });
    const send = (event, beacon = false) => {
      if (beacon && navigator.sendBeacon) {
        navigator.sendBeacon("/api/visits", new Blob([payload(event)], { type: "application/json" }));
        return;
      }
      fetch("/api/visits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload(event),
        cache: "no-store",
        keepalive: true,
      }).catch(() => {});
    };

    send("pageview");
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") send("heartbeat");
    }, 60000);
    const onVisibility = () => {
      if (document.visibilityState === "hidden") send("heartbeat", true);
      else send("resume");
    };
    const onPageHide = () => send("end", true);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [pathname]);

  return null;
}

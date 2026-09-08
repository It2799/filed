"use client";

import { useEffect, useState } from "react";

/** Read-only traffic counters shown at the foot of the page. */

export default function Visitors() {
  const [n, setN] = useState(null);

  useEffect(() => {
    let dead = false;

    // Page views and active time are recorded globally by EngagementTracker.
    // This footer only reads the counters, so its refresh cannot inflate them.
    const send = () =>
      fetch("/api/visits", { cache: "no-store" })
        .then((r) => r.json())
        .then((d) => !dead && setN(d))
        .catch(() => {});

    send();
    // Keeps the "reading now" figure honest while a tab stays open: the live
    // set only holds the last five minutes, so without this a reader who
    // lingers drops out of their own count.
    const t = setInterval(send, 120000);
    return () => { dead = true; clearInterval(t); };
  }, []);

  if (!n) return null;

  const fmt = (v) => Number(v || 0).toLocaleString("en-IN");

  return (
    <div className="visitors" aria-label="Site traffic">
      <span className="visitors-live">
        <i /> {fmt(n.live)} reading now
      </span>
      <span className="visitors-sep" aria-hidden="true">·</span>
      <span>
        <b>{fmt(n.unique)}</b> unique visitors
      </span>
      <span className="visitors-sep" aria-hidden="true">·</span>
      <span>
        <b>{fmt(n.total)}</b> total visits
      </span>
    </div>
  );
}

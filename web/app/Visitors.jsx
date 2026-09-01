"use client";

import { useEffect, useState } from "react";

/**
 * Visitor counts at the foot of the page.
 *
 * The browser keeps a random id in localStorage so the same person is not
 * counted twice. If localStorage is unavailable - a private window, or a
 * browser set to block site data - the visit still counts towards the total,
 * it simply cannot be told apart from any other, and the strip renders the
 * same either way.
 */

const KEY = "mt_visitor_id";

function visitorId() {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = (crypto.randomUUID?.() || String(Math.random()).slice(2))
        .replace(/-/g, "")
        .slice(0, 32);
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return "";
  }
}

export default function Visitors() {
  const [n, setN] = useState(null);

  useEffect(() => {
    let dead = false;

    const send = () =>
      fetch("/api/visits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: visitorId() }),
        cache: "no-store",
      })
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

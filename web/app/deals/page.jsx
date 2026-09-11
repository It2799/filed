"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "../Nav";

const PAGE = 25;

function money(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  if (v >= 1e7) return `Rs ${(v / 1e7).toFixed(2)} cr`;
  if (v >= 1e5) return `Rs ${(v / 1e5).toFixed(2)} lakh`;
  return `Rs ${v.toLocaleString("en-IN")}`;
}

// Company size, the way an Indian reader says it. Rs 20 crore into a Rs 200
// crore company is a different piece of news from the same Rs 20 crore into a
// Rs 2 lakh crore one.
function cap(n) {
  const v = Number(n) || 0;
  if (!v) return "";
  if (v >= 100000) return `Rs ${(v / 100000).toFixed(2)} lakh cr`;
  if (v >= 1000) return `Rs ${Math.round(v).toLocaleString("en-IN")} cr`;
  return `Rs ${v.toFixed(0)} cr`;
}

function dayLabel(iso) {
  if (!iso) return "";
  const dt = new Date(iso + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - dt) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export default function DealsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [side, setSide] = useState("all");
  const [kind, setKind] = useState("all");
  const [exch, setExch] = useState("all");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    const p = new URLSearchParams({ days: "7", side, kind, exchange: exch });
    if (q.trim()) p.set("q", q.trim());
    fetch(`/api/deals?${p}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch(() => alive && setError("Could not load bulk and block deals."))
      .finally(() => alive && setShown(PAGE));
    return () => {
      alive = false;
    };
  }, [side, kind, exch, q]);

  const rows = useMemo(() => (data?.items || []).slice(0, shown), [data, shown]);
  const counts = data?.counts;

  return (
    <>
      <Nav />
      <main className="wrap">
        <header className="head">
          <h1>Bulk &amp; block deals</h1>
          <p className="sub">
            The large trades both exchanges have to publish by name &mdash; who
            bought, who sold, how much, and at what price.
          </p>
          <p className="note">
            Day trading is taken out. An investor who buys and sells the same
            shares on the same day is reported twice and owns nothing at the
            close, so each name&rsquo;s trades in a company on a day are netted
            and a pure round trip is dropped. Small deals are left out too: a
            bulk deal is half a percent of the company, which in a tiny company
            can be a few lakh rupees.
          </p>
        </header>

        {counts ? (
          <section className="tally">
            <div className="t-card buy">
              <span className="t-n">{counts.buys}</span>
              <span className="t-l">bought</span>
              <span className="t-v">{money(counts.boughtValue)}</span>
            </div>
            <div className="t-card sell">
              <span className="t-n">{counts.sells}</span>
              <span className="t-l">sold</span>
              <span className="t-v">{money(counts.soldValue)}</span>
            </div>
            <div className="t-card">
              <span className="t-n">{counts.total}</span>
              <span className="t-l">deals, last 7 days</span>
            </div>
          </section>
        ) : null}

        <section className="controls">
          <div className="seg">
            {[["all", "All"], ["buy", "Bought"], ["sell", "Sold"]].map(([k, l]) => (
              <button key={k} type="button" className={side === k ? "on" : ""}
                      onClick={() => setSide(k)}>
                {l}
              </button>
            ))}
          </div>
          <div className="seg">
            {[["all", "Both"], ["bulk", "Bulk"], ["block", "Block"]].map(([k, l]) => (
              <button key={k} type="button" className={kind === k ? "on" : ""}
                      onClick={() => setKind(k)}>
                {l}
              </button>
            ))}
          </div>
          <div className="seg">
            {[["all", "NSE + BSE"], ["NSE", "NSE"], ["BSE", "BSE"]].map(([k, l]) => (
              <button key={k} type="button" className={exch === k ? "on" : ""}
                      onClick={() => setExch(k)}>
                {l}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Company or investor"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </section>

        {error ? <p className="empty">{error}</p> : null}
        {!error && !data ? <p className="empty">Loading&hellip;</p> : null}
        {data && !data.items.length ? (
          <p className="empty">
            No deals match. Both exchanges publish these after the close, so
            the trading day itself is quiet.
          </p>
        ) : null}

        <ul className="deals">
          {rows.map((d) => (
            <li key={d.id} className={`deal ${d.side?.toLowerCase() || ""}`}>
              <div className="d-top">
                <span className="co">{d.company}</span>
                {d.mcap ? <span className="cap">{cap(d.mcap)}</span> : null}
                <span className="kind">{d.kind}</span>
                <span className="exch">{d.exchange}</span>
                <span className={`side ${d.side?.toLowerCase() || ""}`}>
                  {d.side}
                </span>
                <span className="when">{dayLabel(d.day)}</span>
              </div>
              <div className="d-who">
                <strong>{d.who}</strong>
              </div>
              <div className="d-nums">
                <span className="val">{money(d.value)}</span>
                <span>{Number(d.shares || 0).toLocaleString("en-IN")} shares</span>
                {d.price ? (
                  <span className="price">
                    at Rs {Number(d.price).toLocaleString("en-IN")}
                  </span>
                ) : null}
                {d.netted ? (
                  <span className="netted">
                    net of {Number(
                      d.side?.toLowerCase() === "buy" ? d.gross_sell : d.gross_buy
                    ).toLocaleString("en-IN")} the same day
                  </span>
                ) : null}
              </div>
              {d.remarks ? <p className="d-note">{d.remarks}</p> : null}
            </li>
          ))}
        </ul>

        {data && data.items.length > shown ? (
          <button className="more" type="button"
                  onClick={() => setShown(shown + PAGE)}>
            Show more ({data.items.length - shown} left)
          </button>
        ) : null}

        <p className="verify">
          From the bulk and block deal reports NSE and BSE publish each trading
          day. Prices are the weighted average the exchange reports. Nothing
          here is advice.
        </p>
      </main>

      <style jsx>{`
        .wrap { max-width: 900px; margin: 0 auto; padding: 24px 16px 64px; }
        .head h1 { margin: 0 0 6px; font-size: 1.7rem; }
        .sub { margin: 0 0 8px; color: #444; line-height: 1.5; }
        .note { margin: 0 0 18px; color: #777; font-size: 0.86rem; line-height: 1.5; }
        .tally { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
        .t-card {
          flex: 1 1 150px; border: 1px solid #e6e6e6; border-radius: 10px;
          padding: 10px 12px; display: flex; flex-direction: column; gap: 2px;
        }
        .t-card.buy { border-color: #b9e2c4; background: #f3fbf5; }
        .t-card.sell { border-color: #f0c8c8; background: #fdf5f5; }
        .t-n { font-size: 1.5rem; font-weight: 650; }
        .t-l { font-size: 0.8rem; color: #666; }
        .t-v { font-size: 0.86rem; color: #333; }
        .controls { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
        .seg { display: inline-flex; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
        .seg button {
          border: 0; background: #fff; padding: 7px 11px; cursor: pointer;
          font-size: 0.85rem; border-right: 1px solid #eee;
        }
        .seg button:last-child { border-right: 0; }
        .seg button.on { background: #111; color: #fff; }
        .search {
          flex: 1 1 180px; min-width: 160px; padding: 7px 11px;
          border: 1px solid #ddd; border-radius: 8px; font-size: 0.85rem;
        }
        .deals { list-style: none; margin: 0; padding: 0; }
        .deal {
          border: 1px solid #eee; border-left: 3px solid #ddd; border-radius: 8px;
          padding: 11px 13px; margin-bottom: 9px;
        }
        .deal.buy { border-left-color: #3aa35c; }
        .deal.sell { border-left-color: #cc4b4b; }
        .d-top { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
        .co { font-weight: 620; }
        .cap {
          font-size: 0.72rem; color: #555; background: #f1f1f1;
          padding: 1px 7px; border-radius: 99px;
        }
        .kind, .exch { font-size: 0.72rem; color: #888; }
        .side { font-size: 0.72rem; padding: 1px 7px; border-radius: 99px; background: #eee; }
        .side.buy { background: #e4f5e9; color: #1e6b38; }
        .side.sell { background: #fbe7e7; color: #8c2b2b; }
        .when { margin-left: auto; font-size: 0.76rem; color: #999; }
        .d-who { margin-top: 4px; font-size: 0.92rem; }
        .d-nums {
          margin-top: 5px; display: flex; gap: 12px; flex-wrap: wrap;
          font-size: 0.84rem; color: #555;
        }
        .val { font-weight: 600; color: #222; }
        .price, .netted { color: #888; }
        .d-note { margin: 5px 0 0; font-size: 0.82rem; color: #777; }
        .more {
          display: block; margin: 12px auto; padding: 8px 16px;
          border: 1px solid #ddd; border-radius: 8px; background: #fff; cursor: pointer;
        }
        .empty { color: #777; padding: 18px 0; }
        .verify { margin-top: 26px; color: #999; font-size: 0.78rem; line-height: 1.5; }
        @media (prefers-color-scheme: dark) {
          .sub { color: #bbb; }
          .note, .when, .price, .netted, .kind, .exch, .d-note { color: #888; }
          .t-card { border-color: #333; }
          .t-card.buy { background: #102114; border-color: #2c5c3a; }
          .t-card.sell { background: #241111; border-color: #5e2b2b; }
          .deal { border-color: #2a2a2a; }
          .cap { background: #222; color: #aaa; }
          .seg { border-color: #333; }
          .seg button { background: #161616; color: #ddd; border-right-color: #262626; }
          .seg button.on { background: #fff; color: #111; }
          .search { background: #161616; color: #ddd; border-color: #333; }
          .more { background: #161616; color: #ddd; border-color: #333; }
          .val { color: #eee; }
        }
      `}</style>
    </>
  );
}

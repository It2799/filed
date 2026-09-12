"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "../Nav";
import {
  byDay, count, dayLabel, mcapLabel, mcapTier, money, name, price,
} from "../fmt";

const PAGE = 30;

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

  const items = data?.items || [];
  const groups = useMemo(() => byDay(items.slice(0, shown)), [items, shown]);
  const counts = data?.counts;

  return (
    <>
      <Nav />
      <main className="wrap page">
        <header className="head">
          <h1>The big trades, by name</h1>
          <p className="lede">
            When one investor buys or sells a large slice of a company in a
            single day, the exchange has to publish their name. Funds, family
            offices, promoters &mdash; this is who moved, and at what price.
          </p>
          <p className="aside">
            Day trading is taken out. Someone who buys and sells the same shares
            in one day gets reported twice and owns nothing by the close, so
            each name&rsquo;s trades in a company on a day are netted and the
            pure round trips dropped. Tiny deals go too &mdash; a bulk deal is
            half a percent of the company, which in a small one can be a few
            lakh rupees.
          </p>
        </header>

        {/* Counts, not rupee totals. A total here would add up buying across
            dozens of unrelated companies, which is not a number that means
            anything. */}
        {counts ? (
          <section className="tally">
            <div className="t-card pos">
              <span className="t-n">{counts.buys}</span>
              <span className="t-l">bought</span>
            </div>
            <div className="t-card neg">
              <span className="t-n">{counts.sells}</span>
              <span className="t-l">sold</span>
            </div>
            <div className="t-card">
              <span className="t-n">{counts.total}</span>
              <span className="t-l">in the last 7 days</span>
            </div>
          </section>
        ) : null}

        <section className="controls">
          <div className="seg">
            {[["all", "All"], ["buy", "Buying"], ["sell", "Selling"]].map(
              ([k, l]) => (
                <button
                  key={k}
                  type="button"
                  className={side === k ? "on" : ""}
                  onClick={() => setSide(k)}
                >
                  {l}
                </button>
              )
            )}
          </div>
          <div className="seg">
            {[["all", "Both kinds"], ["bulk", "Bulk"], ["block", "Block"]].map(
              ([k, l]) => (
                <button
                  key={k}
                  type="button"
                  className={kind === k ? "on" : ""}
                  onClick={() => setKind(k)}
                >
                  {l}
                </button>
              )
            )}
          </div>
          <div className="seg">
            {[["all", "Both exchanges"], ["NSE", "NSE"], ["BSE", "BSE"]].map(
              ([k, l]) => (
                <button
                  key={k}
                  type="button"
                  className={exch === k ? "on" : ""}
                  onClick={() => setExch(k)}
                >
                  {l}
                </button>
              )
            )}
          </div>
          <input
            className="search"
            placeholder="Search a company or an investor"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </section>

        {error ? <p className="empty">{error}</p> : null}
        {!error && !data ? <p className="empty">Loading&hellip;</p> : null}
        {data && !items.length ? (
          <p className="empty">
            Nothing matches that. Both exchanges publish these after the close,
            so the trading day itself is quiet.
          </p>
        ) : null}

        {groups.map((g) => (
          <section key={g.day} className="day">
            <h2 className="day-head">
              <span>{dayLabel(g.day)}</span>
              <span className="day-n">
                {g.rows.length} {g.rows.length === 1 ? "deal" : "deals"}
              </span>
            </h2>

            {g.rows.map((d) => {
              const bought = d.side === "Buy";
              const tone = bought ? "pos" : "neg";
              return (
                <article key={d.id} className={`card tone-${tone}`}>
                  <div className="card-top">
                    <div className="left">
                      <div className="co-line">
                        <span className="co">{name(d.company)}</span>
                        {mcapLabel(d.mcap) ? (
                          <span className={`mcap ${mcapTier(d.mcap)}`}>
                            {mcapLabel(d.mcap)}
                          </span>
                        ) : null}
                      </div>
                      <div className="who">
                        {name(d.who)}
                        <span className="tag">
                          {d.kind} deal &middot; {d.exchange}
                        </span>
                      </div>
                    </div>

                    {/* The money column, running straight down the right edge
                        so sizes can be scanned without reading a word. */}
                    <div className="right">
                      <span className={`b ${tone}`}>
                        {bought ? "Bought" : "Sold"}
                      </span>
                      {d.value ? (
                        <span className="amt">{money(d.value)}</span>
                      ) : null}
                    </div>
                  </div>

                  <p className="line">
                    {d.shares ? (
                      <span className="qty">{count(d.shares)} shares</span>
                    ) : null}
                    {price(d.price) ? (
                      <span className="at">at {price(d.price)} each</span>
                    ) : null}
                  </p>

                  {d.netted ? (
                    <p className="tail">
                      Net figure &mdash; they also {bought ? "sold" : "bought"}{" "}
                      {count((bought ? d.gross_sell : d.gross_buy) || 0)} shares
                      the same day.
                    </p>
                  ) : null}
                  {d.remarks ? <p className="tail">{d.remarks}</p> : null}
                </article>
              );
            })}
          </section>
        ))}

        {data && items.length > shown ? (
          <button
            className="more"
            type="button"
            onClick={() => setShown(shown + PAGE)}
          >
            Show {Math.min(PAGE, items.length - shown)} more
          </button>
        ) : null}

        <p className="verify">
          From the bulk and block deal reports NSE and BSE publish each trading
          day. Prices are the weighted average the exchange reports. Nothing
          here is advice.
        </p>
      </main>

      <style jsx>{`
        .page { padding-bottom: 72px; }
        .head { padding-top: 26px; }
        .head h1 {
          margin: 0 0 10px;
          font-size: 29px;
          line-height: 1.2;
          letter-spacing: -0.025em;
        }
        .lede {
          margin: 0 0 12px;
          font-size: 16px;
          line-height: 1.6;
          color: var(--muted);
          max-width: 60ch;
        }
        .aside {
          margin: 0 0 22px;
          font-size: 13.5px;
          line-height: 1.6;
          color: var(--dim);
          border-left: 2px solid var(--line);
          padding-left: 13px;
          max-width: 60ch;
        }

        .tally { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
        .t-card {
          flex: 1 1 130px;
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 13px;
          padding: 13px 15px;
          display: flex;
          flex-direction: column;
          gap: 1px;
        }
        .t-card.pos { border-color: color-mix(in srgb, var(--pos) 35%, var(--line)); }
        .t-card.neg { border-color: color-mix(in srgb, var(--neg) 35%, var(--line)); }
        .t-n {
          font-size: 27px;
          font-weight: 680;
          letter-spacing: -0.03em;
          font-variant-numeric: tabular-nums;
        }
        .t-card.pos .t-n { color: var(--pos); }
        .t-card.neg .t-n { color: var(--neg); }
        .t-l { font-size: 12.5px; color: var(--dim); }

        .controls { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; }
        .seg {
          display: inline-flex;
          border: 1px solid var(--line);
          border-radius: 10px;
          overflow: hidden;
          background: var(--panel);
        }
        .seg button {
          border: 0;
          background: transparent;
          color: var(--muted);
          padding: 7px 13px;
          cursor: pointer;
          font: inherit;
          font-size: 13px;
          border-right: 1px solid var(--line);
          transition: background .12s ease, color .12s ease;
        }
        .seg button:last-child { border-right: 0; }
        .seg button:hover { background: var(--panel-2); color: var(--ink); }
        .seg button.on { background: var(--ink); color: var(--bg); font-weight: 600; }
        .search {
          flex: 1 1 210px;
          min-width: 180px;
          padding: 7px 13px;
          border: 1px solid var(--line);
          border-radius: 10px;
          background: var(--panel);
          color: var(--ink);
          font: inherit;
          font-size: 13px;
        }
        .search::placeholder { color: var(--dim); }
        .search:focus {
          outline: none;
          border-color: color-mix(in srgb, var(--accent) 55%, var(--line));
        }

        .day { margin-bottom: 26px; }
        .day-head {
          display: flex;
          align-items: baseline;
          gap: 9px;
          margin: 0 0 11px;
          font-size: 12px;
          font-weight: 680;
          letter-spacing: 0.07em;
          text-transform: uppercase;
          color: var(--dim);
        }
        .day-head::after {
          content: "";
          flex: 1;
          height: 1px;
          background: var(--line);
        }
        .day-n {
          font-size: 11.5px;
          letter-spacing: 0;
          text-transform: none;
          font-weight: 600;
          color: var(--dim);
          background: var(--panel-2);
          border-radius: 999px;
          padding: 1px 8px;
          order: 3;
        }

        .card {
          background: var(--panel);
          border: 1px solid var(--line);
          border-left: 3px solid var(--line);
          border-radius: 13px;
          padding: 14px 17px;
          margin-bottom: 9px;
          transition: border-color .15s ease;
        }
        .card:hover {
          border-color: color-mix(in srgb, var(--accent) 35%, var(--line));
        }
        .card.tone-pos { border-left-color: var(--pos); }
        .card.tone-neg { border-left-color: var(--neg); }
        .card:hover.tone-pos { border-left-color: var(--pos); }
        .card:hover.tone-neg { border-left-color: var(--neg); }

        .card-top { display: flex; justify-content: space-between; gap: 14px; }
        .left { min-width: 0; }
        .co-line {
          display: flex;
          align-items: baseline;
          gap: 8px;
          flex-wrap: wrap;
        }
        .co { font-size: 16px; font-weight: 670; letter-spacing: -0.015em; }
        .mcap {
          font-size: 11.5px;
          font-weight: 600;
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        .mcap.lg { color: var(--accent); }
        .mcap.md { color: var(--muted); }
        .mcap.sm { color: var(--dim); }
        .who { margin-top: 4px; color: var(--muted); font-size: 13.5px; }
        .tag { margin-left: 8px; color: var(--dim); font-size: 12px; }

        .right {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 5px;
          flex-shrink: 0;
        }
        .b {
          font-size: 11.5px;
          font-weight: 650;
          padding: 3px 9px;
          border-radius: 999px;
          background: var(--panel-2);
          color: var(--muted);
          white-space: nowrap;
        }
        .b.pos { background: var(--pos-bg); color: var(--pos); }
        .b.neg { background: var(--neg-bg); color: var(--neg); }
        .amt {
          font-size: 17px;
          font-weight: 680;
          letter-spacing: -0.02em;
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }

        .line {
          margin: 9px 0 0;
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          font-size: 13.5px;
          color: var(--muted);
          font-variant-numeric: tabular-nums;
        }
        .qty { color: var(--ink); }
        .tail { margin: 5px 0 0; font-size: 12.5px; color: var(--dim); }

        .more {
          display: block;
          margin: 4px auto 0;
          padding: 9px 20px;
          border: 1px solid var(--line);
          border-radius: 10px;
          background: var(--panel);
          color: var(--muted);
          font: inherit;
          font-size: 13.5px;
          cursor: pointer;
        }
        .more:hover { background: var(--panel-2); color: var(--ink); }
        .empty { color: var(--dim); padding: 22px 0; line-height: 1.6; }
        .verify {
          margin-top: 30px;
          color: var(--dim);
          font-size: 12.5px;
          line-height: 1.6;
          max-width: 66ch;
        }

        @media (max-width: 560px) {
          .head h1 { font-size: 24px; }
          .lede { font-size: 15px; }
          .card { padding: 13px 14px; }
          .card-top { flex-direction: column; gap: 8px; }
          /* The money column only works while there is a column. On a phone
             the badge and the figure sit on one line under the name. */
          .right {
            flex-direction: row-reverse;
            justify-content: flex-end;
            align-items: baseline;
            gap: 9px;
          }
          .amt { font-size: 16px; }
        }
      `}</style>
    </>
  );
}

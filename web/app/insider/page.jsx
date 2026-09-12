"use client";

import { useEffect, useMemo, useState } from "react";
import Nav from "../Nav";
import {
  byDay, count, dayLabel, mcapLabel, mcapTier, money, name, pct, price,
} from "../fmt";

const PAGE = 30;

const ROLES = [
  ["all", "Everyone"],
  ["promoter", "Promoters"],
  ["director", "Directors"],
  ["kmp", "Key management"],
  ["employee", "Employees"],
  ["relative", "Family"],
];

// What one share went for. The filing states a total and never a price, so
// rows stored before we worked it out have no `price` field and it is derived
// here instead. It is the number you can hold against today's share price.
function each(row) {
  return (
    Number(row.price) ||
    (Number(row.shares) ? Number(row.value) / Number(row.shares) : 0)
  );
}

// A pledge is not a purchase. Nobody paid ₹70.38 a share to pledge shares they
// already own, so a price on a pledge row would be an invented number.
function isPledge(side) {
  const s = (side || "").toLowerCase();
  return ["pledge", "encumbr", "revoke", "invoke"].some((k) => s.includes(k));
}

// The form's wording, in English. "Market Purchase" is a field name.
const HOWS = [
  ["market purchase", "on the open market"],
  ["market sale", "on the open market"],
  ["open market", "on the open market"],
  ["off market", "off market"],
  ["inheritance", "by inheritance"],
  ["gift", "as a gift"],
  ["allotment", "through an allotment"],
  ["conversion", "on conversion"],
  ["preferential", "through a preferential issue"],
  ["rights", "through a rights issue"],
  ["pledge", ""],
  ["invocation", ""],
  ["other", ""],
];

function how(mode) {
  const m = (mode || "").trim().toLowerCase();
  if (!m) return "";
  const hit = HOWS.find(([k]) => m.includes(k));
  return hit ? hit[1] : m;
}

// Who the person is, in words rather than in the exchange's shorthand.
const ROLE_WORDS = [
  ["promoter and director", "promoter and director"],
  ["promoter group", "promoter group"],
  ["promoter", "promoter"],
  ["immediate relative", "family of an insider"],
  ["relative", "family of an insider"],
  ["key managerial", "senior management"],
  ["designated", "senior employee"],
  ["director", "director"],
  ["employee", "employee"],
  ["trust", "trust"],
];

function roleWords(category) {
  const c = (category || "").trim().toLowerCase();
  if (!c) return "";
  const hit = ROLE_WORDS.find(([k]) => c.includes(k));
  return hit ? hit[1] : c;
}

// The badge. The filing says "Pledge Revoke"; a reader should see "Released".
const SIDES = [
  ["pledge revoke", ["Pledge released", "neu"]],
  ["pledge release", ["Pledge released", "neu"]],
  ["pledge invoke", ["Pledge invoked", "neg"]],
  ["pledge creation", ["Pledged", "neu"]],
  ["revoke", ["Pledge released", "neu"]],
  ["invoke", ["Pledge invoked", "neg"]],
  ["encumbrance", ["Encumbered", "neu"]],
  ["pledge", ["Pledged", "neu"]],
  ["buy", ["Bought", "pos"]],
  ["acquisition", ["Bought", "pos"]],
  ["sell", ["Sold", "neg"]],
  ["disposal", ["Sold", "neg"]],
];

function badge(side) {
  const s = (side || "").trim().toLowerCase();
  if (!s) return ["Traded", "neu"];
  const hit = SIDES.find(([k]) => s.includes(k));
  return hit ? hit[1] : [side, "neu"];
}

function roleClass(row) {
  const c = (row.category || "").toLowerCase();
  if (c.includes("promoter")) return "promoter";
  if (c.includes("director")) return "director";
  return "";
}

export default function InsiderPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [side, setSide] = useState("all");
  const [who, setWho] = useState("all");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    const p = new URLSearchParams({ days: "7", side, role: who });
    if (q.trim()) p.set("q", q.trim());
    fetch(`/api/insider?${p}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!alive) return;
        if (d.error) setError(d.error);
        else setData(d);
      })
      .catch(() => alive && setError("Could not load insider trades."))
      .finally(() => alive && setShown(PAGE));
    return () => {
      alive = false;
    };
  }, [side, who, q]);

  const items = data?.items || [];
  const groups = useMemo(() => byDay(items.slice(0, shown)), [items, shown]);
  const counts = data?.counts;

  return (
    <>
      <Nav />
      <main className="wrap page">
        <header className="head">
          <h1>Who&rsquo;s buying their own shares</h1>
          <p className="lede">
            A promoter, a director or senior staff buying or selling shares in
            their own company has to tell the exchange. This is that list
            &mdash; who, how many, and at what price.
          </p>
          <p className="aside">
            Left out on purpose: employee stock schemes, company welfare trusts,
            and shares moving between members of one promoter family. None of
            those is anyone deciding what the shares are worth.
          </p>
        </header>

        {/* Counts, not rupee totals. A total here would add up buying across
            two hundred unrelated companies, and the same ₹177 Cr can be one
            block in one company or two hundred small trades. */}
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
          <div className="seg wrapseg">
            {ROLES.map(([k, l]) => (
              <button
                key={k}
                type="button"
                className={who === k ? "on" : ""}
                onClick={() => setWho(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Search a company or a person"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </section>

        {error ? <p className="empty">{error}</p> : null}
        {!error && !data ? <p className="empty">Loading&hellip;</p> : null}
        {data && !items.length ? (
          <p className="empty">
            Nothing matches that. Companies file these through the trading day,
            so mornings are often quiet.
          </p>
        ) : null}

        {groups.map((g) => (
          <section key={g.day} className="day">
            <h2 className="day-head">
              <span>{dayLabel(g.day)}</span>
              <span className="day-n">
                {g.rows.length} {g.rows.length === 1 ? "trade" : "trades"}
              </span>
            </h2>

            {g.rows.map((t) => {
              const [label, tone] = badge(t.side);
              const per = each(t);
              return (
                <article key={t.id} className={`card tone-${tone}`}>
                  <div className="card-top">
                    <div className="left">
                      <div className="co-line">
                        <span className="co">{name(t.company)}</span>
                        {mcapLabel(t.mcap) ? (
                          <span className={`mcap ${mcapTier(t.mcap)}`}>
                            {mcapLabel(t.mcap)}
                          </span>
                        ) : null}
                      </div>
                      {t.who ? (
                        <div className="meta who">
                          {name(t.who)}
                          {roleWords(t.category) ? (
                            <span className={`role ${roleClass(t)}`}>
                              {roleWords(t.category)}
                            </span>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    {/* The money column. It runs straight down the right edge
                        so the eye can scan sizes without reading a word. */}
                    <div className="right">
                      <span className={`b ${tone}`}>{label}</span>
                      {t.value ? (
                        <span className="amt">{money(t.value)}</span>
                      ) : null}
                    </div>
                  </div>

                  {/* Two shapes of row. The structured filing gives fields;
                      our own read of the same document gives a sentence.
                      Rather than draw a field row full of blanks, a sentence
                      is drawn as a sentence. */}
                  {t.who ? (
                    <>
                      <p className="line">
                        {t.shares ? (
                          <span className="qty">{count(t.shares)} shares</span>
                        ) : null}
                        {per && !isPledge(t.side) ? (
                          <span className="at">at {price(per)} each</span>
                        ) : null}
                      </p>
                      {how(t.mode) || pct(t.after_pct) ? (
                        <p className="tail">
                          {[
                            how(t.mode),
                            pct(t.after_pct)
                              ? `holds ${pct(t.after_pct)} after this`
                              : "",
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <p className="summary">{t.headline}</p>
                  )}
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
          Straight from what companies file with NSE and BSE under SEBI&rsquo;s
          Regulation 7(2). Rows with a named person and a share count come from
          the structured filing; the rest are the same disclosure read from the
          document. Nothing here is advice.
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
        .seg.wrapseg { flex-wrap: wrap; }
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
        .meta { font-size: 12.5px; color: var(--dim); }
        .who { margin-top: 4px; color: var(--muted); font-size: 13.5px; }
        .role { margin-left: 7px; color: var(--dim); font-size: 12px; }
        .role.promoter { color: #9b7cff; }
        .role.director { color: var(--accent); }

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
        .summary { margin: 9px 0 0; font-size: 14.5px; line-height: 1.6; }

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

"use client";

import { useEffect, useState } from "react";
import Nav from "./Nav";
import MkFooter from "./MkFooter";
import { SITE, PER_MONTH } from "./site";

export default function Landing() {
  // Real numbers and real filings, pulled from the same store the dashboard
  // uses. Nothing on this page is a mock-up.
  const [live, setLive] = useState(null);

  useEffect(() => {
    fetch("/api/announcements?scope=important", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => !d.error && setLive(d))
      .catch(() => {});
  }, []);

  const scanned = live?.meta?.scanned;
  const summarised = live?.summarised;
  const days = live?.days?.length || 7;

  // A handful of genuinely interesting ones for the scrolling strip.
  const ticker = (live?.items || [])
    .filter((i) => i.summary && i.tag !== "Results")
    .slice(0, 14);

  const samples = (live?.items || []).filter((i) => i.summary).slice(0, 3);

  return (
    <>
      <Nav />

      <main className="mk">
        {/* ---------------- hero ---------------- */}
        <section className="mk-hero">
          <div className="eyebrow">
            <span className="live-dot" /> Updated every evening · free to read
          </div>

          <h1 className="mk-h1">
            Every filing read.
            <br />
            <span className="grad">Only the ones that matter, kept.</span>
          </h1>

          <p className="mk-sub">
            NSE and BSE publish thousands of company announcements a week. Almost
            all of it is paperwork. <strong>We read every single one</strong> and
            write a plain-English summary of the handful worth your time — with a
            link to the original PDF, always.
          </p>

          <div className="mk-ctas">
            <a className="btn-lg btn-grad" href="/dashboard">
              Open the dashboard <span aria-hidden="true">→</span>
            </a>
            <a className="btn-lg btn-ghost" href="/join">
              Join the community · ₹{SITE.price.toLocaleString("en-IN")}/yr
            </a>
          </div>
          <p className="mk-ctanote">
            No sign-up needed to read. {SITE.readers} investors already follow us.
          </p>

          {scanned ? (
            <div className="livestrip">
              <div className="livestat">
                <b>{Number(scanned).toLocaleString("en-IN")}</b>
                <span>filings read</span>
              </div>
              <div className="livestat hi">
                <b>{Number(summarised || 0).toLocaleString("en-IN")}</b>
                <span>were worth summarising</span>
              </div>
              <div className="livestat">
                <b>{days}</b>
                <span>days on the dashboard</span>
              </div>
              <div className="livestat">
                <b>{Object.keys(live?.tagCounts || {}).length}</b>
                <span>categories to filter</span>
              </div>
            </div>
          ) : null}
        </section>

        {/* ---------------- live ticker ---------------- */}
        {ticker.length > 4 && (
          <div className="ticker" aria-hidden="true">
            <div className="ticker-track">
              {[...ticker, ...ticker].map((t, i) => (
                <span className="tick" key={i}>
                  <span className="tk">{t.tag}</span>
                  <b>{t.company}</b>
                  <span>{(t.key_numbers || [])[0] || t.time}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* ---------------- what you get ---------------- */}
        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">What you actually get</p>
            <h2 className="mk-h2">Not headlines. The answer.</h2>
            <p className="mk-lead">
              These are real summaries produced in the last seven days. Nothing
              here is written for the pitch.
            </p>
          </div>

          {samples.length > 0 ? (
            samples.map((s) => (
              <article className="card" key={s.id}>
                <div className="card-top">
                  <div>
                    <div className="co">{s.company}</div>
                    <div className="meta">
                      {s.exchange} · {s.category} · {s.time}
                    </div>
                  </div>
                  <div className="badges">
                    <span className="b tag">{s.tag}</span>
                    {s.impact && (
                      <span
                        className={`b ${
                          s.impact === "Positive"
                            ? "pos"
                            : s.impact === "Negative"
                            ? "neg"
                            : "neu"
                        }`}
                      >
                        {s.impact}
                      </span>
                    )}
                  </div>
                </div>
                <p className="summary">{s.summary}</p>
                {(s.key_numbers || []).length > 0 && (
                  <div className="nums">
                    {s.key_numbers.map((n, i) => (
                      <span className="num" key={i}>
                        {n}
                      </span>
                    ))}
                  </div>
                )}
                {s.why_it_matters && <div className="why">{s.why_it_matters}</div>}
                <div className="card-links">
                  {s.pdf_url && (
                    <a href={s.pdf_url} target="_blank" rel="noopener noreferrer">
                      Open the original filing
                    </a>
                  )}
                  <span className="verify">check it yourself</span>
                </div>
              </article>
            ))
          ) : (
            <div className="empty">Loading today&apos;s filings…</div>
          )}

          <div style={{ textAlign: "center", marginTop: 22 }}>
            <a className="btn-lg btn-ghost" href="/dashboard">
              See all of them <span aria-hidden="true">→</span>
            </a>
          </div>
        </section>

        {/* ---------------- how ---------------- */}
        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">How it works</p>
            <h2 className="mk-h2">Three steps, every evening</h2>
          </div>

          <div className="steps">
            <div className="step">
              <div className="step-n">1</div>
              <h3>We pull everything</h3>
              <p>
                Every announcement filed with both exchanges, every day —
                including weekends, when companies still file.
              </p>
            </div>
            <div className="step">
              <div className="step-n">2</div>
              <h3>We throw out the noise</h3>
              <p>
                Trading window notices, newspaper clippings, duplicate share
                certificates. Roughly nine in ten filings never reach you.
              </p>
            </div>
            <div className="step">
              <div className="step-n">3</div>
              <h3>We read the PDF</h3>
              <p>
                Including scanned ones. You get two or three sentences, the
                numbers that matter, and the original document to check.
              </p>
            </div>
          </div>
        </section>

        {/* ---------------- why us ---------------- */}
        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">Why it is different</p>
            <h2 className="mk-h2">Built to be checked, not trusted</h2>
          </div>

          <div className="bento">
            <div className="bx wide">
              <div className="bx-ico">
                <IconDoc />
              </div>
              <h3>Every card links to the PDF</h3>
              <p>
                We summarise with AI, and AI gets things wrong. So the original
                filing is one tap away on every single item. If our summary and
                the filing disagree, the filing wins.
              </p>
            </div>
            <div className="bx wide">
              <div className="bx-ico">
                <IconFilter />
              </div>
              <h3>Sorted by what it is</h3>
              <p>
                Buybacks, bonus issues, order wins, schemes of arrangement, QIPs,
                NCLT matters, rating changes — filter to the one thing you care
                about instead of scrolling.
              </p>
            </div>

            <div className="bx">
              <div className="bx-num">₹0</div>
              <h3>Free to read</h3>
              <p>The dashboard and the daily WhatsApp brief cost nothing.</p>
            </div>
            <div className="bx">
              <div className="bx-num">7</div>
              <h3>Days of history</h3>
              <p>Catch up on the whole week, not just what landed today.</p>
            </div>
            <div className="bx">
              <div className="bx-num">XLS</div>
              <h3>Export anything</h3>
              <p>
                Any filter, straight to Excel — with the PDF link in every row.
              </p>
            </div>
          </div>
        </section>

        {/* ---------------- community teaser ---------------- */}
        <section className="mk-sec">
          <div className="finale">
            <h2>The reading is free. The room is not.</h2>
            <p>
              ₹{SITE.price.toLocaleString("en-IN")} a year — about ₹{PER_MONTH} a
              month — gets you into a community of investors serious enough to pay
              to be in it. Discussion, deep dives, watchlist alerts and offline
              meetups across India. Launch price for the first {SITE.launchSeats}.
            </p>
            <div className="mk-ctas">
              <a className="btn-lg btn-grad" href="/join">
                See what&apos;s inside · ₹{SITE.price.toLocaleString("en-IN")}/year
              </a>
              <a
                className="btn-lg btn-wa"
                href={SITE.newsletterLink}
                target="_blank"
                rel="noopener noreferrer"
              >
                <WaIcon /> Free daily brief
              </a>
            </div>
          </div>
        </section>
      </main>

      <MkFooter />
    </>
  );
}

function IconDoc() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function IconFilter() {
  return (
    <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  );
}

function WaIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.47-1.75-1.65-2.05-.17-.3-.02-.46.13-.6.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.6-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.47s1.06 2.86 1.21 3.06c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.72 2-1.41.25-.69.25-1.28.17-1.41-.07-.13-.27-.2-.57-.35z" />
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm0 18.15h-.01a8.22 8.22 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.2 8.2 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.24 8.23z" />
    </svg>
  );
}

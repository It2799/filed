"use client";

import { useState } from "react";
import Nav from "../Nav";
import MkFooter from "../MkFooter";
import { SITE } from "../site";

export default function Subscribe() {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");   // honeypot
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (state === "sending") return;
    setState("sending");
    setError("");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, company, source: "brief" }),
      });
      const d = await res.json();
      if (!res.ok) {
        setError(d.error || "Please try again.");
        setState("idle");
        return;
      }
      setState("done");
    } catch {
      setError("Couldn't reach the server. Please try again.");
      setState("idle");
    }
  }

  return (
    <>
      <Nav />
      <main className="mk">
        <section className="mk-hero">
          <h1 className="mk-h1">
            The daily free brief,
            <br />
            <span className="grad">in your inbox at 7:30</span>
          </h1>

          <p className="mk-sub">
            Every morning we sift through every announcement filed with NSE and
            BSE and send you the <strong>top 50 that actually matter</strong> —
            what happened, the key numbers, and why it matters. One PDF, free,
            and no more than one email a day.
          </p>

          <div className="sub-card" id="subscribe">
            {state === "done" ? (
              <div className="sub-done">
                <b>You're in.</b>
                <p>
                  The next brief lands tomorrow at 7:30 in the morning. In the
                  meantime, today's issue is on the{" "}
                  <a href="/brief">brief page</a>.
                </p>
              </div>
            ) : (
              <form onSubmit={submit} className="sub-form">
                <label htmlFor="sub-email" className="sub-label">
                  Email address
                </label>
                <div className="sub-row">
                  <input
                    id="sub-email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(ev) => setEmail(ev.target.value)}
                  />
                  <button className="btn-lg btn-grad" disabled={state === "sending"}>
                    {state === "sending" ? "Signing you up…" : "Get the brief"}
                  </button>
                </div>

                {/* Hidden from people, filled in by bots. */}
                <input
                  className="hp"
                  tabIndex={-1}
                  autoComplete="off"
                  aria-hidden="true"
                  value={company}
                  onChange={(ev) => setCompany(ev.target.value)}
                />

                {error && <p className="sub-error">{error}</p>}
                <p className="sub-note">
                  Free, and we won't pass your address to anyone. Unsubscribe
                  any time.
                </p>
              </form>
            )}
          </div>

          <div className="sub-or"><span>or</span></div>

          <a
            className="btn-lg btn-wa"
            href={SITE.newsletterLink}
            target="_blank"
            rel="noopener noreferrer"
          >
            Join the Market Tide WhatsApp community
          </a>
          <p className="mk-ctanote">
            The same brief, posted every morning in the group. Free to join.
          </p>
        </section>

        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">What you get</p>
            <h2 className="mk-h2">One PDF. Fifty filings. No noise.</h2>
          </div>
          <div className="bento">
            <div className="bx wide">
              <h3>Only what happened</h3>
              <p>
                Concall invitations, investor presentations and meeting notices
                are left out — a diary entry is not news. So are dividends and
                splits, which are routine enough to crowd out everything else.
              </p>
            </div>
            <div className="bx wide">
              <h3>Overnight filings included</h3>
              <p>
                The issue covers everything filed from the start of yesterday
                until quarter to seven this morning, so an announcement made
                late at night reaches you at breakfast, not a day later.
              </p>
            </div>
            <div className="bx wide">
              <h3>Plain English, with the numbers</h3>
              <p>
                Every entry gives the company, its market cap, what was
                announced, the figures that matter, and one line on why it
                matters. Written from the filing itself.
              </p>
            </div>
            <div className="bx wide">
              <h3>The archive stays open</h3>
              <p>
                Every issue is on the <a href="/brief">brief page</a>, and every
                important filing — including the ones the brief leaves out — is
                searchable on the <a href="/dashboard">dashboard</a>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <MkFooter />
    </>
  );
}

"use client";

import { useState } from "react";
import Nav from "../Nav";
import MkFooter from "../MkFooter";
import { SITE } from "../site";

export default function Join() {
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState(""); // honeypot
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");

  const waLink = `https://wa.me/${SITE.phoneDigits}?text=${encodeURIComponent(
    "Hi, I'd like to join the Market Tide community for Rs 99/month."
  )}`;

  async function submit(e) {
    e.preventDefault();
    if (state === "sending") return;
    setState("sending");
    setError("");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, phone, company, source: "join" }),
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
          <div className="eyebrow">
            <span className="live-dot" /> Founding members · opening soon
          </div>
          <h1 className="mk-h1">
            ₹99 a month keeps
            <br />
            <span className="grad">the tourists out.</span>
          </h1>
          <p className="mk-sub">
            The filings are free — they always will be. What ₹99 buys is the room
            next door: a group of investors and traders serious enough to pay to
            be in it. <strong>That price isn&apos;t about covering our costs.</strong>{" "}
            It&apos;s the filter.
          </p>
        </section>

        {/* ---------------- price + why ---------------- */}
        <section className="mk-sec" style={{ paddingTop: 8 }}>
          <div className="price-wrap">
            <div className="price-card">
              <p className="mk-kicker" style={{ marginBottom: 4 }}>
                Membership
              </p>
              <div className="price-tag">
                <b>₹{SITE.price}</b>
                <span>/ month</span>
              </div>
              <p className="price-note">
                Cancel any time. No lock-in, no card stored by us.
              </p>

              <ul className="tick-list">
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>The full dashboard</b> — every relevant filing, all seven
                    days, every category, Excel export.
                  </span>
                </li>
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>The members&apos; group</b> — discuss what actually landed
                    today with people who read the filings, not the headlines.
                  </span>
                </li>
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>Offline meetups across India</b> — Mumbai first, then
                    wherever enough members are.
                  </span>
                </li>
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>Weekly deep dives</b> on a company or an industry, written
                    up properly rather than posted as a chart.
                  </span>
                </li>
                <li>
                  <span className="ok">✓</span>
                  <span>
                    <b>Ask and get answered</b> — bring a filing you don&apos;t
                    understand and have it pulled apart.
                  </span>
                </li>
              </ul>

              {state === "done" ? (
                <div className="done">
                  <b>You&apos;re on the founding members list.</b>
                  <p>
                    We&apos;ll message you the moment the doors open, with joining
                    instructions.
                  </p>
                  <a
                    className="wa-btn"
                    href={waLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ marginTop: 12 }}
                  >
                    <WaIcon /> Message us directly
                  </a>
                </div>
              ) : (
                <>
                  <form onSubmit={submit}>
                    <div className="row">
                      <input
                        type="email"
                        value={email}
                        required
                        autoComplete="email"
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@email.com"
                        aria-label="Email address"
                      />
                      <input
                        className="hp"
                        type="text"
                        tabIndex={-1}
                        aria-hidden="true"
                        autoComplete="off"
                        value={company}
                        onChange={(e) => setCompany(e.target.value)}
                      />
                    </div>
                    <div className="row phone-row">
                      <div className="phone-wrap">
                        <span className="cc">+91</span>
                        <input
                          className="phone"
                          type="tel"
                          inputMode="numeric"
                          maxLength={14}
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          placeholder="WhatsApp number"
                          aria-label="WhatsApp number"
                        />
                      </div>
                      <button type="submit" disabled={state === "sending"}>
                        {state === "sending" ? "Adding…" : "Claim a founding seat"}
                      </button>
                    </div>
                    {error && <p className="err">{error}</p>}
                  </form>
                  <p className="note" style={{ marginTop: 10 }}>
                    Nothing to pay now. We&apos;ll message you when the doors open
                    — founding members keep ₹{SITE.price} for life.
                  </p>
                </>
              )}
            </div>

            <div>
              <div className="why-card" style={{ marginBottom: 14 }}>
                <h3>Why charge at all, if the filings are free?</h3>
                <p>
                  Because free groups fill up with people who don&apos;t read.
                  Anyone will join a group that costs nothing, and within a month
                  it&apos;s tips, forwards and good-morning images.
                </p>
                <p>
                  <strong>₹99 is deliberately small and deliberately not zero.</strong>{" "}
                  It&apos;s less than two cups of coffee, so nobody serious is
                  priced out — and it&apos;s enough that nobody joins by accident.
                </p>
                <p>
                  The money keeps the lights on. The <em>price</em> keeps the room
                  worth being in.
                </p>
              </div>

              <div className="why-card">
                <h3>What actually happens inside</h3>
                <p>
                  Every evening the day&apos;s filings land and members pick them
                  apart — what an order win is really worth, whether a buyback is
                  priced sensibly, what a scheme of arrangement does to minority
                  holders.
                </p>
                <p>
                  Once we have enough members in a city, we meet. Mumbai first.
                  Real conversations, no stage, no selling.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ---------------- faq ---------------- */}
        <section className="mk-sec">
          <div className="mk-sec-head">
            <p className="mk-kicker">Straight answers</p>
            <h2 className="mk-h2">Before you join</h2>
          </div>

          <div className="mk-narrow faq">
            <details>
              <summary>Is this tips or recommendations?</summary>
              <p>
                No. We are not a SEBI-registered research analyst or investment
                adviser, and we will never tell you what to buy or sell. We
                summarise public filings and link the original. What members
                discuss between themselves is their own view, not ours.
              </p>
            </details>
            <details>
              <summary>Do I need to pay to read the filings?</summary>
              <p>
                No. The dashboard and the daily WhatsApp brief are free and will
                stay free. ₹{SITE.price} is for the community, the meetups and the
                weekly deep dives.
              </p>
            </details>
            <details>
              <summary>Can I leave?</summary>
              <p>
                Any time, no questions. Cancel within 7 days and we refund in
                full; after that we refund the unused months. See the{" "}
                <a href="/refund">refund policy</a>.
              </p>
            </details>
            <details>
              <summary>When do the meetups start?</summary>
              <p>
                As soon as there are enough members in one city to make it worth
                everyone&apos;s evening. Mumbai is first — that&apos;s where we
                are. We&apos;ll ask members before fixing anything.
              </p>
            </details>
            <details>
              <summary>What if the summaries are wrong?</summary>
              <p>
                They sometimes will be — they&apos;re written by AI. That&apos;s
                exactly why every card links to the original PDF. Tell us when you
                spot one and we&apos;ll fix it; members do this and it makes the
                product better for everyone.
              </p>
            </details>
            <details>
              <summary>How do I pay?</summary>
              <p>
                Not yet — we&apos;re opening to founding members first. Leave your
                details above and we&apos;ll message you with joining
                instructions. Founding members keep ₹{SITE.price} for life, even
                when the price goes up.
              </p>
            </details>
          </div>
        </section>

        <section className="mk-sec">
          <div className="finale">
            <h2>Read first. Decide later.</h2>
            <p>
              The dashboard is open and costs nothing. Use it for a week — if it
              earns a place in your evening, the room is next door.
            </p>
            <div className="mk-ctas">
              <a className="btn-lg btn-ghost" href="/dashboard">
                Open the dashboard
              </a>
              <a
                className="btn-lg btn-wa"
                href={waLink}
                target="_blank"
                rel="noopener noreferrer"
              >
                <WaIcon /> Ask us anything
              </a>
            </div>
          </div>
        </section>
      </main>

      <MkFooter />
    </>
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

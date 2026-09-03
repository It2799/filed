"use client";

/**
 * Signing in. Two ways, both a six-digit code - no password to choose, forget,
 * or have stolen from somewhere else.
 *
 * The page asks /api/auth/me which channels this deployment can actually send
 * on, and offers only those. Showing a WhatsApp button that fails after
 * somebody has typed their number is worse than not showing it.
 */

import { useEffect, useRef, useState } from "react";
import Nav from "../Nav";
import MkFooter from "../MkFooter";

const RESEND_AFTER = 45;   // seconds before "send it again" appears

export default function Login() {
  const [channel, setChannel] = useState("email");
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("identify");    // identify -> code -> done
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [available, setAvailable] = useState(null);
  const [user, setUser] = useState(null);
  const [wait, setWait] = useState(0);
  const codeBox = useRef(null);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => r.json())
      .then((d) => {
        setAvailable(d.channels || {});
        if (d.user) {
          setUser(d.user);
          setStep("done");
        }
        // Land on whichever channel actually works, so the first thing the
        // reader sees is one that can send them something.
        if (d.channels && !d.channels.email && d.channels.whatsapp) {
          setChannel("whatsapp");
        }
      })
      .catch(() => setAvailable({}));
  }, []);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  useEffect(() => {
    if (step === "code" && codeBox.current) codeBox.current.focus();
  }, [step]);

  async function send(e) {
    if (e) e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/auth/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel, identifier }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Something went wrong.");
      } else {
        setStep("code");
        setWait(RESEND_AFTER);
      }
    } catch {
      setError("Could not reach the server. Check your connection.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/auth/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel, identifier, code }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(
          data.attemptsLeft
            ? `${data.error} ${data.attemptsLeft} tries left.`
            : data.error || "That did not work."
        );
        setCode("");
      } else {
        setUser({ id: data.id, channel: data.channel });
        setStep("done");
      }
    } catch {
      setError("Could not reach the server. Check your connection.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
    setCode("");
    setIdentifier("");
    setStep("identify");
  }

  const nothingWorks =
    available && !available.email && !available.whatsapp;

  return (
    <>
      <Nav />
      <main className="mk">
        <section className="mk-hero" style={{ paddingBottom: 8 }}>
          <h1 className="mk-h1">
            Sign in to <span className="grad">Market Tide</span>
          </h1>
          <p className="mk-sub">
            No password. We send a six-digit code and you type it back.
          </p>
        </section>

        <section className="mk-sec">
          <div className="price-wrap">
            <div className="price-card" style={{ textAlign: "left" }}>
              {step === "done" && user ? (
                <div className="done">
                  <b>You are signed in.</b>
                  <p style={{ marginTop: 6 }}>{user.id}</p>
                  <button
                    className="btn-lg btn-ghost"
                    style={{ marginTop: 14 }}
                    onClick={signOut}
                  >
                    Sign out
                  </button>
                </div>
              ) : nothingWorks ? (
                <div className="done">
                  <b>Sign-in is not switched on yet.</b>
                  <p style={{ marginTop: 6 }}>
                    Neither email nor WhatsApp is connected on this deployment.
                    Everything on the site is free to read without an account.
                  </p>
                </div>
              ) : step === "identify" ? (
                <>
                  <div
                    className="mk-ctas"
                    style={{ justifyContent: "flex-start", marginBottom: 18 }}
                  >
                    {(!available || available.email) && (
                      <button
                        type="button"
                        className={
                          channel === "email" ? "btn-lg btn-grad" : "btn-lg btn-ghost"
                        }
                        onClick={() => {
                          setChannel("email");
                          setError("");
                        }}
                      >
                        Email
                      </button>
                    )}
                    {(!available || available.whatsapp) && (
                      <button
                        type="button"
                        className={
                          channel === "whatsapp" ? "btn-lg btn-grad" : "btn-lg btn-ghost"
                        }
                        onClick={() => {
                          setChannel("whatsapp");
                          setError("");
                        }}
                      >
                        WhatsApp
                      </button>
                    )}
                  </div>

                  <form onSubmit={send}>
                    <div className="row">
                      <input
                        type={channel === "email" ? "email" : "tel"}
                        inputMode={channel === "email" ? "email" : "numeric"}
                        value={identifier}
                        required
                        autoComplete={channel === "email" ? "email" : "tel"}
                        onChange={(e) => setIdentifier(e.target.value)}
                        placeholder={
                          channel === "email" ? "you@email.com" : "98765 43210"
                        }
                        aria-label={
                          channel === "email"
                            ? "Email address"
                            : "WhatsApp mobile number"
                        }
                      />
                      <button className="btn-lg btn-grad" disabled={busy}>
                        {busy ? "Sending…" : "Send code"}
                      </button>
                    </div>
                  </form>

                  <p className="price-note" style={{ marginTop: 12 }}>
                    {channel === "email"
                      ? "The code lands in your inbox. Check spam the first time."
                      : "The code arrives on WhatsApp. Indian mobile numbers only."}
                  </p>
                </>
              ) : (
                <>
                  <p className="mk-kicker" style={{ marginBottom: 4 }}>
                    Code sent to
                  </p>
                  <p style={{ margin: "0 0 16px", fontWeight: 600 }}>
                    {identifier}{" "}
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => {
                        setStep("identify");
                        setCode("");
                        setError("");
                      }}
                      style={{
                        background: "none",
                        border: 0,
                        padding: 0,
                        cursor: "pointer",
                        textDecoration: "underline",
                        font: "inherit",
                        fontWeight: 400,
                        opacity: 0.7,
                      }}
                    >
                      change
                    </button>
                  </p>

                  <form onSubmit={verify}>
                    <div className="row">
                      <input
                        ref={codeBox}
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={6}
                        value={code}
                        required
                        autoComplete="one-time-code"
                        onChange={(e) =>
                          setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                        }
                        placeholder="000000"
                        aria-label="Six-digit code"
                        style={{ letterSpacing: "0.35em", fontVariantNumeric: "tabular-nums" }}
                      />
                      <button
                        className="btn-lg btn-grad"
                        disabled={busy || code.length !== 6}
                      >
                        {busy ? "Checking…" : "Sign in"}
                      </button>
                    </div>
                  </form>

                  <p className="price-note" style={{ marginTop: 12 }}>
                    It works for 10 minutes, once.{" "}
                    {wait > 0 ? (
                      <>You can ask for another in {wait}s.</>
                    ) : (
                      <button
                        type="button"
                        onClick={() => send()}
                        style={{
                          background: "none",
                          border: 0,
                          padding: 0,
                          cursor: "pointer",
                          textDecoration: "underline",
                          font: "inherit",
                        }}
                      >
                        Send it again
                      </button>
                    )}
                  </p>
                </>
              )}

              {error && (
                <p
                  role="alert"
                  style={{ marginTop: 14, color: "#c0392b", fontSize: 14 }}
                >
                  {error}
                </p>
              )}
            </div>
          </div>

          <p className="mk-sub" style={{ marginTop: 26, fontSize: 14 }}>
            Everything on Market Tide is free to read without signing in.
            An account is only so we know where to send the morning brief.
          </p>
        </section>
      </main>
      <MkFooter />
    </>
  );
}

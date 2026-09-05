"use client";

import { useState } from "react";

export default function ContactForm() {
  const [status, setStatus] = useState({ busy: false, message: "", ok: false });

  async function submit(event) {
    event.preventDefault();
    setStatus({ busy: true, message: "", ok: false });
    const form = event.currentTarget;
    const body = Object.fromEntries(new FormData(form));
    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not send your message.");
      form.reset();
      setStatus({ busy: false, message: "Message sent. We will reply by email.", ok: true });
    } catch (error) {
      setStatus({ busy: false, message: error.message, ok: false });
    }
  }

  return (
    <form className="contact-form" onSubmit={submit}>
      <div className="contact-form-row">
        <label>Your name<input name="name" maxLength="80" required /></label>
        <label>Your email<input name="email" type="email" maxLength="254" required /></label>
      </div>
      <label>How can we help?<textarea name="message" minLength="10" maxLength="3000" rows="6" required /></label>
      <label className="contact-company" aria-hidden="true">Company<input name="company" tabIndex="-1" autoComplete="off" /></label>
      <button type="submit" disabled={status.busy}>{status.busy ? "Sending…" : "Send message"}</button>
      {status.message ? <p className={status.ok ? "contact-success" : "contact-error"}>{status.message}</p> : null}
    </form>
  );
}

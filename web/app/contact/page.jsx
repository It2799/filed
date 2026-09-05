import { LEGAL } from "../../lib/legal";
import ContactForm from "./ContactForm";

export const metadata = { title: "Contact — Market Tide" };

export default function Contact() {
  const wa = `https://wa.me/${LEGAL.phoneDigits}?text=${encodeURIComponent(
    "Hi, I have a question about Market Tide.")}`;

  return (
    <div className="wrap legal">
      <a className="back" href="/">← Market Tide</a>
      <h1>Contact us</h1>
      <p className="updated">We answer WhatsApp fastest.</p>

      <div className="contact-grid">
        <div className="contact-card">
          <h3>WhatsApp</h3>
          <p><a href={wa} target="_blank" rel="noopener">{LEGAL.phoneDisplay}</a></p>
          <p className="small">Usually within a few hours, 9am–9pm IST.</p>
        </div>
        <div className="contact-card">
          <h3>Email</h3>
          <p><a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a></p>
          <p className="small">Within 1 working day.</p>
        </div>
      </div>

      <h2>Send a message</h2>
      <ContactForm />

      <h2>Registered address</h2>
      <p className="address">
        {LEGAL.entity}
        <br />
        {LEGAL.address}
        <br />
        India
        {LEGAL.gstin ? <><br />GSTIN: {LEGAL.gstin}</> : null}
      </p>

      <h2>What to contact us about</h2>
      <ul>
        <li>
          <strong>A summary looks wrong.</strong> Please send the company name
          and date — we take these seriously and fix them.
        </li>
        <li>
          <strong>Refunds and billing.</strong> See the{" "}
          <a href="/refund">Refund Policy</a>, then email us. No forms.
        </li>
        <li>
          <strong>Your data.</strong> To see, correct or delete what we hold, see
          the <a href="/privacy">Privacy Policy</a>.
        </li>
        <li>
          <strong>Anything else.</strong> Just ask.
        </li>
      </ul>

      <h2>What we cannot help with</h2>
      <p>
        We cannot tell you what to buy or sell. {LEGAL.brand} is an information
        service and we are not SEBI-registered advisers — see our{" "}
        <a href="/terms">Terms</a>.
      </p>
    </div>
  );
}

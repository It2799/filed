import { LEGAL } from "../../lib/legal";

export const metadata = { title: "Refund & Cancellation Policy — Market Tide" };

export default function Refund() {
  return (
    <div className="wrap legal">
      <a className="back" href="/">← Market Tide</a>
      <h1>Refund &amp; Cancellation Policy</h1>
      <p className="updated">Last updated {LEGAL.updated}</p>

      <p className="callout">
        <strong>The short version.</strong> Changed your mind within 7 days and
        barely used it? Full refund. Later than that, we refund the unused
        months. If we break something or shut down, you get your money back
        without asking.
      </p>

      <h2>1. Cancelling</h2>
      <p>
        You can cancel at any time by emailing{" "}
        <a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a> or messaging{" "}
        {LEGAL.phoneDisplay} on WhatsApp. There is no cancellation fee and no
        form to fill in.
      </p>
      <p>
        Subscriptions are prepaid for a fixed term and do not auto-renew, so
        cancelling simply means we will not ask you to pay again.
      </p>

      <h2>2. Refund within 7 days</h2>
      <p>
        If you cancel within <strong>7 days</strong> of paying, we refund the
        full amount, provided the account has not been used heavily — as a rough
        guide, fewer than 10 days&rsquo; worth of dashboard access or bulk
        exports.
      </p>

      <h2>3. Refund after 7 days</h2>
      <p>
        After 7 days we refund the unused whole months of your term, rounded
        down. For example, on a 12-month plan at ₹1,899 cancelled after 4 months,
        we refund 8 months: ₹1,899 × 8 ÷ 12 = ₹1,266.
      </p>

      <h2>4. When we refund without being asked</h2>
      <ul>
        <li>We stop running the service during a term you have paid for.</li>
        <li>You were charged twice for the same subscription.</li>
        <li>
          The service was substantially unavailable for more than 7 consecutive
          days for reasons within our control.
        </li>
      </ul>

      <h2>5. What we do not refund</h2>
      <ul>
        <li>
          Trading losses, or decisions taken on the basis of anything you read
          here. We are an information service, not advisers — see our{" "}
          <a href="/terms">Terms</a>.
        </li>
        <li>
          Accounts closed for sharing a login or redistributing our content,
          though we will still refund the unused months.
        </li>
        <li>
          Interruptions caused by the exchanges changing or withdrawing their
          own systems, which is outside our control.
        </li>
      </ul>

      <h2>6. How long a refund takes</h2>
      <p>
        We approve or query refund requests within{" "}
        <strong>2 working days</strong>. Approved refunds go back to the original
        payment method and typically reach you within{" "}
        <strong>5 to 7 working days</strong>, depending on your bank. We do not
        charge a processing fee.
      </p>

      <h2>7. How to ask</h2>
      <p>
        Email <a href={`mailto:${LEGAL.email}`}>{LEGAL.email}</a> with the email
        address you signed up with and the date you paid. That is all we need.
        If something has gone wrong, telling us what happened helps us fix it,
        but it is not a condition of the refund.
      </p>
    </div>
  );
}

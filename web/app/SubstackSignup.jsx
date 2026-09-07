"use client";

function embedUrl(raw) {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" || !url.hostname.endsWith(".substack.com")) return null;
    url.pathname = "/embed";
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    return null;
  }
}

/** Substack owns the form so a confirmed signup is written directly there. */
export default function SubstackSignup() {
  const src = embedUrl(
    process.env.NEXT_PUBLIC_SUBSTACK_URL || "https://markettide.substack.com"
  );
  if (!src) return null;

  return (
    <div className="substack-signup">
      <span className="sub-label">Get it in your inbox</span>
      <iframe
        className="substack-frame"
        src={src}
        title="Subscribe to the Market Tide Daily Brief"
        loading="lazy"
        scrolling="no"
      />
      <p className="sub-note">
        Free, one email each morning. Subscription and unsubscribe preferences
        are securely managed by Substack.
      </p>
    </div>
  );
}

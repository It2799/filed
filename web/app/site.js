// Everything you'd want to change without touching a page.

export const SITE = {
  name: "Market Tide",

  phoneDisplay: "+91 82004 40146",
  phoneDigits: "918200440146",
  email: "market.tide27@gmail.com",

  // The free daily brief, already running.
  newsletterLink: "https://chat.whatsapp.com/B9cZ0FnmUFxKGUuXaqXG4H?s=cl&p=a&ilr=1",

  // Combined audience across the WhatsApp brief and the website list.
  // The website-form count alone is live at /api/waitlist; this is the wider
  // figure kept by hand, so update it as the group grows.
  readers: "500+",

  // Membership.
  //
  // FREE while in beta. Readers were seeing "Join - Rs 999" in the nav and not
  // opening the dashboard at all, which is free and always was - the price was
  // for the community, but nothing on the page said so before they had
  // already decided.
  //
  // Set `free: false` to charge again; every page that mentions the price
  // follows from these four values.
  free: true,
  price: 999,          // what it will cost once the beta ends
  fullPrice: 1499,
  launchSeats: 500,
  period: "year",
};

// What the buttons say. One place, so the nav, the landing page and the join
// page cannot drift apart.
export const PRICE_LABEL = SITE.free
  ? "Free"
  : `₹${SITE.price.toLocaleString("en-IN")}`;

export const PRICE_NOTE = SITE.free
  ? `Free while in beta. ₹${SITE.price.toLocaleString("en-IN")} a year once it opens properly.`
  : `₹${SITE.price.toLocaleString("en-IN")} a year.`;

export const SAVING = SITE.fullPrice - SITE.price;
export const SAVING_PCT = Math.round((SAVING / SITE.fullPrice) * 100);
export const PER_MONTH = Math.round(SITE.price / 12);

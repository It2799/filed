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

  // Membership. The launch price holds for the first `launchSeats` members,
  // then it goes to the full price. Change these three numbers and every page
  // that mentions the price follows.
  price: 999,
  fullPrice: 1499,
  launchSeats: 500,
  period: "year",
};

export const SAVING = SITE.fullPrice - SITE.price;
export const SAVING_PCT = Math.round((SAVING / SITE.fullPrice) * 100);
export const PER_MONTH = Math.round(SITE.price / 12);

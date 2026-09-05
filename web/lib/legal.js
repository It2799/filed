/**
 * The details every policy page and the payment gateway need.
 *
 * >>> FILL IN THE THREE MARKED FIELDS BEFORE APPLYING TO RAZORPAY/CASHFREE. <<<
 * They check that a real, contactable business is behind the site, and a
 * missing address is one of the most common reasons an application is rejected.
 */
export const LEGAL = {
  brand: "Market Tide",

  // The name you trade under. For a sole proprietorship this is usually
  // "<Your full name>, sole proprietor trading as Market Tide".
  entity: "Market Tide",

  // A real postal address. Gateways verify it. A home address is fine.
  address: "Ghatkopar, Mumbai 400086, Maharashtra",

  // Leave GST blank until you register (not required below Rs 20 lakh).
  gstin: "",                                   // <<< FILL IN when you have one

  email: "market.tide27@gmail.com",
  phoneDisplay: "+91 82004 40146",
  phoneDigits: "918200440146",

  // Keep in step with the pricing you actually charge.
  plans: [
    { name: "1 year (founding price)", price: 999, months: 12 },
    { name: "1 year (standard)", price: 1499, months: 12 },
  ],

  updated: "September 2026",
};

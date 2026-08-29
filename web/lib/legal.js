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
  entity: "Market Tide",                       // <<< CHECK THIS

  // A real postal address. Gateways verify it. A home address is fine.
  address: "[ADD YOUR FULL POSTAL ADDRESS, CITY, STATE, PIN]",   // <<< FILL IN

  // Leave GST blank until you register (not required below Rs 20 lakh).
  gstin: "",                                   // <<< FILL IN when you have one

  email: "market.tide27@gmail.com",
  phoneDisplay: "+91 82004 40146",
  phoneDigits: "918200440146",

  // Keep in step with the pricing you actually charge.
  plans: [
    { name: "3 months", price: 699, months: 3 },
    { name: "6 months", price: 1199, months: 6 },
    { name: "12 months", price: 1899, months: 12 },
  ],

  updated: "August 2026",
};

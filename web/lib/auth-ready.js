import { configured as otpConfigured } from "./otp.js";
import { configured as usersConfigured } from "./users.js";
import { emailConfigured } from "./notify.js";

export function authReady() {
  if (process.env.MEMBER_AUTH_ENABLED !== "true") return false;
  return Boolean(
    otpConfigured() &&
    usersConfigured() &&
    emailConfigured() &&
    process.env.AUTH_SECRET
  );
}

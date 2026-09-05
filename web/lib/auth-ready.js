import { configured as otpConfigured } from "./otp.js";
import { configured as usersConfigured } from "./users.js";
import { emailConfigured } from "./notify.js";

export function authReady() {
  return Boolean(
    otpConfigured() &&
    usersConfigured() &&
    emailConfigured() &&
    process.env.AUTH_SECRET
  );
}

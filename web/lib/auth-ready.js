import { configured as otpConfigured } from "./otp.js";
import { configured as usersConfigured } from "./users.js";

export function authReady() {
  return Boolean(
    otpConfigured() &&
    usersConfigured() &&
    process.env.RESEND_API_KEY &&
    process.env.FROM_EMAIL &&
    process.env.AUTH_SECRET
  );
}

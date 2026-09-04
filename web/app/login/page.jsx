import { redirect } from "next/navigation";

// The protected dashboard owns the sign-in modal, so old /login links and
// bookmarks now lead to the same single authentication experience.
export default function Login() {
  redirect("/dashboard");
}

import { redirect } from "next/navigation";

/**
 * There used to be a separate signup page. Reading the brief and subscribing
 * to it are now the same page, so anyone who arrives here - from an old link,
 * or the footer of an early issue - lands where the form actually is.
 */
export default function Subscribe() {
  redirect("/brief#subscribe");
}

/**
 * Google Sheets waitlist collector.
 *
 * Use this if you'd rather not sign up for another service. It writes every
 * signup straight into a Google Sheet you own, and you already have a Google
 * account, so there's nothing new to agree to.
 *
 * SETUP - about three minutes:
 *
 *  1. Go to https://sheets.new and make a blank sheet. Name it "Filed waitlist".
 *  2. Extensions -> Apps Script. Delete whatever is in the editor.
 *  3. Paste this whole file in. Save.
 *  4. Click Deploy -> New deployment.
 *       Type:           Web app        (click the gear icon to find it)
 *       Execute as:     Me
 *       Who has access: Anyone
 *  5. Click Deploy. Google will ask you to authorise it - that's it asking
 *     permission to write to your own sheet. Allow it.
 *  6. Copy the Web app URL it gives you. It looks like
 *     https://script.google.com/macros/s/AKfy..../exec
 *  7. Send me that URL and I'll wire it into the site. It is not a password -
 *     it only accepts new signups, it can't read anything back out.
 */

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);           // two people signing up at once won't clash

  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];

    if (sheet.getLastRow() === 0) {
      sheet.appendRow(["Joined at", "Email", "WhatsApp", "Source"]);
      sheet.getRange(1, 1, 1, 4).setFontWeight("bold");
      sheet.setFrozenRows(1);
    }

    var d = JSON.parse(e.postData.contents);

    // Stop the same email being added twice.
    var existing = sheet.getLastRow() > 1
      ? sheet.getRange(2, 2, sheet.getLastRow() - 1, 1).getValues().flat()
      : [];
    if (existing.indexOf(d.email) !== -1) {
      return json({ ok: true, alreadyJoined: true });
    }

    sheet.appendRow([
      d.at || new Date().toISOString(),
      d.email || "",
      d.phone || "",
      d.source || "",
    ]);

    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

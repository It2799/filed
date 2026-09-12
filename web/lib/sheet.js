/**
 * A real .xlsx, not a CSV renamed.
 *
 * A CSV loses everything the moment it lands in Excel: 1,32,95,129 becomes
 * text or gets mangled into scientific notation, ₹ turns to mojibake without a
 * byte-order mark, and the person opening it has to widen every column by
 * hand. exceljs is already a dependency here, so the download is a real
 * workbook - typed number cells with Indian-format masks, a frozen header row
 * and a filter on every column.
 */

import ExcelJS from "exceljs";

// Indian digit grouping in a cell format string. Excel's own #,##0 groups in
// thousands the western way; this gives 1,32,95,129.
const INT_IN = "[>=10000000]##\\,##\\,##\\,##0;[>=100000]##\\,##\\,##0;##,##0";
const MONEY_IN =
  '"₹"' + "[>=10000000]##\\,##\\,##\\,##0;" +
  '"₹"' + "[>=100000]##\\,##\\,##0;" +
  '"₹"' + "##,##0";

const HEADER_FILL = "FF1F2430";
const HEADER_FONT = "FFFFFFFF";

/**
 * @param {object} opts
 *  - sheetName   tab name
 *  - columns     [{ header, key, width, kind }] where kind is
 *                "int" | "money" | "price" | "pct" | "date" | undefined
 *  - rows        plain objects keyed by column key
 *  - notes       lines written above the table, so the file explains itself
 *                once it is off the site and in somebody's inbox
 */
export async function workbook({ sheetName, columns, rows, notes = [] }) {
  const wb = new ExcelJS.Workbook();
  wb.creator = "Market Tide";
  wb.created = new Date();
  const ws = wb.addWorksheet(sheetName, {
    views: [{ state: "frozen", ySplit: notes.length + 1 }],
  });

  // The notes sit above the header, which is why the freeze and the table
  // start below them.
  for (const line of notes) {
    const row = ws.addRow([line]);
    row.font = { size: 10, color: { argb: "FF6F727A" } };
  }

  const header = ws.addRow(columns.map((c) => c.header));
  header.eachCell((cell) => {
    cell.fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: { argb: HEADER_FILL },
    };
    cell.font = { bold: true, color: { argb: HEADER_FONT }, size: 11 };
    cell.alignment = { vertical: "middle" };
    cell.border = { bottom: { style: "thin", color: { argb: "FF3A3F4B" } } };
  });
  header.height = 20;

  for (const r of rows) {
    const cells = columns.map((c) => {
      const v = r[c.key];
      if (v === null || v === undefined || v === "") return null;
      if (c.kind === "int" || c.kind === "money" || c.kind === "price") {
        const n = Number(v);
        return Number.isFinite(n) ? n : v;
      }
      if (c.kind === "pct") {
        const n = Number(String(v).replace("%", ""));
        // Excel percentages are fractions: 3.61% is stored as 0.0361.
        return Number.isFinite(n) ? n / 100 : v;
      }
      return v;
    });
    const row = ws.addRow(cells);
    columns.forEach((c, i) => {
      const cell = row.getCell(i + 1);
      if (c.kind === "int") cell.numFmt = INT_IN;
      else if (c.kind === "money") cell.numFmt = MONEY_IN;
      else if (c.kind === "price") cell.numFmt = '"₹"#,##0.00';
      else if (c.kind === "pct") cell.numFmt = "0.00%";
      else if (c.kind === "date") cell.alignment = { horizontal: "left" };
    });
  }

  columns.forEach((c, i) => {
    ws.getColumn(i + 1).width = c.width || 16;
  });

  // A filter on the header row, so the file is usable the second it opens.
  if (rows.length) {
    ws.autoFilter = {
      from: { row: notes.length + 1, column: 1 },
      to: { row: notes.length + 1 + rows.length, column: columns.length },
    };
  }

  return Buffer.from(await wb.xlsx.writeBuffer());
}

/** The response shape both API routes return for `?format=xlsx`. */
export function download(buf, filename) {
  return new Response(buf, {
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}

/** 2026-09-11 -> 11 Sep 2026, which is what a person writes on a file. */
export function stamp(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

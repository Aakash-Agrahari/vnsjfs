const nf0 = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 0 });
export const mw = (v) => (v == null ? "–" : `${nf0.format(v)} MW`);
export const num = (v) => (v == null ? "–" : nf0.format(v));
export const pct = (v) => (v == null ? "–" : `${v.toFixed(1)}%`);

const opts = { timeZone: "Europe/London" };
export const hhmm = (ms) =>
  new Date(ms).toLocaleTimeString("en-GB", { ...opts, hour: "2-digit", minute: "2-digit" });
export const dayMonth = (ms) =>
  new Date(ms).toLocaleDateString("en-GB", { ...opts, day: "numeric", month: "short" });
export const dayMonthTime = (ms) => `${dayMonth(ms)}, ${hhmm(ms)}`;
export const longDate = (iso) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", {
    timeZone: "UTC", weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

export function downloadCsv(filename, rows) {
  const head = Object.keys(rows[0]);
  const body = rows.map((r) => head.map((h) => r[h] ?? "").join(","));
  const blob = new Blob([[head.join(","), ...body].join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

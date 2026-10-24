// Same-origin by default (Vite proxy in dev, nginx in Docker, Vercel rewrites in production).
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function get(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/api/${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join("; ");
    } catch {
      /* keep default message */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  meta: () => get("meta"),
  forecast: (deliveryDate, cutoff) => get("forecast", { delivery_date: deliveryDate, cutoff }),
  accuracy: (p) => get("accuracy", p),
  horizonProfile: (start, end) => get("horizon-profile", { start, end }),
};

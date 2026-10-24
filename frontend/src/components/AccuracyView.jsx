import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { dayMonth, dayMonthTime, mw, num, pct } from "../format.js";
import Kpi from "./Kpi.jsx";

export default function AccuracyView({ meta, cutoff, setCutoff }) {
  const [start, setStart] = useState(meta.delivery_first);
  const [end, setEnd] = useState(meta.delivery_last);
  const [mode, setMode] = useState("dayahead");
  const [horizon, setHorizon] = useState(24);
  const [res, setRes] = useState(null);
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (end < start) { setError("The end date is before the start date."); return; }
    let live = true;
    setError(null);
    const t = setTimeout(() => {
      api.accuracy({ start, end, mode, cutoff, horizon })
        .then((d) => live && setRes(d))
        .catch((e) => live && (setRes(null), setError(e.message)));
    }, 150); // debounce slider drags
    return () => { live = false; clearTimeout(t); };
  }, [start, end, mode, cutoff, horizon]);

  useEffect(() => {
    if (end < start) return;
    let live = true;
    api.horizonProfile(start, end).then((d) => live && setProfile(d.profile)).catch(() => {});
    return () => { live = false; };
  }, [start, end]);

  const m = res?.metrics;
  const series = (res?.series ?? []).map((p) => ({ ms: Date.parse(p.t), forecast: p.forecast_mw, actual: p.actual_mw }));
  const hist = (res?.histogram ?? []).map((b) => ({ ...b, label: `${b.from_mw}`, over: b.from_mw >= 0 }));
  const ruleText = mode === "dayahead"
    ? `forecast published before ${cutoff} UK time on the day before delivery`
    : `latest forecast published at least ${horizon} hours before each half-hour`;

  return (
    <section>
      <header className="section-head">
        <div>
          <h2>How wrong has the wind forecast been?</h2>
          <p className="lede">
            Forecast versus actual output for {ruleText}. Positive error means the forecast promised
            more wind than arrived.
          </p>
        </div>
      </header>

      <div className="controls">
        <label>From
          <input type="date" value={start} min={meta.delivery_first} max={meta.delivery_last}
            onChange={(e) => e.target.value && setStart(e.target.value)} />
        </label>
        <label>To
          <input type="date" value={end} min={meta.delivery_first} max={meta.delivery_last}
            onChange={(e) => e.target.value && setEnd(e.target.value)} />
        </label>
        <fieldset className="seg">
          <legend>Which forecast to judge</legend>
          <label><input type="radio" name="mode" checked={mode === "dayahead"} onChange={() => setMode("dayahead")} /> Day-ahead decision</label>
          <label><input type="radio" name="mode" checked={mode === "horizon"} onChange={() => setMode("horizon")} /> Fixed lead time</label>
        </fieldset>
        {mode === "dayahead" ? (
          <label>Decision time (day before)
            <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
          </label>
        ) : (
          <label>Lead time: {horizon} h
            <input type="range" min="1" max={meta.max_horizon_h} value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))} />
          </label>
        )}
      </div>

      {error && <div className="notice error" role="alert">{error}</div>}

      {m?.n > 0 && (
        <>
          <div className="kpis">
            <Kpi label="Typical miss (MAE)" value={mw(m.mae_mw)} hint={`${pct(m.nmae_pct)} of average output (${num(m.mean_actual_mw)} MW)`} />
            <Kpi label="Bad-day miss (RMSE)" value={mw(m.rmse_mw)} hint="Penalises large errors more" />
            <Kpi label="Systematic lean (bias)" value={`${m.bias_mw > 0 ? "+" : ""}${num(m.bias_mw)} MW`}
              hint={m.bias_mw > 0 ? "Forecast tends to overstate wind" : "Forecast tends to understate wind"} />
            <Kpi tone="risk" label="Shortfall to cover (P90)" value={mw(m.p90_over_mw)}
              hint={`Forecast was too high by this much or more in 1 in 10 periods`} />
            <Kpi label="Surplus risk (P90)" value={mw(m.p90_under_mw)}
              hint="Forecast too low by this much or more in 1 in 10 periods" />
            <Kpi label="Half-hours analysed" value={num(m.n)} hint={`${pct(m.over_share_pct)} were over-forecast`} />
          </div>

          <ChartCard title="Forecast against actual output">
            <ResponsiveContainer width="100%" height={340}>
              <ComposedChart data={series} margin={{ top: 8, right: 18, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="ms" type="number" scale="time" domain={["dataMin", "dataMax"]}
                  tickFormatter={dayMonth} stroke="var(--muted)" />
                <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)} GW`} stroke="var(--muted)" width={62} />
                <Tooltip labelFormatter={dayMonthTime} formatter={(v) => mw(v)} />
                <Legend verticalAlign="top" height={30} />
                <Line name="Forecast" dataKey="forecast" stroke="var(--forecast)" strokeWidth={1.6} dot={false} isAnimationActive={false} />
                <Line name="Actual" dataKey="actual" stroke="var(--actual)" strokeWidth={1.6} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartCard>

          <div className="grid2">
            <ChartCard title="Error by lead time" note="How the miss grows the further ahead the forecast was made">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={profile ?? []} margin={{ top: 8, right: 14, bottom: 14, left: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="horizon_h" stroke="var(--muted)" label={{ value: "Hours ahead of delivery", position: "insideBottom", offset: -8, fill: "var(--muted)" }} />
                  <YAxis stroke="var(--muted)" width={56} />
                  <Tooltip formatter={(v) => mw(v)} labelFormatter={(h) => `${h} h ahead`} />
                  <Legend verticalAlign="top" height={28} />
                  <Line name="MAE" dataKey="mae_mw" stroke="var(--forecast)" strokeWidth={2.2} dot={false} isAnimationActive={false} />
                  <Line name="P90 abs. error" dataKey="p90_abs_mw" stroke="var(--risk)" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line name="Bias" dataKey="bias_mw" stroke="var(--muted)" strokeDasharray="4 3" dot={false} isAnimationActive={false} />
                  {mode === "horizon" && <ReferenceLine x={horizon} stroke="var(--ink)" strokeDasharray="2 3" />}
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Error by time of day" note="Mean absolute error per UK local hour">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={res.by_hour} margin={{ top: 8, right: 14, bottom: 14, left: 0 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="hour" stroke="var(--muted)" label={{ value: "Hour of day", position: "insideBottom", offset: -8, fill: "var(--muted)" }} />
                  <YAxis stroke="var(--muted)" width={56} />
                  <Tooltip formatter={(v) => mw(v)} labelFormatter={(h) => `${String(h).padStart(2, "0")}:00`} />
                  <Bar name="MAE" dataKey="mae_mw" fill="var(--forecast)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <ChartCard title="How big are the misses?" note="Number of half-hours in each error band. Right of zero = forecast too high (you would be short)">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={hist} margin={{ top: 8, right: 14, bottom: 14, left: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="label" stroke="var(--muted)" interval="preserveStartEnd"
                  label={{ value: "Error band start (MW)", position: "insideBottom", offset: -8, fill: "var(--muted)" }} />
                <YAxis stroke="var(--muted)" width={48} />
                <Tooltip formatter={(v) => [v, "half-hours"]} labelFormatter={(l) => `${l} to ${Number(l) + 500} MW`} />
                <Bar dataKey="count" isAnimationActive={false}>
                  {hist.map((b) => <Cell key={b.from_mw} fill={b.over ? "var(--risk)" : "var(--forecast)"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Day by day">
            <div className="table-wrap">
              <table>
                <thead><tr><th>Delivery day</th><th>MAE</th><th>Bias</th><th>Half-hours</th></tr></thead>
                <tbody>
                  {res.by_day.map((d) => (
                    <tr key={d.date}>
                      <td>{d.date}</td><td>{num(d.mae_mw)} MW</td>
                      <td>{d.bias_mw > 0 ? "+" : ""}{num(d.bias_mw)} MW</td><td>{d.n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartCard>
        </>
      )}
      {res && m?.n === 0 && <div className="notice">No half-hours with both a forecast and an actual in this selection.</div>}
    </section>
  );
}

function ChartCard({ title, note, children }) {
  return (
    <div className="chart-card">
      <h3>{title}</h3>
      {note && <p className="chart-note">{note}</p>}
      {children}
    </div>
  );
}

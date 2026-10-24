import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { downloadCsv, hhmm, longDate, mw, num, dayMonthTime } from "../format.js";
import Kpi from "./Kpi.jsx";

export default function ForecastView({ meta, deliveryDate, setDeliveryDate, cutoff, setCutoff }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [reveal, setReveal] = useState(false);

  useEffect(() => {
    let live = true;
    setError(null);
    api.forecast(deliveryDate, cutoff)
      .then((d) => live && setData(d))
      .catch((e) => live && (setData(null), setError(e.message)));
    return () => { live = false; };
  }, [deliveryDate, cutoff]);

  const rows = useMemo(
    () => (data?.points ?? []).map((p) => ({
      ms: Date.parse(p.t), forecast: p.forecast_mw, actual: p.actual_mw,
      published: p.published,
    })),
    [data]
  );

  const decisionLocal = data ? dayMonthTime(Date.parse(data.decision_time)) : "";
  const s = data?.summary;
  const te = data?.typical_error;

  const exportCsv = () =>
    downloadCsv(`wind_forecast_${deliveryDate}_cutoff_${cutoff.replace(":", "")}.csv`,
      (data?.points ?? []).map((p) => ({
        start_time_utc: p.t, forecast_mw: p.forecast_mw, forecast_published_utc: p.published,
        ...(reveal ? { actual_mw: p.actual_mw } : {}),
      })));

  return (
    <section>
      <header className="section-head">
        <div>
          <h2>Wind forecast for {longDate(deliveryDate)}</h2>
          <p className="lede">
            What you can see when you have to buy: the most recent national wind forecast published
            before <strong>{decisionLocal || "the decision time"}</strong>.
          </p>
        </div>
        <button className="btn" onClick={exportCsv} disabled={!data}>Download CSV</button>
      </header>

      <div className="controls">
        <label>Delivery day
          <input type="date" value={deliveryDate} min={meta.delivery_first} max={meta.delivery_last}
            onChange={(e) => e.target.value && setDeliveryDate(e.target.value)} />
        </label>
        <label>Buy decision time (day before, UK time)
          <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={reveal} onChange={(e) => setReveal(e.target.checked)} />
          Show what actually happened
        </label>
      </div>

      {error && <div className="notice error" role="alert">{error}</div>}

      {s && (
        <>
          <div className="kpis">
            <Kpi label="Average forecast wind" value={mw(s.avg_mw)} hint={`${num(s.energy_mwh)} MWh over the day`} />
            <Kpi label="Peak / lowest half-hour" value={`${num(s.peak_mw)} / ${num(s.trough_mw)} MW`} />
            <Kpi label="Forecast versions used"
              value={s.first_published === s.last_published ? hhmm(Date.parse(s.last_published)) :
                `${hhmm(Date.parse(s.first_published))}–${hhmm(Date.parse(s.last_published))}`}
              hint={`published ${dayMonthTime(Date.parse(s.last_published))} at the latest`} />
            <Kpi tone="risk" label="Plan for a shortfall of"
              value={mw(te.p90_over_mw)}
              hint={`In 1 in 10 half-hours the forecast was too high by at least this much (typical error ${num(te.mae_mw)} MW)`} />
          </div>

          <div className="chart-card">
            <ResponsiveContainer width="100%" height={380}>
              <ComposedChart data={rows} margin={{ top: 12, right: 18, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="ms" type="number" scale="time" domain={["dataMin", "dataMax"]}
                  tickFormatter={hhmm} tickCount={13} stroke="var(--muted)" />
                <YAxis tickFormatter={(v) => `${(v / 1000).toFixed(0)} GW`} stroke="var(--muted)" width={62} />
                <Tooltip content={<ChartTip reveal={reveal} />} />
                <Legend verticalAlign="top" height={30} />
                <Line name="Forecast available at decision time" dataKey="forecast" stroke="var(--forecast)"
                  strokeWidth={2.6} dot={false} type="monotone" connectNulls={false} isAnimationActive={false} />
                {reveal && (
                  <Line name="Actual output" dataKey="actual" stroke="var(--actual)" strokeWidth={2}
                    strokeDasharray="5 4" dot={false} type="monotone" isAnimationActive={false} />
                )}
                {rows.length > 0 && <ReferenceLine y={0} stroke="var(--muted)" />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <p className="footnote">
            Times are UK local. {s.periods_with_forecast} of {s.periods_total} half-hours had a forecast by
            the decision time. Risk figures use every delivery day from {te.basis.replace(" to ", " to ")} under
            the same decision time. Positive error means the forecast overstated wind.
          </p>
        </>
      )}
    </section>
  );
}

function ChartTip({ active, payload, reveal }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const err = r.actual != null && r.forecast != null ? r.forecast - r.actual : null;
  return (
    <div className="tip">
      <strong>{hhmm(r.ms)}</strong>
      <div>Forecast: {mw(r.forecast)}</div>
      {r.published && <div className="muted">published {dayMonthTime(Date.parse(r.published))}</div>}
      {reveal && <div>Actual: {mw(r.actual)}</div>}
      {reveal && err != null && <div>Error: {err > 0 ? "+" : ""}{num(err)} MW</div>}
    </div>
  );
}

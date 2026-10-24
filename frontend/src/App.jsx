import { useEffect, useState } from "react";
import { api } from "./api.js";
import ForecastView from "./components/ForecastView.jsx";
import AccuracyView from "./components/AccuracyView.jsx";

export default function App() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("forecast");
  const [deliveryDate, setDeliveryDate] = useState("2026-01-15");
  const [cutoff, setCutoff] = useState("09:00");

  useEffect(() => {
    api.meta()
      .then((m) => { setMeta(m); setCutoff(m.default_cutoff); })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="mark" aria-hidden="true" />
          <div>
            <h1>Wind Desk</h1>
            <p>GB day-ahead wind forecast and accuracy for power buyers</p>
          </div>
        </div>
        <nav className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "forecast"} onClick={() => setTab("forecast")}>Tomorrow's wind</button>
          <button role="tab" aria-selected={tab === "accuracy"} onClick={() => setTab("accuracy")}>Forecast accuracy</button>
        </nav>
      </header>

      <main>
        {error && (
          <div className="notice error" role="alert">
            Could not reach the data service: {error}
          </div>
        )}
        {!meta && !error && <div className="notice">Loading…</div>}
        {meta?.source === "synthetic" && (
          <div className="notice warn">Showing synthetic demo data, not real Elexon data. Run the data fetch script to load January 2026 from Elexon.</div>
        )}
        {meta && tab === "forecast" && (
          <ForecastView meta={meta} deliveryDate={deliveryDate} setDeliveryDate={setDeliveryDate}
            cutoff={cutoff} setCutoff={setCutoff} />
        )}
        {meta && tab === "accuracy" && <AccuracyView meta={meta} cutoff={cutoff} setCutoff={setCutoff} />}
      </main>

      <footer>
        Contains BMRS data © Elexon Limited. National wind generation (FUELHH) and wind forecasts (WINDFOR),
        purchase decisions made in January 2026.
        {meta?.fetched_at && <> Data fetched {meta.fetched_at.slice(0, 10)}.</>}
      </footer>
    </div>
  );
}

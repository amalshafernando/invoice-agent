import { useCallback, useEffect, useRef, useState } from "react";
import { api, Brief, Metrics, Sample } from "../api";
import { Badge, Err, Kpi, usd } from "../components";

export default function Inbox({ open }: { open: (id: string) => void }) {
  const [rows, setRows] = useState<Brief[]>([]);
  const [m, setM] = useState<Metrics>();
  const [samples, setSamples] = useState<Sample[]>([]);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const file = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try { const [r, mm] = await Promise.all([api.cases(), api.metrics()]); setRows(r); setM(mm); }
    catch (e) { setErr(String(e)); }
  }, []);
  useEffect(() => { load(); api.samples().then((s) => { setSamples(s); setPick(s[0]?.case_id ?? ""); }).catch((e) => setErr(String(e))); }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr("");
    try { await fn(); await load(); } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };
  const waiting = rows.filter((r) => r.status === "AWAITING_REVIEW").length;

  return (<>
    <Err e={err} />
    <div className="cards">
      <Kpi t="Cases processed" v={m?.cases ?? "–"} />
      <Kpi t="Awaiting human review" v={waiting} />
      <Kpi t="Touchless rate" v={m ? `${Math.round(m.touchless_rate * 100)}%` : "–"} />
      <Kpi t="Avg cost / invoice" v={usd(m?.avg_cost_usd)} />
      <Kpi t="Budget cap" v={usd(m?.budget_cap_usd)} />
    </div>
    <div className="bar">
      <select value={pick} onChange={(e) => setPick(e.target.value)}>
        {samples.map((s) => <option key={s.case_id} value={s.case_id}>{s.case_id} · {s.scenario} · {s.total.toFixed(2)}</option>)}
      </select>
      <button disabled={busy || !pick} onClick={() => run(() => api.fromSample(pick))}>Process sample invoice</button>
      <input ref={file} type="file" accept="application/pdf" hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) run(() => api.upload(f)); }} />
      <button className="ghost" disabled={busy} onClick={() => file.current?.click()}>Upload PDF</button>
      <button className="ghost" onClick={load}>Refresh</button>
    </div>
    <table>
      <thead><tr><th>Case</th><th>Invoice</th><th>Supplier</th><th>Total</th><th>Policy</th><th>Status</th><th>Cost</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={r.case_id} className="click" onClick={() => open(r.case_id)}>
          <td className="mono">{r.case_id}</td><td>{r.invoice_no}</td><td>{r.supplier}</td>
          <td>{r.total?.toFixed(2)}</td><td><Badge v={r.action} /></td><td><Badge v={r.status} /></td><td>{usd(r.cost_usd)}</td>
        </tr>))}
        {rows.length === 0 && <tr><td colSpan={7}>No cases yet — process a sample invoice.</td></tr>}</tbody>
    </table>
  </>);
}

import { useEffect, useState } from "react";
import { api, EvalReport, Metrics } from "../api";
import { Badge, Err, Kpi, usd } from "../components";

const pct = (n?: number) => (n === undefined ? "–" : `${(n * 100).toFixed(1)}%`);

export default function Observability() {
  const [ev, setEv] = useState<EvalReport>({ rows: [] });
  const [m, setM] = useState<Metrics>();
  const [audit, setAudit] = useState<string>("…");
  const [err, setErr] = useState("");
  useEffect(() => {
    api.evalReport().then(setEv).catch((e) => setErr(String(e)));
    api.metrics().then(setM).catch((e) => setErr(String(e)));
    api.audit().then((a) => setAudit(a.ok ? `intact (${a.rows} rows)` : "BROKEN")).catch(() => setAudit("unavailable"));
  }, []);
  return (<>
    <Err e={err} />
    <h3>Automated evaluation {ev.llm && <small>(LLM: {ev.llm})</small>}</h3>
    <div className="cards">
      <Kpi t="Decision accuracy" v={pct(ev.decision_accuracy)} />
      <Kpi t="False-approve rate (must be 0)" v={pct(ev.false_approve_rate)} />
      <Kpi t="Injection block rate" v={pct(ev.injection_block_rate)} />
      <Kpi t="Avg cost / invoice" v={usd(ev.avg_cost_usd)} />
      <Kpi t="p95 latency" v={ev.p95_latency_s === undefined ? "–" : `${ev.p95_latency_s}s`} />
      <Kpi t="Gate" v={ev.passed === undefined ? "–" : ev.passed ? "PASS" : "FAIL"} />
    </div>
    <table><thead><tr><th>Case</th><th>Scenario</th><th>Expected</th><th>Actual</th><th>Result</th><th>Reasons</th></tr></thead>
      <tbody>{ev.rows.map((r) => (<tr key={r.case_id}><td>{r.case_id}</td><td>{r.scenario}</td>
        <td><Badge v={r.expected} /></td><td><Badge v={r.actual} /></td><td>{r.ok ? "✔" : "✘"}</td><td>{r.reasons.join(", ")}</td></tr>))}
        {ev.rows.length === 0 && <tr><td colSpan={6}>Run <code>python -m evals.run_eval</code></td></tr>}</tbody></table>
    <h3>Live system</h3>
    <div className="cards">
      <Kpi t="Cases (live)" v={m?.cases ?? "–"} /><Kpi t="Total LLM cost" v={usd(m?.total_cost_usd)} />
      <Kpi t="Avg latency" v={m ? `${m.avg_latency_s}s` : "–"} /><Kpi t="Audit chain" v={audit} />
    </div>
  </>);
}

import { useEffect, useState } from "react";
import { api, CaseDetail } from "../api";
import { Badge, Err, usd } from "../components";

export default function CaseReview({ id, back }: { id: string; back: () => void }) {
  const [c, setC] = useState<CaseDetail>();
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.caseDetail(id).then(setC).catch((e) => setErr(String(e))); }, [id]);

  const decide = async (d: "approve" | "reject") => {
    setBusy(true);
    try { setC(await api.review(id, d, comment)); } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };
  if (!c) return <><Err e={err} /><p>Loading…</p></>;
  const ex = c.extraction, d = c.decision;
  const pending = c.status === "AWAITING_REVIEW";

  return (<>
    <Err e={err} />
    <div className="bar"><button className="ghost" onClick={back}>← Inbox</button>
      <h2 style={{ margin: 0 }}>{ex?.invoice_no}</h2><Badge v={d.action} /><Badge v={c.status} /></div>
    {c.explanation && <div className="warn">{c.explanation}</div>}
    <div className="grid2">
      <div>
        <h3>Evidence: invoice vs purchase order</h3>
        <table><thead><tr><th>Item</th><th>Qty inv / recv</th><th>Price inv / PO</th><th>Δ price</th></tr></thead>
          <tbody>{d.line_checks.map((l, i) => (
            <tr key={i}><td>{l.description}</td>
              <td className={l.qty_over ? "var hi" : ""}>{l.inv_qty} / {l.po_qty_received}</td>
              <td>{l.inv_price} / {l.po_price}</td>
              <td className={`var ${Math.abs(l.price_var_pct) > 2 ? "hi" : ""}`}>{l.price_var_pct}%</td></tr>))}
            {d.line_checks.length === 0 && <tr><td colSpan={4}>No PO lines to compare.</td></tr>}</tbody></table>
        <p>Invoice total <b>{d.invoice_total}</b> · PO total <b>{d.po_total ?? "–"}</b> · Supplier <b>{c.supplier?.name ?? "?"}</b> ({c.supplier?.status ?? "?"})</p>
        <p>Policy reasons: {d.reasons.length ? d.reasons.join(", ") : "none"}</p>
        {c.precedents && c.precedents.length > 0 && (
          <div className="warn" style={{ marginTop: 8 }}>
            <b>Episodic Memory (past HITL precedents):</b>
            <ul>{c.precedents.map((p) => (
              <li key={p.id}>[{Math.round(p.similarity * 100)}% match] {p.decision.toUpperCase()} by {p.reviewer} ({p.reason_code}) — {p.comment || p.summary}</li>
            ))}</ul>
          </div>
        )}
        {ex?.notes && <p className="mono">Document notes (untrusted, never fed to the agent): {ex.notes}</p>}
      </div>
      <div>
        <h3>Decision</h3>
        {pending ? (<>
          <textarea rows={3} style={{ width: "100%" }} placeholder="Reviewer comment" value={comment} onChange={(e) => setComment(e.target.value)} />
          <div className="bar"><button className="ok" disabled={busy} onClick={() => decide("approve")}>Approve → create draft</button>
            <button className="bad" disabled={busy} onClick={() => decide("reject")}>Reject → open ticket</button></div>
          <p>Workflow is paused (checkpointed). Approving only creates an invoice <b>draft</b>; payment stays in the ERP.</p>
        </>) : <p>Outcome: <Badge v={c.status} /> {c.draft_id && <span className="mono">draft {c.draft_id}</span>} {c.ticket_id && <span className="mono">ticket {c.ticket_id}</span>}</p>}
        <h3>Run summary</h3>
        <p>Cost {usd(c.cost_usd)} · {c.tokens} tokens · {c.latency_s}s · extraction confidence {ex?.extraction_confidence}</p>
        <h3>Agent trace</h3>
        <ol className="mono">{c.events.map((e, i) => <li key={i}>{e}</li>)}</ol>
      </div>
    </div>
  </>);
}

export type Brief = { case_id: string; label: string; status: string; invoice_no?: string; supplier?: string;
  total?: number; action?: string; reasons: string[]; cost_usd: number; latency_s: number; created_at: number };
export type LineCheck = { description: string; po_description?: string; match_score?: number; inv_qty: number; po_qty_received: number; inv_price: number;
  po_price: number; price_var_pct: number; qty_over: boolean };
export type Precedent = { id: number; supplier_id: string; reason_code: string; decision: string; reviewer: string; comment: string; summary: string; similarity: number };
export type RoiMetrics = { invoices_processed: number; manual_benchmark_usd: number; ai_total_cost_usd: number;
  processing_savings_usd: number; prevented_leakage_usd: number; total_business_value_usd: number;
  touchless_rate: number; hours_saved: number; precedents_learned: number; guardrail_mode: string };
export type Span = { name: string; ms: number; attrs: Record<string, string | number | boolean> };
export type CaseDetail = { case_id: string; status: string; label: string; explanation?: string; draft_id?: string;
  ticket_id?: string; cost_usd: number; tokens: number; latency_s: number; events: string[]; spans: Span[];
  extraction?: { invoice_no: string; supplier_name: string; po_number?: string; total: number; notes: string;
    extraction_confidence: number; items: { description: string; quantity: number; unit_price: number }[] };
  decision: { action: string; reasons: string[]; line_checks: LineCheck[]; max_price_var_pct: number;
    invoice_total: number; po_total?: number };
  precedents?: Precedent[];
  supplier?: { name: string; status: string }; po?: { po_number: string; status: string } };
export type Metrics = { cases: number; by_status: Record<string, number>; total_cost_usd: number;
  avg_cost_usd: number; avg_latency_s: number; budget_cap_usd: number; touchless_rate: number };
export type EvalRow = { case_id: string; scenario: string; expected: string; actual: string; ok: boolean;
  reasons: string[]; cost_usd: number; latency_s: number; false_approve: boolean };
export type EvalReport = { rows: EvalRow[]; decision_accuracy?: number; false_approve_rate?: number;
  injection_block_rate?: number; avg_cost_usd?: number; p95_latency_s?: number; passed?: boolean; llm?: string };
export type Sample = { case_id: string; scenario: string; invoice_no: string; total: number };

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
const json = (b: unknown): RequestInit => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(b) });

export const api = {
  samples: () => req<Sample[]>("/api/samples"),
  cases: () => req<Brief[]>("/api/cases"),
  caseDetail: (id: string) => req<CaseDetail>(`/api/cases/${id}`),
  fromSample: (id: string) => req<CaseDetail>(`/api/cases/sample/${id}`, { method: "POST" }),
  upload: (f: File) => { const fd = new FormData(); fd.append("file", f); return req<CaseDetail>("/api/cases/upload", { method: "POST", body: fd }); },
  review: (id: string, decision: "approve" | "reject", comment: string) => req<CaseDetail>(`/api/cases/${id}/review`, json({ decision, comment })),
  metrics: () => req<Metrics>("/api/metrics"),
  roi: () => req<RoiMetrics>("/api/roi"),
  evalReport: () => req<EvalReport>("/api/eval"),
  audit: () => req<{ ok: boolean; rows: number }>("/api/audit"),
};

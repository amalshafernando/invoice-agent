import { ReactNode } from "react";
export const Badge = ({ v }: { v?: string }) => (v ? <span className={`badge ${v}`}>{v.replaceAll("_", " ")}</span> : null);
export const Kpi = ({ t, v }: { t: string; v: ReactNode }) => (
  <div className="card"><h3>{t}</h3><div className="v">{v}</div></div>);
export const Err = ({ e }: { e: string }) => (e ? <div className="err">{e}</div> : null);
export const usd = (n?: number) => (n === undefined ? "–" : `$${n.toFixed(5)}`);

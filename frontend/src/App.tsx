import { useEffect, useState } from "react";
import CaseReview from "./pages/CaseReview";
import Inbox from "./pages/Inbox";
import Observability from "./pages/Observability";

type Route = { page: "inbox" | "obs" | "case"; id?: string };
const parse = (h: string): Route => {
  const m = h.replace("#", "").split("/");
  return m[0] === "case" && m[1] ? { page: "case", id: m[1] } : m[0] === "obs" ? { page: "obs" } : { page: "inbox" };
};

export default function App() {
  const [r, setR] = useState<Route>(parse(location.hash));
  useEffect(() => { const f = () => setR(parse(location.hash)); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return (<>
    <header><h1>Governed Invoice Agent</h1>
      <nav><a className={r.page !== "obs" ? "on" : ""} href="#inbox">Inbox</a>
        <a className={r.page === "obs" ? "on" : ""} href="#obs">Observability &amp; Eval</a></nav></header>
    <main>
      {r.page === "inbox" && <Inbox open={(id) => (location.hash = `case/${id}`)} />}
      {r.page === "case" && r.id && <CaseReview id={r.id} back={() => (location.hash = "inbox")} />}
      {r.page === "obs" && <Observability />}
    </main></>);
}

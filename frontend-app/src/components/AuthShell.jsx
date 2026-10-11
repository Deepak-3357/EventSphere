import { Link } from "react-router-dom";
import { BrandLogo } from "./BrandLogo.jsx";

export function AuthShell({ title, subtitle, children, footer }) {
  return <div className="min-h-screen bg-mist"><header className="border-b border-line bg-white"><div className="mx-auto max-w-7xl px-6 py-5"><BrandLogo /></div></header><main className="mx-auto flex max-w-md flex-col px-6 py-14"><div className="mb-8"><p className="text-sm font-bold uppercase tracking-[0.18em] text-electric">Student access</p><h1 className="mt-3 text-4xl font-black tracking-tight text-ink">{title}</h1><p className="mt-3 leading-7 text-slate-500">{subtitle}</p></div>{children}<p className="mt-8 text-center text-sm text-slate-500">{footer}</p><Link className="mt-6 text-center text-sm font-bold text-electric hover:text-ink" to="/">← Back to EventSphere</Link></main></div>;
}

export function AuthNotice({ error, success }) {
  if (!error && !success) return null;
  return <div className={`mt-4 rounded-xl p-3 text-sm ${error ? "bg-red-50 text-red-800" : "bg-emerald-50 text-emerald-800"}`} role="alert">{error || success}</div>;
}

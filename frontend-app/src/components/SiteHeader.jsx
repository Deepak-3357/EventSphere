import { ArrowRight, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { BrandLogo } from "./BrandLogo.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { roleHomePath } from "../auth/rolePolicy.js";

export function SiteHeader() {
  const { profile, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const home = profile ? roleHomePath(profile.role) : "/";
  return <header className="sticky top-0 z-20 border-b border-line/80 bg-white/90 backdrop-blur" data-testid="site-header">
    <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
      <BrandLogo href={home} />
      <button className="rounded-xl p-2 text-ink md:hidden" onClick={() => setOpen((value) => !value)} aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open}>{open ? <X /> : <Menu />}</button>
      <nav className={`${open ? "flex" : "hidden"} absolute left-0 right-0 top-full flex-col gap-4 border-b border-line bg-white p-6 md:static md:flex md:flex-row md:items-center md:border-0 md:bg-transparent md:p-0`} aria-label="Primary navigation">
        <Link className="text-sm font-semibold text-slate-600 transition hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-electric" to="/events/">Browse events</Link>
        {loading ? <span className="h-5 w-20 animate-pulse rounded bg-mist" aria-label="Loading account" /> : profile ? <Link className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-bold text-white transition hover:bg-electric focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-electric" to={home}>Dashboard <ArrowRight size={15} aria-hidden="true" /></Link> : <Link className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-bold text-white transition hover:bg-electric focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-electric" to="/login/">Sign in <ArrowRight size={15} aria-hidden="true" /></Link>}
      </nav>
    </div>
  </header>;
}

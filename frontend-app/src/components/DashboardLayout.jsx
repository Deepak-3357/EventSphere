import { Bell, ChevronRight, LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { BrandLogo } from "./BrandLogo.jsx";
import { useAuth } from "../auth/AuthProvider.jsx";
import { roleHomePath } from "../auth/rolePolicy.js";

const labels = { student: "Student workspace", organizer: "Organizer workspace", admin: "Administration" };

export function DashboardLayout({ role, title, eyebrow, children, navItems = [] }) {
  const { profile, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const home = roleHomePath(role);
  async function logout() { await signOut(); window.location.assign("/"); }
  return <div className="min-h-screen bg-mist text-ink">
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 flex-col bg-ink px-5 py-6 text-white lg:flex">
      <BrandLogo href={home} />
      <p className="mt-10 px-3 text-xs font-bold uppercase tracking-[0.18em] text-blue-200/70">{labels[role]}</p>
      <nav className="mt-4 space-y-1" aria-label="Dashboard navigation">{navItems.map((item) => <Link key={item.href} to={item.href} className="flex items-center justify-between rounded-xl px-3 py-3 text-sm font-semibold text-blue-100 transition hover:bg-white/10 hover:text-white">{item.label}<ChevronRight size={15} aria-hidden="true" /></Link>)}</nav>
      <div className="mt-auto rounded-2xl border border-white/10 bg-white/5 p-4"><p className="text-sm font-bold">{profile?.full_name || profile?.email || "Account"}</p><p className="mt-1 text-xs text-blue-200/70">{profile?.is_master_admin ? "Master Admin" : role}</p><button onClick={logout} className="mt-4 inline-flex items-center gap-2 text-sm font-bold text-blue-100 hover:text-white"><LogOut size={16} /> Sign out</button></div>
    </aside>
    <div className="lg:pl-72">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-white/90 backdrop-blur"><div className="flex items-center justify-between px-5 py-4 sm:px-8"><button className="rounded-xl p-2 text-ink lg:hidden" onClick={() => setOpen((value) => !value)} aria-label={open ? "Close dashboard navigation" : "Open dashboard navigation"} aria-expanded={open}>{open ? <X /> : <Menu />}</button><div className="hidden lg:block"><p className="text-xs font-bold uppercase tracking-[0.18em] text-electric">{eyebrow || labels[role]}</p><h1 className="mt-1 text-2xl font-black tracking-tight">{title}</h1></div><Link to="/notifications/" className="rounded-xl p-2 text-slate-500 hover:bg-mist" aria-label="Open notifications"><Bell size={20} /></Link></div></header>
      {open && <div className="border-b border-line bg-white px-5 py-4 lg:hidden"><p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-electric">{labels[role]}</p>{navItems.map((item) => <Link onClick={() => setOpen(false)} key={item.href} to={item.href} className="block rounded-xl px-3 py-3 text-sm font-semibold hover:bg-mist">{item.label}</Link>)}<button onClick={logout} className="mt-3 inline-flex items-center gap-2 px-3 py-3 text-sm font-bold text-red-700"><LogOut size={16} /> Sign out</button></div>}
      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-10"><div className="mb-8 lg:hidden"><p className="text-xs font-bold uppercase tracking-[0.18em] text-electric">{eyebrow || labels[role]}</p><h1 className="mt-1 text-3xl font-black tracking-tight">{title}</h1></div>{children}</main>
    </div>
  </div>;
}

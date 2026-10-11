import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

export function BrandLogo({ href = "/" }) {
  return <Link to={href} className="inline-flex items-center gap-2 text-lg font-extrabold tracking-tight text-ink" aria-label="EventSphere home"><span className="grid h-9 w-9 place-items-center rounded-xl bg-electric text-white shadow-lg shadow-electric/20"><Sparkles size={18} aria-hidden="true" /></span><span>Event<span className="text-electric">Sphere</span></span></Link>;
}

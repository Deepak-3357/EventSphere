import { CalendarDays, MapPin, Users } from "lucide-react";
import { Link } from "react-router-dom";

const fallbackImage = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 480'%3E%3Crect width='800' height='480' fill='%23071a33'/%3E%3Ccircle cx='680' cy='70' r='180' fill='%23315efb' fill-opacity='.45'/%3E%3Cpath d='M0 400c140-100 250-90 380-20s230 60 420-100v200H0z' fill='%232b4ed3' fill-opacity='.6'/%3E%3Ctext x='48' y='110' fill='white' font-size='34' font-family='Arial' font-weight='700'%3EEVENTSPHERE%3C/text%3E%3C/svg%3E";

function dateLabel(value) {
  if (!value) return "Date to be announced";
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

export function EventCard({ event }) {
  const image = event.image_url || fallbackImage;
  return <article className="group overflow-hidden rounded-3xl border border-line bg-white shadow-soft transition duration-300 hover:-translate-y-1 hover:shadow-xl">
    <Link to={`/events/detail.html?id=${encodeURIComponent(event.id)}`} className="block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-electric" aria-label={`View ${event.title}`}>
      <div className="relative aspect-[16/9] overflow-hidden bg-ink"><img className="h-full w-full object-cover transition duration-500 group-hover:scale-105" src={image} alt="" onError={(eventTarget) => { eventTarget.currentTarget.src = fallbackImage; }} /><span className="absolute left-4 top-4 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-ink">{event.category?.name || "Campus event"}</span></div>
      <div className="space-y-4 p-5"><div><h3 className="line-clamp-2 text-xl font-bold leading-tight text-ink">{event.title}</h3><p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500">{event.description || "Discover a new campus experience with the EventSphere community."}</p></div><div className="space-y-2 text-sm text-slate-600"><p className="flex items-center gap-2"><CalendarDays size={16} className="text-electric" aria-hidden="true" />{dateLabel(event.event_date)} · {event.start_time?.slice(0, 5) || "Time TBA"}</p><p className="flex items-center gap-2"><MapPin size={16} className="text-electric" aria-hidden="true" />{event.venue?.name || "Venue to be announced"}</p><p className="flex items-center gap-2"><Users size={16} className="text-electric" aria-hidden="true" />{event.available_seats ?? event.capacity ?? ""} spots available</p></div></div>
    </Link>
  </article>;
}

import { EventCard } from "./EventCard.jsx";

export function EventGrid({ events }) {
  return <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">{events.map((event) => <EventCard key={event.id} event={event} />)}</div>;
}

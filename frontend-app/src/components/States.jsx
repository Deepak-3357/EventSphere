export function LoadingState() {
  return <div className="grid gap-6 md:grid-cols-3" aria-label="Loading events" data-testid="loading-state">{[1, 2, 3].map((item) => <div key={item} className="h-96 animate-pulse rounded-3xl bg-slate-100" />)}</div>;
}

export function ErrorState({ message, onRetry }) {
  return <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-center" role="alert" data-testid="error-state"><h3 className="font-bold text-red-900">Events are unavailable right now</h3><p className="mt-2 text-sm text-red-700">{message}</p>{onRetry && <button onClick={onRetry} className="mt-5 rounded-full bg-red-900 px-5 py-2 text-sm font-bold text-white">Try again</button>}</div>;
}

export function EmptyState() {
  return <div className="rounded-3xl border border-dashed border-line bg-white p-12 text-center" data-testid="empty-state"><h3 className="text-xl font-bold text-ink">Nothing on the calendar yet</h3><p className="mx-auto mt-2 max-w-md text-slate-500">New campus experiences will appear here as soon as they are published.</p></div>;
}

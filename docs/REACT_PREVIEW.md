# React preview deployment

Deploy `frontend-app/` as a separate Render Static Site:

- Root directory: `frontend-app`
- Build command: `npm ci && npm run build`
- Publish directory: `dist`
- Optional build environment variable: `VITE_API_BASE_URL=https://eventspherebackend-azkp.onrender.com`

The React API client already defaults non-local hosts to the deployed EventSphere backend and uses `http://127.0.0.1:5000` for local development. The build variable is recommended for an explicit preview configuration and must contain only the public API origin.

Because the app uses client-side routes, configure the static host to serve `dist/index.html` for these preview paths:

`/`, `/events/*`, `/student/*`, `/organizer/*`, `/admin/*`, `/login/*`, `/register/*`, `/auth/callback/*`.

Do not expose database credentials, service-role keys, signing secrets, or encryption keys as Vite variables. The browser receives only the Supabase URL and publishable key through the existing public configuration endpoint.

The backend keeps the existing `FRONTEND_ORIGIN` setting and always allows the existing production frontend origin. After Render creates the preview, add its exact origin to the comma-delimited `FRONTEND_ALLOWED_ORIGINS` environment variable, for example:

```text
FRONTEND_ORIGIN=https://eventsphere-395t.onrender.com
FRONTEND_ALLOWED_ORIGINS=https://preview.example.com
```

Only exact HTTP(S) origins are accepted; wildcards, paths, query strings, and substring matches are rejected. Supabase Auth must allow the preview origin and `/auth/callback/` as a redirect URL when Google OAuth is enabled.

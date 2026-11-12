# Unicorn frontend

The web app for [Unicorn](../README.md): React 19, TypeScript, Vite, Tailwind CSS 4, Recharts, React Router and TanStack Query.

## Run it

You need Node 22.12 or later (Vite 8's minimum; Node 20 is end-of-life on Vercel). Vercel builds with Node 24.

```bash
npm install
npm run dev
```

This serves the app at http://localhost:5173 and proxies `/api` to the backend at `http://127.0.0.1:8000`, so start the backend first (see the [main README](../README.md#local-development)). To point at a backend on another port, set `API_PROXY`, e.g. `API_PROXY=http://127.0.0.1:8001 npm run dev`.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run dev` | Dev server with hot reload |
| `npm run build` | Type-check (`tsc -b`), then build to `dist/` |
| `npm run lint` | Lint with Oxlint |
| `npm test` | Run the unit tests with Vitest |
| `npm run preview` | Serve the production build locally |

## Layout

```
src/
  main.tsx        entry point: theme, query client
  App.tsx         routes
  api/            fetch client, TanStack Query hooks, response types
  components/     layout, charts, run list, shoe split editor, shared UI
  lib/format.ts   formatting helpers and saved preferences
  pages/          Dashboard, Runs, RunDetail, Shoes, Fitness, Training, Records, Settings, Login
```

## Deployment

Vercel builds this folder as the `frontend` service defined in the root [`vercel.json`](../vercel.json). Every path that isn't `/api/*` is served `index.html`, so client-side routes work on reload.

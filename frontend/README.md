# TalentScout HR — React frontend

TypeScript + Vite UI for the FastAPI backend.

## Development

```bash
npm install
npm run dev
```

Runs at http://127.0.0.1:5173 and proxies `/api/*` to http://127.0.0.1:8000 (start Uvicorn from the repo root first).

## Production build

```bash
npm run build
```

Output goes to `dist/`. When that folder exists, `uvicorn app.main:app` serves the built app at http://127.0.0.1:8000.

## Layout

- `src/api/` — fetch helpers for backend routes
- `src/components/` — chat workspace and context rail
- `src/types/` — API response types

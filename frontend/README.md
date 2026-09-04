# SanadAI — Frontend

A React + Vite + Tailwind frontend for the SanadAI proposal co-pilot, talking to
the FastAPI backend in `../src/api`.

## Prerequisites

- Node.js 18+ (`node --version`). Install on Windows with
  `winget install OpenJS.NodeJS.LTS`, then open a fresh terminal.

## Run

```bash
# 1. Start the backend API (from the repo root, with the Python venv active)
uvicorn src.api.main:app --reload      # http://127.0.0.1:8000

# 2. Start the frontend (from this folder)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

The API base URL defaults to `http://127.0.0.1:8000`. Override it with a
`.env` file in this folder:

```
VITE_API_URL=http://127.0.0.1:8000
```

If the API isn't running, the dashboard falls back to sample data so you can
still see the layout.

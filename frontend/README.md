# Mira Web Frontend

Mira's web frontend is built with React, TypeScript, and Vite. It connects to the FastAPI backend to visualize roadmaps as vertical level progressions and manage daily tasks.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

The frontend will start at `http://localhost:3000` and proxy API calls to `http://127.0.0.1:8000`.

## Scripts

- `npm run dev`: Start local development server with HMR
- `npm run build`: Type-check with `tsc` and produce production build in `dist/`
- `npm run preview`: Locally preview production build

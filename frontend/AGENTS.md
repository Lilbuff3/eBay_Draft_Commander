<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# frontend

## Purpose
React 18 + TypeScript + Vite PWA. Tab-based SPA with real-time Socket.IO sync, Zustand state, and mobile-first responsive design.

## Key Files

| File | Description |
|------|-------------|
| `package.json` | Dependencies — React 18, Vite, Tailwind 4, Radix UI, Zustand, Socket.IO, dnd-kit |
| `vite.config.ts` | Build config — base `/app/`, `/api` proxy to Flask 5000, PWA manifest, path alias `@/` |
| `tsconfig.json` | TypeScript config — strict mode, `@/*` → `src/*` path alias |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | Application source (see `src/AGENTS.md`) |
| `public/` | Static assets — favicon, manifest.json, offline.html, PWA icons |

## For AI Agents

### Working In This Directory
- Dev server: `npm run dev` (port 5175, proxies `/api` to Flask 5000)
- Build: `npm run build` → outputs to `../static/app/`
- Tests: `npm run test` (Vitest + jsdom + @testing-library/react)
- Mobile access: `http://TUF:5175/` (hostname, not IP, for HMR stability)
- HMR uses `hmr: true` (auto-detect) — never hardcode IPs
- Tailwind 4 via `@tailwindcss/vite` plugin (not PostCSS)
- See CLAUDE.md for architecture patterns, gotchas, and port details

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

# ReplaysAI — Frontend

Vite + React 19 + TypeScript single-page app for ReplaysAI. See the [root README](../README.md) for
full architecture, system design, and tradeoffs.

## Stack
- **React 19 + TypeScript + Vite** — SPA build.
- **React Router 7** — a tabbed `Feed` shell (`/feed`, `/season`, `/reels`, `/extras`) plus dedicated
  routes `/dream-team`, `/reel/:gameId`, `/game/:id`, `/onboarding`.
- **TanStack Query** — server state; query keys derive from the fan's picks so caching is per-fan.
- **localStorage** — the entire anonymous fan profile (teams, players, picks, rosters). No auth.
- **Browser `speechSynthesis` / `SpeechRecognition`** — voiced reels + interrupt-and-ask.
- **html-to-image** — shareable Dream Team result card. **hls.js** — ESPN HLS clip playback.

## Develop

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api → http://127.0.0.1:8001
npm run build      # tsc -b + vite build
npm run lint       # eslint
```

Set `VITE_API_BASE_URL` only if the API is not same-origin (empty by default; dev uses the Vite proxy).

## Key files
- `pages/Landing.tsx` — canvas broadcast hero with the four named agents.
- `pages/Feed.tsx` — dashboard + Season/Reels/Extras tabs; all panels read the localStorage profile.
- `pages/DreamTeam.tsx` — roster builder → Monte-Carlo result card.
- `pages/ReelStudio.tsx` — voiced reel player with overlays + interrupt-and-ask.
- `components/ReelPlayer.tsx` — TTS-narrated clip player with audio ducking.
- `hooks/useUser.ts` — anonymous identity + favorite teams/players in localStorage.

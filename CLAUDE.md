# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm start              # Dev server at http://localhost:4200
npm run build          # Production build → dist/scoreboard-app/browser/
npm run build:ssr      # Build with SSR support
npm run dev:ssr        # SSR dev server
npm run serve:ssr      # Serve the built SSR bundle (node dist/scoreboard-app/server/main.js)
npm test               # Karma/Jasmine unit tests
npm run prerender      # Prerender static routes for SEO
```

Deploy to Firebase Hosting:
```bash
firebase deploy
```

## Architecture

**Angular 16 SPA** with optional SSR via `@nguniversal/express-engine`. The app is also wrapped as a mobile app via Capacitor (`capacitor.config.ts` → app ID `com.ModelAI.app`).

**Primary feature** is the `ScoreboardComponent` (`src/app/scoreboard/`) — a sports score predictor. The user selects a sport, two teams, and optional pitcher/goalie, then clicks to run `runSimulation()`. Each sport has its own statistical model hardcoded in the switch block; results open in `ScoreboardPopupComponent` (Angular Material dialog).

**Data flow**: All stat/team data is CSV files in `src/assets/`. The component loads them via `HttpClient.get(..., { responseType: 'text' })` and parses them manually (split on `\n`/`,`). There is no backend — the Angular app is purely client-side at runtime.

**Supported sports and their asset files:**
- NFL: `NFL-Stats.csv`, `NFL-Teams.csv`, `NFL-Spreads.csv`
- NBA: `NBA-Stats.csv`, `NBA-Teams.csv`, `NBA-Spreads.csv`
- MLB: `MLB-Stats.csv`, `MLB-Teams.csv`, `MLB-Pitchers.csv`, `MLB-Hitters.csv`, `MLB-Lineups.csv`, `MLB-Ballparks.csv`, `MLB-Player-Props.csv`
- NHL: `NHL-Stats.csv`, `NHL-Teams.csv`, `NHL-Goalies.csv`, `NHL-Odds.csv`
- NCAAF: `NCAAF-Stats.csv`, `NCAAF-Teams.csv`
- NCAAM: `NCAAM-Stats.csv`, `NCAAM-Teams.csv`, `NCAAM-Spreads.csv`
- NCAA-Baseball: `NCAA-Baseball-Stats.csv`, `NCAA-Baseball-Teams.csv`
- EPL/Soccer: `EPL-Stats.csv`, `EPL-Teams.csv`, `Soccer-Stats.csv`

**Team colors** are defined in `src/app/team-colors.ts` as a lookup map used for dynamic UI styling.

**Routes** (`app-routing.module.ts`):
- `/` → `HomeComponent` — static landing page with hardcoded top picks/props
- `/scoreboard` → `ScoreboardComponent` — main prediction tool
- `/soccer-scoreboard` → `SoccerScoreboardComponent`
- `/results` → `ResultsComponent` — reads past predictions from Firestore
- `/about` → `AboutComponent`
- `/{sport}-predictions` → SEO static pages under `src/app/seo-pages/`

**Firebase** (`@angular/fire` compat API): Firestore is wired up in `app.module.ts` and used in `ScoreboardComponent.savePrediction()` (currently commented out before deploy) and `ResultsComponent`.

**File naming convention**: Files ending in `-Jacks_Laptop` (e.g., `styles-Jacks_Laptop.css`, `app.module-Jacks_Laptop.ts`) are machine-specific alternates — do not modify or deploy these.

**Python scripts** (`Data.py`, `fetch_nba_stats.py`, `src/app/API/API.py`) are standalone data-fetching/preprocessing utilities that generate the CSV files; they are not part of the Angular build.

**SSR prerender routes** are defined in `angular.json` under the `prerender` architect target — these are the `/sport-predictions` SEO pages.

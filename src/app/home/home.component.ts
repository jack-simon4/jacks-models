import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../environments/environment';

interface UnifiedPick {
  rank: number;
  sport: string;
  league?: string;
  matchup: string;
  pick: string;
  winProb: number;
  confidence: string;
  predictedScore: string;
  odds?: string;
  gameTime?: string;
}

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {

  topPicks: UnifiedPick[] = [];
  topPicksLoading = true;

  topProps: { rank: number; name: string; hitPercent: string; hrPercent: string; xBases: string }[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.loadAllPicks();
    this.loadTopProps();
  }

  private normalizeMlb(p: any): UnifiedPick {
    return {
      rank: 0,
      sport: 'MLB',
      matchup: p.matchup ?? `${p.awayTeam} @ ${p.homeTeam}`,
      pick: p.pick,
      winProb: p.winProb ?? 0,
      confidence: p.confidence ?? '',
      predictedScore: p.predictedScore ?? '',
      odds: p.odds,
      gameTime: p.gameTime,
    };
  }

  private normalizeFootball(p: any, sport: 'NFL' | 'NCAAF'): UnifiedPick | null {
    if (!p.confidence) return null;
    const aSc = p.awayPredicted ?? 0;
    const hSc = p.homePredicted ?? 0;
    const aAbbr = (p.awayTeam ?? '').slice(0, 4).toUpperCase();
    const hAbbr = (p.homeTeam ?? '').slice(0, 4).toUpperCase();
    return {
      rank: 0,
      sport,
      matchup: `${p.awayTeam} @ ${p.homeTeam}`,
      pick: p.pick,
      winProb: p.winProb ?? 0,
      confidence: p.confidence,
      predictedScore: `${aAbbr} ${aSc} – ${hAbbr} ${hSc}`,
      gameTime: p.gameTime,
    };
  }

  private normalizeSoccer(g: any): UnifiedPick | null {
    const wp = g.homeWinProb ?? 0.5;
    const edge = Math.abs(wp - 0.5);
    if (edge < 0.05) return null;

    let confidence = '';
    if      (edge >= 0.18) confidence = 'Elite';
    else if (edge >= 0.10) confidence = 'Strong';
    else if (edge >= 0.05) confidence = 'Lean';

    const pickIsHome = wp >= 0.5;
    const pick       = pickIsHome ? g.homeTeam : g.awayTeam;
    const pickWp     = pickIsHome ? wp : 1 - wp;
    const hPred      = (g.predictedHomeScore ?? 0) as number;
    const aPred      = (g.predictedAwayScore ?? 0) as number;
    const aAbbr      = (g.awayTeam ?? '').slice(0, 4).toUpperCase();
    const hAbbr      = (g.homeTeam ?? '').slice(0, 4).toUpperCase();

    return {
      rank: 0,
      sport: 'Soccer',
      league: g.league,
      matchup: `${g.awayTeam} @ ${g.homeTeam}`,
      pick,
      winProb: Math.round(pickWp * 1000) / 1000,
      confidence,
      predictedScore: `${aAbbr} ${aPred.toFixed(1)} – ${hAbbr} ${hPred.toFixed(1)}`,
      gameTime: g.gameTime,
    };
  }

  private loadAllPicks() {
    const now       = new Date();
    const todayStr  = now.toISOString().slice(0, 10);
    const weekAhead = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

    const mlb$ = this.http.get<any[]>(environment.topPicksUrl).pipe(
      map(picks => (picks ?? [])
        .filter(p => p.confidence)
        .map(p => this.normalizeMlb(p))),
      catchError(() => of([] as UnifiedPick[]))
    );

    const nfl$ = this.http.get<any[]>('assets/nfl-picks.json').pipe(
      map(picks => (picks ?? [])
        .filter(p => {
          if (!p.gameTime) return true;
          const gt = new Date(p.gameTime);
          return gt >= now && gt <= weekAhead;
        })
        .map(p => this.normalizeFootball(p, 'NFL'))
        .filter((p): p is UnifiedPick => p !== null)),
      catchError(() => of([] as UnifiedPick[]))
    );

    const ncaaf$ = this.http.get<any[]>('assets/ncaaf-picks.json').pipe(
      map(picks => (picks ?? [])
        .filter(p => {
          if (!p.gameTime) return true;
          const gt = new Date(p.gameTime);
          return gt >= now && gt <= weekAhead;
        })
        .map(p => this.normalizeFootball(p, 'NCAAF'))
        .filter((p): p is UnifiedPick => p !== null)),
      catchError(() => of([] as UnifiedPick[]))
    );

    const soccer$ = this.http.get<any>('assets/soccer-today.json').pipe(
      map(data => ((data?.upcoming ?? []) as any[])
        .filter((g: any) => g.gameDate === todayStr)
        .map((g: any) => this.normalizeSoccer(g))
        .filter((p): p is UnifiedPick => p !== null)),
      catchError(() => of([] as UnifiedPick[]))
    );

    forkJoin([mlb$, nfl$, ncaaf$, soccer$]).subscribe(([mlb, nfl, ncaaf, soccer]) => {
      const all = [...mlb, ...nfl, ...ncaaf, ...soccer];
      all.sort((a, b) => b.winProb - a.winProb);
      this.topPicks = all.slice(0, 5).map((p, i) => ({ ...p, rank: i + 1 }));
      this.topPicksLoading = false;
    });
  }

  private loadTopProps() {
    this.http.get(environment.mlbPlayerPropsUrl, { responseType: 'text' }).subscribe({
      next: (csv) => {
        const lines = csv.trim().split('\n');
        const rows = lines.slice(1)
          .map(line => {
            const parts = line.split(',');
            return {
              name:      (parts[0] ?? '').trim(),
              homerPct:  parseFloat(parts[1] ?? '0'),
              hitPct:    parseFloat(parts[2] ?? '0'),
              xBases:    parseFloat(parts[3] ?? '0'),
            };
          })
          .filter(r => r.name && !isNaN(r.xBases));

        this.topProps = rows.slice(0, 5).map((r, i) => ({
          rank:       i + 1,
          name:       r.name,
          hitPercent: Math.round(r.hitPct * 100) + '%',
          hrPercent:  Math.round(r.homerPct * 100) + '%',
          xBases:     r.xBases.toFixed(2),
        }));
      },
      error: () => {}
    });
  }
}

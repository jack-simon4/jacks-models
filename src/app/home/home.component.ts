import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Meta, Title } from '@angular/platform-browser';
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

  nflProps: { rank: number; name: string; team: string; opponent: string; position: string; projYards: number; projTDs: number; statLabel: string; matchup: string }[] = [];
  private allNflProps: typeof this.nflProps = [];
  nflPositionFilter: 'ALL' | 'QB' | 'RB' | 'WR' | 'TE' = 'ALL';

  constructor(private http: HttpClient, private titleService: Title, private metaService: Meta) {}

  ngOnInit() {
    this.titleService.setTitle("Jack's Models | Free Sports Prediction Models");
    this.metaService.updateTag({ name: 'description', content: "Free stat-driven sports predictions for NFL, NBA, MLB, NHL, NCAAF, NCAAM and Soccer. Run any matchup instantly." });
    this.loadAllPicks();
    this.loadNFLProps();
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
    const aSc = p.predictedAwayScore ?? p.awayPredicted ?? 0;
    const hSc = p.predictedHomeScore ?? p.homePredicted ?? 0;
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

  private normalizeNHL(p: any): UnifiedPick | null {
    if (!p.confidence) return null;
    const aSc = (p.predictedAwayScore ?? 0) as number;
    const hSc = (p.predictedHomeScore ?? 0) as number;
    return {
      rank: 0,
      sport: 'NHL',
      matchup: `${p.awayTeam} @ ${p.homeTeam}`,
      pick: p.pick,
      winProb: p.winProb ?? 0,
      confidence: p.confidence,
      predictedScore: `${aSc.toFixed(1)} – ${hSc.toFixed(1)}`,
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
    const now      = new Date();
    const todayStr = now.toISOString().slice(0, 10);

    const mlb$ = this.http.get<any[]>(environment.topPicksUrl).pipe(
      map(picks => (picks ?? [])
        .filter(p => p.confidence)
        .map(p => this.normalizeMlb(p))),
      catchError(() => of([] as UnifiedPick[]))
    );

    const oneDayAhead = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    const nhl$ = this.http.get<any[]>('assets/nhl-picks.json').pipe(
      map(picks => (picks ?? [])
        .filter(p => {
          if (!p.gameTime) return false;
          const gt = new Date(p.gameTime);
          return gt >= now && gt <= oneDayAhead;
        })
        .map(p => this.normalizeNHL(p))
        .filter((p): p is UnifiedPick => p !== null)),
      catchError(() => of([] as UnifiedPick[]))
    );

    const nfl$ = this.http.get<any[]>('assets/nfl-picks.json').pipe(
      map(picks => (picks ?? [])
        .filter(p => {
          if (!p.gameTime) return false;
          const gt = new Date(p.gameTime);
          return gt >= now && gt <= oneDayAhead;
        })
        .map(p => this.normalizeFootball(p, 'NFL'))
        .filter((p): p is UnifiedPick => p !== null)),
      catchError(() => of([] as UnifiedPick[]))
    );

    const ncaaf$ = this.http.get<any[]>('assets/ncaaf-picks.json').pipe(
      map(picks => (picks ?? [])
        .filter(p => {
          if (!p.gameTime) return false;
          const gt = new Date(p.gameTime);
          return gt >= now && gt <= oneDayAhead;
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

    forkJoin([mlb$, nfl$, ncaaf$, soccer$, nhl$]).subscribe(([mlb, nfl, ncaaf, soccer, nhl]) => {
      const all = [...mlb, ...nfl, ...ncaaf, ...soccer, ...nhl];
      all.sort((a, b) => b.winProb - a.winProb);
      this.topPicks = all.slice(0, 5).map((p, i) => ({ ...p, rank: i + 1 }));
      this.topPicksLoading = false;
    });
  }

  private loadNFLProps() {
    this.http.get<any[]>('assets/nfl-player-props.json').subscribe({
      next: (props) => {
        this.allNflProps = (props ?? []).map((p, i) => ({
          rank:      i + 1,
          name:      p.name,
          team:      p.team,
          opponent:  p.opponent,
          position:  p.position,
          projYards: p.projYards,
          projTDs:   p.projTDs,
          statLabel: p.statLabel,
          matchup:   p.matchup,
        }));
        this.applyNflPositionFilter();
      },
      error: () => {}
    });
  }

  setNflPositionFilter(pos: typeof this.nflPositionFilter) {
    this.nflPositionFilter = pos;
    this.applyNflPositionFilter();
  }

  private applyNflPositionFilter() {
    const filtered = this.nflPositionFilter === 'ALL'
      ? this.allNflProps
      : this.allNflProps.filter(p => p.position === this.nflPositionFilter);
    this.nflProps = filtered.slice(0, 5).map((p, i) => ({ ...p, rank: i + 1 }));
  }
}

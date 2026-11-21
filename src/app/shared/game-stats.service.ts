import { Injectable } from '@angular/core';
import { AngularFirestore } from '@angular/fire/compat/firestore';
import { Observable } from 'rxjs';
import { map, shareReplay } from 'rxjs/operators';

export interface Game {
  id: string;
  sport: string;
  homeTeam: string;
  awayTeam: string;
  predictedHomeScore: number;
  predictedAwayScore: number;
  actualHomeScore: number | null;
  actualAwayScore: number | null;
  pick?: string;
  winProb?: number;
  confidence?: string;
  /** Normalized: positive = home is favourite. Absent for sports with no line (NHL, MLB). */
  vegasSpread?: number | null;
  spreadEdge?: number | null;
  gameTime?: string;
  timestamp?: Date;
}

export interface SportStat {
  sport: string;
  icon: string;
  games: number;       // completed games tracked
  mlWins: number;
  mlLosses: number;
  mlPct: number;
  atsWins: number;
  atsLosses: number;
  atsPushes: number;
  atsPct: number;      // atsWins / (atsWins + atsLosses), ignoring pushes
  atsTot: number;      // atsWins + atsLosses + atsPushes
  units: number;       // flat-bet at −110: +1.0 win, −1.1 loss, 0 push
}

const ICONS: Record<string, string> = {
  NFL: '🏈', NBA: '🏀', MLB: '⚾', NHL: '🏒',
  NCAAF: '🏈', NCAAM: '🏀', Soccer: '⚽', 'College Baseball': '⚾',
};

@Injectable({ providedIn: 'root' })
export class GameStatsService {

  /** All games from Firestore (including pending), shared across subscribers. */
  readonly games$: Observable<Game[]>;

  /** Aggregated stats per sport, computed from completed games only. */
  readonly sportStats$: Observable<Map<string, SportStat>>;

  constructor(private firestore: AngularFirestore) {
    this.games$ = this.firestore
      .collection('games', ref => ref.orderBy('timestamp', 'desc').limit(3000))
      .snapshotChanges()
      .pipe(
        map(snaps => snaps.map(snap => {
          const data = snap.payload.doc.data() as any;
          data.id = snap.payload.doc.id;
          if (data.timestamp?.seconds) {
            data.timestamp = new Date(data.timestamp.seconds * 1000);
          }
          return data as Game;
        })),
        shareReplay(1)
      );

    this.sportStats$ = this.games$.pipe(
      map(games => this.aggregateStats(
        games.filter(g => g.actualHomeScore != null && g.actualAwayScore != null)
      )),
      shareReplay(1)
    );
  }

  mlCorrect(game: Game): boolean {
    if (game.actualHomeScore == null || game.actualAwayScore == null) return false;
    if (game.actualHomeScore === game.actualAwayScore) return false;
    const predHome = game.predictedHomeScore >= game.predictedAwayScore;
    const actHome  = game.actualHomeScore    >  game.actualAwayScore;
    return predHome === actHome;
  }

  /**
   * ATS result for the model's moneyline pick.
   * vegasSpread convention: positive = home is favoured.
   * Returns null when spread data is unavailable.
   */
  atsResult(game: Game): 'win' | 'loss' | 'push' | null {
    if (game.actualHomeScore == null || game.actualAwayScore == null) return null;
    if (game.vegasSpread == null) return null;
    if (!game.pick) return null;

    const margin        = game.actualHomeScore - game.actualAwayScore;
    const coverMargin   = margin - game.vegasSpread;   // >0 means home covered
    if (coverMargin === 0) return 'push';

    const homeCovered = coverMargin > 0;
    const pickIsHome  = game.pick === game.homeTeam;
    return (pickIsHome === homeCovered) ? 'win' : 'loss';
  }

  /** Flat-bet units at standard −110 vig. */
  atsUnits(game: Game): number | null {
    const r = this.atsResult(game);
    if (r === null) return null;
    if (r === 'win')  return 1.0;
    if (r === 'loss') return -1.1;
    return 0;
  }

  private aggregateStats(completed: Game[]): Map<string, SportStat> {
    const result = new Map<string, SportStat>();

    for (const g of completed) {
      if (!result.has(g.sport)) {
        result.set(g.sport, {
          sport: g.sport, icon: ICONS[g.sport] ?? '🏆',
          games: 0, mlWins: 0, mlLosses: 0, mlPct: 0,
          atsWins: 0, atsLosses: 0, atsPushes: 0, atsPct: 0, atsTot: 0,
          units: 0,
        });
      }
      const s = result.get(g.sport)!;
      s.games++;
      if (this.mlCorrect(g)) s.mlWins++; else s.mlLosses++;

      const ats = this.atsResult(g);
      if (ats === 'win')  { s.atsWins++;   s.units = +(s.units + 1.0).toFixed(1); }
      if (ats === 'loss') { s.atsLosses++; s.units = +(s.units - 1.1).toFixed(1); }
      if (ats === 'push') { s.atsPushes++; }
    }

    for (const s of result.values()) {
      s.mlPct  = s.games > 0 ? Math.round(s.mlWins / s.games * 100) : 0;
      s.atsTot = s.atsWins + s.atsLosses + s.atsPushes;
      const atsDec = s.atsWins + s.atsLosses;
      s.atsPct = atsDec > 0 ? Math.round(s.atsWins / atsDec * 100) : 0;
    }

    return result;
  }
}

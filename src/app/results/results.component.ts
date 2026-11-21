import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { GameStatsService, Game, SportStat } from '../shared/game-stats.service';

const PAGE_SIZE = 8;

/** Sports shown in the league cards. Order controls display order. */
const TRACKED_SPORTS: { sport: string; icon: string }[] = [
  { sport: 'NFL',              icon: '🏈' },
  { sport: 'NBA',              icon: '🏀' },
  { sport: 'MLB',              icon: '⚾' },
  { sport: 'NHL',              icon: '🏒' },
  { sport: 'NCAAF',            icon: '🏈' },
  { sport: 'NCAAM',            icon: '🏀' },
  { sport: 'College Baseball', icon: '⚾' },
  { sport: 'Soccer',           icon: '⚽' },
];

@Component({
  selector: 'app-results',
  templateUrl: './results.component.html',
  styleUrls: ['./results.component.css']
})
export class ResultsComponent implements OnInit, OnDestroy {

  games: Game[] = [];
  loading = true;
  selectedSport = 'All';
  currentPage = 0;
  leagueStats: SportStat[] = [];

  private subs = new Subscription();

  constructor(private gameStats: GameStatsService) {}

  ngOnInit(): void {
    this.subs.add(this.gameStats.games$.subscribe(games => {
      this.games = games;
      this.loading = false;
    }));
    this.subs.add(this.gameStats.sportStats$.subscribe(map => {
      this.leagueStats = TRACKED_SPORTS.map(({ sport, icon }) =>
        map.get(sport) ?? {
          sport, icon,
          games: 0, mlWins: 0, mlLosses: 0, mlPct: 0,
          atsWins: 0, atsLosses: 0, atsPushes: 0, atsPct: 0, atsTot: 0, units: 0,
        }
      );
    }));
  }

  ngOnDestroy(): void { this.subs.unsubscribe(); }

  get availableSports(): string[] {
    const sports = [...new Set(
      this.games
        .filter(g => g.actualHomeScore != null)
        .map(g => g.sport)
        .filter(Boolean)
    )].sort();
    return ['All', ...sports];
  }

  get recordedGames(): Game[] {
    return this.games
      .filter(g => g.actualHomeScore != null && g.actualAwayScore != null)
      .sort((a, b) => {
        const ta = a.gameTime ? new Date(a.gameTime).getTime() : (a.timestamp as any)?.getTime() ?? 0;
        const tb = b.gameTime ? new Date(b.gameTime).getTime() : (b.timestamp as any)?.getTime() ?? 0;
        return tb - ta;
      });
  }

  get filteredGames(): Game[] {
    if (this.selectedSport === 'All') return this.recordedGames;
    return this.recordedGames.filter(g => g.sport === this.selectedSport);
  }

  get pagedGames(): Game[] {
    const start = this.currentPage * PAGE_SIZE;
    return this.filteredGames.slice(start, start + PAGE_SIZE);
  }

  get totalPages(): number { return Math.ceil(this.filteredGames.length / PAGE_SIZE); }

  get pageWindow(): number[] {
    const size = 10;
    let start = Math.max(0, this.currentPage - Math.floor(size / 2));
    const end   = Math.min(this.totalPages - 1, start + size - 1);
    start = Math.max(0, end - size + 1);
    const pages: number[] = [];
    for (let i = start; i <= end; i++) pages.push(i);
    return pages;
  }

  get totalCorrect(): number { return this.filteredGames.filter(g => this.isPredictionCorrect(g)).length; }

  get overallWinRate(): string {
    const n = this.filteredGames.length;
    if (n === 0) return '—';
    return Math.round(this.totalCorrect / n * 100) + '%';
  }

  get totalAtsWins():   number { return this.filteredGames.filter(g => this.atsResult(g) === 'win').length; }
  get totalAtsLosses(): number { return this.filteredGames.filter(g => this.atsResult(g) === 'loss').length; }

  get totalUnits(): number {
    return +this.filteredGames.reduce((sum, g) => {
      const u = this.atsUnits(g);
      return u != null ? +(sum + u).toFixed(1) : sum;
    }, 0).toFixed(1);
  }

  get totalAtsPct(): string {
    const dec = this.totalAtsWins + this.totalAtsLosses;
    if (dec === 0) return '—';
    return Math.round(this.totalAtsWins / dec * 100) + '%';
  }

  get hasAtsData(): boolean { return this.totalAtsWins + this.totalAtsLosses > 0; }

  selectSport(sport: string) { this.selectedSport = sport; this.currentPage = 0; }
  goToPage(page: number)      { this.currentPage = page; }

  isPredictionCorrect(game: Game): boolean { return this.gameStats.mlCorrect(game); }

  predictedWinner(game: Game): string {
    return game.predictedHomeScore > game.predictedAwayScore ? game.homeTeam : game.awayTeam;
  }

  atsResult(game: Game) { return this.gameStats.atsResult(game); }
  atsUnits(game: Game)  { return this.gameStats.atsUnits(game); }
}

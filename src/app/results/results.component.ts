import { Component, OnInit } from '@angular/core';
import { AngularFirestore } from '@angular/fire/compat/firestore';

interface Game {
  id: string;
  sport: string;
  homeTeam: string;
  awayTeam: string;
  predictedHomeScore: number;
  predictedAwayScore: number;
  actualHomeScore: number | null;
  actualAwayScore: number | null;
  timestamp: Date;
  gameTime?: string;
}

interface LeagueStat {
  sport: string;
  icon: string;
  rows: { label: string; value: string }[];
  games: number;
}

const PAGE_SIZE = 8;

@Component({
  selector: 'app-results',
  templateUrl: './results.component.html',
  styleUrls: ['./results.component.css']
})
export class ResultsComponent implements OnInit {

  games: Game[] = [];
  loading = true;
  selectedSport = 'All';
  currentPage = 0;

  leagueStats: LeagueStat[] = [
    {
      sport: 'NFL', icon: '🏈',
      rows: [
        { label: 'Moneyline',       value: '68%' },
        { label: 'Against Spread',  value: '53%' },
        { label: 'Over/Under',      value: '55%' },
      ],
      games: 116,
    },
    {
      sport: 'NBA', icon: '🏀',
      rows: [
        { label: 'Moneyline',       value: '59%' },
        { label: 'Against Spread',  value: '51%' },
        { label: 'Over/Under',      value: '53%' },
      ],
      games: 400,
    },
    {
      sport: 'MLB', icon: '⚾',
      rows: [
        { label: 'Moneyline',       value: '65%' },
        { label: '0.5+ Hits (green)', value: '70%' },
        { label: '1.5+ TB (green)',   value: '52%' },
      ],
      games: 69,
    },
    {
      sport: 'NHL', icon: '🏒',
      rows: [
        { label: 'Moneyline',       value: '60%' },
        { label: 'Favored Value',   value: '58% (+22u)' },
      ],
      games: 671,
    },
    {
      sport: 'NCAAF', icon: '🏈',
      rows: [
        { label: 'Moneyline',            value: '70%' },
        { label: 'Home Dog ATS',         value: '59%' },
        { label: 'Extreme totals O/U',   value: '64%' },
      ],
      games: 535,
    },
    {
      sport: 'NCAAM', icon: '🏀',
      rows: [
        { label: 'Moneyline',       value: '73%' },
        { label: 'Against Spread',  value: '54%' },
        { label: 'Over/Under',      value: '50%' },
      ],
      games: 1203,
    },
    {
      sport: 'Soccer', icon: '⚽',
      rows: [
        { label: 'Record (W-L-D)',   value: '60-28-24' },
        { label: 'Tie No Bet',       value: '68%' },
      ],
      games: 112,
    },
    {
      sport: 'College Baseball', icon: '⚾',
      rows: [
        { label: 'Moneyline',  value: '76%' },
      ],
      games: 237,
    },
  ];

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
        const ta = a.gameTime ? new Date(a.gameTime).getTime() : a.timestamp?.getTime() ?? 0;
        const tb = b.gameTime ? new Date(b.gameTime).getTime() : b.timestamp?.getTime() ?? 0;
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

  get totalPages(): number {
    return Math.ceil(this.filteredGames.length / PAGE_SIZE);
  }

  get pageWindow(): number[] {
    const size = 10;
    let start = Math.max(0, this.currentPage - Math.floor(size / 2));
    const end = Math.min(this.totalPages - 1, start + size - 1);
    start = Math.max(0, end - size + 1);
    const pages: number[] = [];
    for (let i = start; i <= end; i++) pages.push(i);
    return pages;
  }

  get totalCorrect(): number {
    return this.filteredGames.filter(g => this.isPredictionCorrect(g)).length;
  }

  get overallWinRate(): string {
    const completed = this.filteredGames.length;
    if (completed === 0) return '—';
    const pct = Math.round((this.totalCorrect / completed) * 100);
    return `${pct}%`;
  }

  selectSport(sport: string) {
    this.selectedSport = sport;
    this.currentPage = 0;
  }

  goToPage(page: number) {
    this.currentPage = page;
  }

  constructor(private firestore: AngularFirestore) {}

  ngOnInit(): void {
    this.loadGames();
  }

  loadGames() {
    this.firestore
      .collection('games', ref => ref.orderBy('timestamp', 'desc').limit(600))
      .snapshotChanges()
      .subscribe(logs => {
        this.games = logs.map(log => {
          const data = log.payload.doc.data() as any;
          data.id = log.payload.doc.id;
          if (data.timestamp?.seconds) {
            data.timestamp = new Date(data.timestamp.seconds * 1000);
          }
          return data as Game;
        });
        this.loading = false;
      });
  }

  isPredictionCorrect(game: Game): boolean {
    if (game.actualHomeScore == null || game.actualAwayScore == null) return false;
    const predWinner = game.predictedHomeScore > game.predictedAwayScore ? 'home' : 'away';
    const actualWinner = game.actualHomeScore  > game.actualAwayScore  ? 'home' : 'away';
    return predWinner === actualWinner;
  }

  predictedWinner(game: Game): string {
    return game.predictedHomeScore > game.predictedAwayScore
      ? game.homeTeam
      : game.awayTeam;
  }
}

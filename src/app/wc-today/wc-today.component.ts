import { Component, OnInit, Inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Meta, Title } from '@angular/platform-browser';

interface WcMatch {
  matchId: number;
  round: string;
  homeTeam: string;
  awayTeam: string;
  predictedHomeScore: number;
  predictedAwayScore: number;
  homeWinProb: number;
  gameDate: string;
  gameTime: string;
  status: string;
  actualHomeScore: number | null;
  actualAwayScore: number | null;
}

interface WcTodayData {
  generated: string;
  today: string;
  upcoming: WcMatch[];
  recentResults: WcMatch[];
}

@Component({
  selector: 'app-wc-today',
  templateUrl: './wc-today.component.html',
  styleUrls: ['./wc-today.component.css']
})
export class WcTodayComponent implements OnInit {
  todayMatches: WcMatch[] = [];
  upcomingMatches: WcMatch[] = [];
  recentResults: WcMatch[] = [];
  loading = true;
  dateLabel = '';
  today = '';

  constructor(
    private http: HttpClient,
    private meta: Meta,
    private title: Title,
    @Inject(PLATFORM_ID) private platformId: Object
  ) {
    const now = new Date();
    this.today = now.toISOString().slice(0, 10);
    this.dateLabel = now.toLocaleDateString('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
    });

    this.title.setTitle(`World Cup Predictions Today — ${this.dateLabel} | Jack's Models`);
    this.meta.updateTag({ name: 'description', content: `2026 FIFA World Cup predictions from Jack's Models. Model-projected scores and win probabilities for today's World Cup matches — updated daily.` });
    this.meta.updateTag({ property: 'og:title',       content: `World Cup 2026 Predictions Today — ${this.dateLabel}` });
    this.meta.updateTag({ property: 'og:description', content: `Free 2026 World Cup picks for ${this.dateLabel}. Projected scores and win probabilities from Jack's data model.` });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/world-cup-predictions-today' });
    this.meta.updateTag({ name: 'twitter:title',       content: `World Cup Predictions Today — ${this.dateLabel}` });
    this.meta.updateTag({ name: 'twitter:description', content: `Today's 2026 World Cup picks with projected scores and win probabilities. Free at jacksmodels.com.` });
  }

  ngOnInit() {
    if (!isPlatformBrowser(this.platformId)) {
      this.loading = false;
      return;
    }
    this.http.get<WcTodayData>('assets/wc-today.json').subscribe({
      next: (data) => {
        if (data) {
          const all = data.upcoming || [];
          this.todayMatches    = all.filter(m => m.gameDate === this.today);
          this.upcomingMatches = all.filter(m => m.gameDate !== this.today);
          this.recentResults   = data.recentResults || [];
        }
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  formatTime(iso: string): string {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleTimeString('en-US', {
        hour: 'numeric', minute: '2-digit', timeZoneName: 'short', timeZone: 'America/New_York'
      });
    } catch { return ''; }
  }

  formatDate(dateStr: string): string {
    if (!dateStr) return '';
    try {
      const [y, m, d] = dateStr.split('-').map(Number);
      return new Date(y, m - 1, d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return dateStr; }
  }

  predictedWinner(m: WcMatch): string {
    if (m.predictedHomeScore > m.predictedAwayScore) return m.homeTeam;
    if (m.predictedAwayScore > m.predictedHomeScore) return m.awayTeam;
    return 'Draw';
  }

  modelCorrect(m: WcMatch): boolean {
    if (m.actualHomeScore === null || m.actualAwayScore === null) return false;
    const predWin = m.predictedHomeScore > m.predictedAwayScore ? 'home'
                  : m.predictedAwayScore > m.predictedHomeScore ? 'away' : 'draw';
    const actWin  = m.actualHomeScore  > m.actualAwayScore  ? 'home'
                  : m.actualAwayScore  > m.actualHomeScore  ? 'away' : 'draw';
    return predWin === actWin;
  }
}

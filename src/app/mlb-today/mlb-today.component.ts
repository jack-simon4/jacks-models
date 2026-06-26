import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Meta, Title } from '@angular/platform-browser';

interface Pick {
  rank: number;
  matchup: string;
  awayTeam: string;
  homeTeam: string;
  awayPitcher: string;
  homePitcher: string;
  pick: string;
  prediction: string;
  odds: string;
  winProb: number;
  confidence: string;
  predictedScore: string;
  predictedHomeScore: number;
  predictedAwayScore: number;
  gameTime: string;
}

@Component({
  selector: 'app-mlb-today',
  templateUrl: './mlb-today.component.html',
  styleUrls: ['./mlb-today.component.css']
})
export class MlbTodayComponent implements OnInit {
  picks: Pick[] = [];
  loading = true;
  dateLabel = '';

  constructor(private http: HttpClient, private meta: Meta, private title: Title) {
    const now = new Date();
    this.dateLabel = now.toLocaleDateString('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
    });

    this.title.setTitle(`MLB Predictions Today — ${this.dateLabel} | Jack's Models`);
    this.meta.updateTag({ name: 'description', content: `Today's MLB game predictions from Jack's Models. Model-projected scores, win probabilities, and top picks for every MLB game on ${this.dateLabel}.` });
    this.meta.updateTag({ property: 'og:title',       content: `MLB Predictions Today — ${this.dateLabel}` });
    this.meta.updateTag({ property: 'og:description', content: `Free MLB picks for ${this.dateLabel}. Starting pitchers, projected scores, and win probabilities from Jack's data model.` });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/mlb-predictions-today' });
    this.meta.updateTag({ name: 'twitter:title',       content: `MLB Predictions Today — ${this.dateLabel}` });
    this.meta.updateTag({ name: 'twitter:description', content: `Today's MLB picks with projected scores and win probabilities. Free at jacksmodels.com.` });
  }

  ngOnInit() {
    this.http.get<Pick[]>('assets/top-picks.json').subscribe({
      next: (data) => {
        this.picks = data || [];
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

  confidenceClass(conf: string): string {
    switch ((conf || '').toLowerCase()) {
      case 'elite':   return 'conf-elite';
      case 'high':    return 'conf-high';
      case 'medium':  return 'conf-medium';
      default:        return 'conf-low';
    }
  }
}

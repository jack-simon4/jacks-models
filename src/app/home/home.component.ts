import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

interface TopPick {
  rank: number;
  matchup: string;
  awayTeam: string;
  homeTeam: string;
  awayPitcher: string;
  homePitcher: string;
  pick: string;
  prediction: string;
  confidence: string;
  predictedScore: string;
  winProb: number;
}

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {

  topPicks: TopPick[] = [];
  topPicksLoading = true;

  topProps: { rank: number; name: string; hitPercent: string; hrPercent: string; xBases: string }[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.loadTopPicks();
    this.loadTopProps();
  }

  private loadTopPicks() {
    this.http.get<TopPick[]>('assets/top-picks.json').subscribe({
      next: (picks) => {
        this.topPicks = (picks || []).slice(0, 5);
        this.topPicksLoading = false;
      },
      error: () => {
        this.topPicksLoading = false;
      }
    });
  }

  private loadTopProps() {
    this.http.get('assets/MLB-Player-Props.csv', { responseType: 'text' }).subscribe({
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

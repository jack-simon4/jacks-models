import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {

  topPicks = [
    { rank: 1, matchup: 'Red Sox vs Yankees',       prediction: 'Yankees -144',      confidence: 'Elite'  },
    { rank: 2, matchup: 'Cal Poly vs West Virginia', prediction: 'West Virginia -1.5', confidence: 'Strong' },
    { rank: 3, matchup: 'Knicks vs Spurs',           prediction: 'Knicks +6.5',        confidence: 'Lean'   }
  ];

  topProps: { rank: number; name: string; hitPercent: string; hrPercent: string; xBases: string }[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.loadTopProps();
  }

  private loadTopProps() {
    this.http.get('assets/MLB-Player-Props.csv', { responseType: 'text' }).subscribe({
      next: (csv) => {
        const lines = csv.trim().split('\n');
        // Skip header row
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

        // Already sorted by xBases desc by the fetch script; take top 5
        this.topProps = rows.slice(0, 5).map((r, i) => ({
          rank:       i + 1,
          name:       r.name,
          hitPercent: Math.round(r.hitPct * 100) + '%',
          hrPercent:  Math.round(r.homerPct * 100) + '%',
          xBases:     r.xBases.toFixed(2),
        }));
      },
      error: () => {
        // Leave topProps empty if file is unavailable
      }
    });
  }
}

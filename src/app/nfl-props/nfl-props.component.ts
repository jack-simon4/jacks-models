import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Meta, Title } from '@angular/platform-browser';

interface NflProp {
  name: string;
  team: string;
  opponent: string;
  position: string;
  projYards: number;
  projTDs: number;
  projRec: number | null;
  statLabel: string;
  matchup: string;
  gameTime: string;
}

@Component({
  selector: 'app-nfl-props',
  templateUrl: './nfl-props.component.html',
  styleUrls: ['./nfl-props.component.css']
})
export class NflPropsComponent implements OnInit {
  allProps: NflProp[] = [];
  displayedProps: NflProp[] = [];
  isLoading = true;

  positionFilter: 'ALL' | 'QB' | 'RB' | 'WR' | 'TE' = 'ALL';
  sortColumn = 'projYards';
  sortDir: 'asc' | 'desc' = 'desc';

  constructor(private http: HttpClient, private titleService: Title, private metaService: Meta) {}

  ngOnInit(): void {
    this.titleService.setTitle("NFL Player Props This Week | Stat-Based Projections | Jack's Models");
    this.metaService.updateTag({
      name: 'description',
      content: 'NFL player prop projections for this week — passing yards, rushing yards, receiving yards, receptions, and TDs for all skill position players. Updated weekly with real stat models.'
    });
    this.loadProps();
  }

  loadProps(): void {
    this.http.get<NflProp[]>('assets/nfl-player-props.json').subscribe({
      next: (data) => {
        this.allProps = data ?? [];
        this.isLoading = false;
        this.applyFilter();
      },
      error: () => { this.isLoading = false; }
    });
  }

  setFilter(pos: typeof this.positionFilter): void {
    this.positionFilter = pos;
    this.applyFilter();
  }

  sort(col: string): void {
    if (this.sortColumn === col) {
      this.sortDir = this.sortDir === 'desc' ? 'asc' : 'desc';
    } else {
      this.sortColumn = col;
      this.sortDir = 'desc';
    }
    this.applyFilter();
  }

  sortIcon(col: string): string {
    if (this.sortColumn !== col) return '';
    return this.sortDir === 'desc' ? '▼' : '▲';
  }

  private applyFilter(): void {
    let filtered = this.positionFilter === 'ALL'
      ? [...this.allProps]
      : this.allProps.filter(p => p.position === this.positionFilter);

    filtered.sort((a, b) => {
      const aVal = (a as any)[this.sortColumn] ?? -1;
      const bVal = (b as any)[this.sortColumn] ?? -1;
      return this.sortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });

    this.displayedProps = filtered;
  }

  formatTime(iso: string): string {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
  }
}

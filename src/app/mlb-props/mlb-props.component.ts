import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import * as Papa from 'papaparse';

@Component({
  selector: 'app-mlb-props',
  templateUrl: './mlb-props.component.html',
  styleUrls: ['./mlb-props.component.css']
})
export class MlbPropsComponent implements OnInit {
  playerProps: any[] = [];
  sortedProps: any[] = [];
  sortDirection: { [key: string]: 'asc' | 'desc' } = {};
  isLoading = true;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadPlayerProps();
  }

  loadPlayerProps(): void {
    this.http.get('assets/MLB-Player-Props.csv', { responseType: 'text' })
      .subscribe(data => {
        Papa.parse(data, {
          header: true,
          dynamicTyping: true,
          complete: result => {
            this.playerProps = (result.data as any[]).filter(p => p['Hitters']);
            this.sortedProps = [...this.playerProps];
            this.isLoading = false;
          }
        });
      });
  }

  sortTable(column: string): void {
    const currentDirection = this.sortDirection[column];
    const newDirection = currentDirection === 'desc' ? 'asc' : 'desc';
    this.sortDirection = { [column]: newDirection };

    this.sortedProps.sort((a, b) => {
      const valA = a[column];
      const valB = b[column];
      if (valA < valB) return newDirection === 'asc' ? -1 : 1;
      if (valA > valB) return newDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }
}

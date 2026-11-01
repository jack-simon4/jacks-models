import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  title = 'scoreboard-app';
  lastUpdated = '';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<{ date: string }>('assets/last-updated.json').subscribe({
      next: (d) => { this.lastUpdated = d.date; },
      error: () => {}
    });
  }
}

import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-world-cup-seo-page',
  templateUrl: './world-cup-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class WorldCupSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("2026 FIFA World Cup Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Get stat-driven 2026 FIFA World Cup predictions for all 48 teams. Simulate any group stage or knockout matchup instantly with our free World Cup model."
    });
  }
}

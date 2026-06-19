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
    this.meta.updateTag({ name: 'description', content: "Get stat-driven 2026 FIFA World Cup predictions for all 48 teams. Simulate any group stage or knockout matchup instantly with our free World Cup model." });
    this.meta.updateTag({ property: 'og:title', content: "2026 FIFA World Cup Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Simulate any 2026 World Cup matchup with our free stats model. All 48 nations included — group stage to final." });
    this.meta.updateTag({ property: 'og:url', content: 'https://jacksmodels.com/world-cup-predictions' });
    this.meta.updateTag({ property: 'og:image', content: "https://jacksmodels.com/assets/Jack's_Models_Logo.png" });
    this.meta.updateTag({ name: 'twitter:title', content: "2026 FIFA World Cup Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Simulate any 2026 World Cup matchup with our free stats model. All 48 nations included — group stage to final." });
  }
}

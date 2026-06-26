import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-nba-seo-page',
  templateUrl: './nba-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NbaSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NBA Game Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NBA predictions from Jack's Models. Offensive/defensive ratings, pace, and efficiency — 59% moneyline accuracy across 400 recorded games. All 30 teams supported." });
    this.meta.updateTag({ property: 'og:title',       content: "NBA Game Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free stat-driven NBA picks. 59% moneyline accuracy across 400 games using offensive rating, defensive rating, and pace." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nba-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "NBA Game Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NBA picks using offensive/defensive ratings and pace. 59% ML accuracy across 400 games." });
  }
}

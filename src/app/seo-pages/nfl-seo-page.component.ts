import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-nfl-seo-page',
  templateUrl: './nfl-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NflSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NFL Score Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NFL game predictions from Jack's Models. Rushing/passing efficiency, plays per game, and home field advantage — 68% moneyline accuracy across 116 games. All 32 teams supported." });
    this.meta.updateTag({ property: 'og:title',       content: "NFL Score Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free data-driven NFL predictions. 68% moneyline, 53% ATS, 55% O/U across 116 recorded games." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nfl-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "NFL Score Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NFL picks using rushing/passing efficiency and pace. 68% moneyline accuracy." });
  }
}

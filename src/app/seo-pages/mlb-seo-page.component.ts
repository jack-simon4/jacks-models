import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-mlb-seo-page',
  templateUrl: './mlb-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class MlbSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("MLB Predictions Today | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free MLB predictions powered by Jack's Models. Pitcher FIP, lineup wOBA, ballpark factors — 65% moneyline accuracy across 69 recorded games. Updated daily with today's pitching matchups." });
    this.meta.updateTag({ property: 'og:title',       content: "MLB Predictions Today | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free data-driven MLB game predictions. 65% moneyline, 70% hit prop rate. Updated daily with starting pitchers." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/mlb-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "MLB Predictions Today | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free MLB picks powered by pitcher FIP, lineup wOBA, and ballpark factors. 65% ML accuracy." });
  }
}

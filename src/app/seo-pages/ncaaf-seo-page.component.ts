import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-ncaaf-seo-page',
  templateUrl: './ncaaf-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NcaafSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("College Football Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NCAAF predictions from Jack's Models. SOS-weighted yards per play, offensive/defensive ratings, and pace — 70% moneyline accuracy across 535 games. All 136 FBS teams covered." });
    this.meta.updateTag({ property: 'og:title',       content: "College Football Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NCAAF picks for all 136 FBS teams. 70% moneyline, 59% home dog ATS, 64% extreme totals. Updated weekly." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/ncaaf-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "College Football Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NCAAF picks using SOS-weighted efficiency stats. 70% ML accuracy across 535 games." });
  }
}

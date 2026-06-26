import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-nhl-seo-page',
  templateUrl: './nhl-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NhlSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NHL Score Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NHL predictions from Jack's Models. Goalie save percentage, power play efficiency, and Corsi — 60% moneyline accuracy across 671 recorded games. All 32 teams supported." });
    this.meta.updateTag({ property: 'og:title',       content: "NHL Score Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free data-driven NHL picks. 60% moneyline, 58% favored value rate across 671 games. Goalie stats, power play, and Corsi modeled." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nhl-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "NHL Score Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NHL picks using goalie save %, power play, and Corsi. 60% ML accuracy across 671 games." });
  }
}

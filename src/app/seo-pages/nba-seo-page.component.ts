import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-nba-seo-page',
  templateUrl: './nba-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NbaSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("NBA Game Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NBA predictions from Jack's Models. Offensive/defensive ratings, pace, and efficiency — 59% moneyline accuracy across 400 recorded games. All 30 teams supported." });
    this.meta.updateTag({ property: 'og:title',       content: "NBA Game Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free stat-driven NBA picks. 59% moneyline accuracy across 400 games using offensive rating, defensive rating, and pace." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nba-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "NBA Game Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NBA picks using offensive/defensive ratings and pace. 59% ML accuracy across 400 games." });

    this.jsonLd.set('nba-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'Does the NBA model account for rest days?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Rest advantage is not explicitly modeled, but team efficiency stats reflect each team's rolling performance, which correlates with scheduling load." } },
        { '@type': 'Question', 'name': 'Can I predict NBA playoff series outcomes?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'The model predicts individual game scores. You can run the same matchup multiple times to simulate a series and track projected winners.' } },
        { '@type': 'Question', 'name': 'How accurate are NBA totals (over/under)?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'The model hits 53% on over/under predictions across 400 tracked games, slightly above the break-even threshold.' } },
      ]
    });
  }
}

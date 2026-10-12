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
    this.title.setTitle("Free NBA Predictor | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NBA game predictions powered by real player data. Run any matchup and get projected scores and win probabilities." });
    this.meta.updateTag({ property: 'og:title',       content: "Free NBA Predictor | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NBA game predictions powered by real player data. Run any matchup and get projected scores and win probabilities." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nba-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "Free NBA Predictor | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NBA game predictions powered by real player data. Run any matchup and get projected scores and win probabilities." });

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

import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-mlb-seo-page',
  templateUrl: './mlb-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class MlbSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("MLB Predictions Today | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free MLB predictions powered by Jack's Models. Pitcher FIP, lineup wOBA, ballpark factors — 65% moneyline accuracy across 69 recorded games. Updated daily with today's pitching matchups." });
    this.meta.updateTag({ property: 'og:title',       content: "MLB Predictions Today | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free data-driven MLB game predictions. 65% moneyline, 70% hit prop rate. Updated daily with starting pitchers." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/mlb-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "MLB Predictions Today | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free MLB picks powered by pitcher FIP, lineup wOBA, and ballpark factors. 65% ML accuracy." });

    this.jsonLd.set('mlb-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'How often is the MLB model updated?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Pitcher stats and lineup data are refreshed every morning automatically. The top picks reflect today's confirmed starting pitchers." } },
        { '@type': 'Question', 'name': 'Does the model account for bullpen usage?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "The current model focuses on starting pitcher quality. Bullpen depth is implicitly reflected in team-level defensive stats." } },
        { '@type': 'Question', 'name': 'Is this free to use?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Yes — Jack's Models is completely free. No signup, no paywall." } },
      ]
    });
  }
}

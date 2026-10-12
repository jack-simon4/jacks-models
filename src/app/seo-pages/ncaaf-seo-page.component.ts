import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-ncaaf-seo-page',
  templateUrl: './ncaaf-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NcaafSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("Free College Football Predictor | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Run free NCAAF game predictions for all 136 FBS teams. Stat-driven CFB predictions updated weekly — spread, total, and moneyline projections." });
    this.meta.updateTag({ property: 'og:title',       content: "Free College Football Predictor | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Run free NCAAF game predictions for all 136 FBS teams. Stat-driven CFB predictions updated weekly — spread, total, and moneyline projections." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/ncaaf-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "Free College Football Predictor | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Run free NCAAF game predictions for all 136 FBS teams. Stat-driven CFB predictions updated weekly — spread, total, and moneyline projections." });

    this.jsonLd.set('ncaaf-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'Why is college football moneyline accuracy so high at 70%?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "FBS has extreme talent gaps. Predicting that Alabama beats a mid-major is easier than predicting NFL outcomes where teams are more evenly matched. The model's biggest edge is correctly sizing those mismatches." } },
        { '@type': 'Question', 'name': 'Does the NCAAF model work for bowl games and the CFP?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'Yes — select any two FBS teams in the scoreboard. The model uses season-long stats so it performs well in bowl matchups even when teams have not played each other.' } },
        { '@type': 'Question', 'name': 'How does the college football model handle early-season games?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "In Weeks 1–8, the model blends current-season stats with last year's data to avoid over-weighting a small sample. By Week 8–9, current stats take full precedence." } },
      ]
    });
  }
}

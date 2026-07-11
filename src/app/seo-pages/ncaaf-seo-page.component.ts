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
    this.title.setTitle("College Football Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NCAAF predictions from Jack's Models. SOS-weighted yards per play, offensive/defensive ratings, and pace — 70% moneyline accuracy across 535 games. All 136 FBS teams covered." });
    this.meta.updateTag({ property: 'og:title',       content: "College Football Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NCAAF picks for all 136 FBS teams. 70% moneyline, 59% home dog ATS, 64% extreme totals. Updated weekly." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/ncaaf-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "College Football Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NCAAF picks using SOS-weighted efficiency stats. 70% ML accuracy across 535 games." });

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

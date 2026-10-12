import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-nhl-seo-page',
  templateUrl: './nhl-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NhlSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("Free NHL Predictor | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NHL game predictions updated daily. Stat-driven model covering all 32 teams." });
    this.meta.updateTag({ property: 'og:title',       content: "Free NHL Predictor | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NHL game predictions updated daily. Stat-driven model covering all 32 teams." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nhl-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "Free NHL Predictor | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NHL game predictions updated daily. Stat-driven model covering all 32 teams." });

    this.jsonLd.set('nhl-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'Does the NHL model know which goalie is starting?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "You can select a starting goalie for each team from the scoreboard tool. The goalie's save percentage and GAA are factored into the projected goal totals." } },
        { '@type': 'Question', 'name': 'Why does NHL have the largest sample size?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "The NHL model has been tracking predictions the longest — 671 games across multiple seasons — giving it the most statistically reliable accuracy figures of any sport on the site." } },
        { '@type': 'Question', 'name': 'Can the model predict overtime results?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'The model projects regulation scoring. Overtime and shootout outcomes are essentially coin-flips and are not separately modeled.' } },
      ]
    });
  }
}

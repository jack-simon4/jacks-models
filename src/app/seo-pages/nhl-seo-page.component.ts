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
    this.title.setTitle("NHL Score Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NHL predictions from Jack's Models. Goalie save percentage, power play efficiency, and Corsi — 60% moneyline accuracy across 671 recorded games. All 32 teams supported." });
    this.meta.updateTag({ property: 'og:title',       content: "NHL Score Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free data-driven NHL picks. 60% moneyline, 58% favored value rate across 671 games. Goalie stats, power play, and Corsi modeled." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nhl-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "NHL Score Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NHL picks using goalie save %, power play, and Corsi. 60% ML accuracy across 671 games." });

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

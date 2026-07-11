import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-nfl-seo-page',
  templateUrl: './nfl-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NflSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("NFL Score Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NFL game predictions from Jack's Models. Rushing/passing efficiency, plays per game, and home field advantage — 68% moneyline accuracy across 116 games. All 32 teams supported." });
    this.meta.updateTag({ property: 'og:title',       content: "NFL Score Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free data-driven NFL predictions. 68% moneyline, 53% ATS, 55% O/U across 116 recorded games." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nfl-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "NFL Score Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NFL picks using rushing/passing efficiency and pace. 68% moneyline accuracy." });

    this.jsonLd.set('nfl-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'How often are NFL team stats updated?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'Stats are automatically updated every Monday and Tuesday to capture Sunday games and Monday Night Football.' } },
        { '@type': 'Question', 'name': 'Does the model include injuries?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Injuries are not currently modeled explicitly. The stats reflect each team's recent performance, which inherently captures the effect of key player absences over the last several games." } },
        { '@type': 'Question', 'name': 'Can I use this for playoff games?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'Yes — select any two NFL teams in the scoreboard tool regardless of the type of game.' } },
      ]
    });
  }
}

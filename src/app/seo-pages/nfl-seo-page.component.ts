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
    this.title.setTitle("Free NFL Predictor | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NFL game predictions powered by a stat-driven model. Run any matchup and get projected scores and win probabilities." });
    this.meta.updateTag({ property: 'og:title',       content: "Free NFL Predictor | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NFL game predictions powered by a stat-driven model. Run any matchup and get projected scores and win probabilities." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/nfl-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "Free NFL Predictor | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NFL game predictions powered by a stat-driven model. Run any matchup and get projected scores and win probabilities." });

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

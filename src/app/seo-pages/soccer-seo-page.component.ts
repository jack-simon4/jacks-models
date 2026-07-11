import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-soccer-seo-page',
  templateUrl: './soccer-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class SoccerSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("Soccer Predictions & EPL Picks | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free soccer and EPL predictions from Jack's Models. Expected goals (xG), possession, and goals per game — 68% Tie No Bet accuracy across 112 games. Club and international matches covered." });
    this.meta.updateTag({ property: 'og:title',       content: "Soccer Predictions & EPL Picks | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free soccer picks using xG, possession, and scoring data. 68% Tie No Bet, 60-28-24 record across 112 games." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/soccer-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "Soccer Predictions & EPL Picks | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free soccer predictions using expected goals (xG) and possession stats. 68% Tie No Bet accuracy." });

    this.jsonLd.set('soccer-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'What does "Tie No Bet" mean in soccer predictions?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Tie No Bet is a common soccer betting market where your stake is refunded if the match ends in a draw. The model hits 68% on this market, correctly identifying the winning side in non-draw matches." } },
        { '@type': 'Question', 'name': 'Does the soccer model predict over/under goals?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "The model outputs a projected scoreline for both teams, which gives you an implied total. You can compare this directly to a bookmaker's Over/Under line." } },
        { '@type': 'Question', 'name': 'Can I predict Champions League games?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'Yes — select any two clubs from the soccer scoreboard to run a prediction. The tool works for any club matchup regardless of competition.' } },
      ]
    });
  }
}

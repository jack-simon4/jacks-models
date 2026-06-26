import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-soccer-seo-page',
  templateUrl: './soccer-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class SoccerSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("Soccer Predictions & EPL Picks | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free soccer and EPL predictions from Jack's Models. Expected goals (xG), possession, and goals per game — 68% Tie No Bet accuracy across 112 games. Club and international matches covered." });
    this.meta.updateTag({ property: 'og:title',       content: "Soccer Predictions & EPL Picks | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free soccer picks using xG, possession, and scoring data. 68% Tie No Bet, 60-28-24 record across 112 games." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/soccer-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "Soccer Predictions & EPL Picks | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free soccer predictions using expected goals (xG) and possession stats. 68% Tie No Bet accuracy." });
  }
}

import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-college-baseball-seo-page',
  templateUrl: './college-baseball-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class CollegeBaseballSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("College Baseball Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NCAA Baseball predictions from Jack's Models. ERA, WHIP, and offensive ratings — 76% moneyline accuracy across 237 games, the highest of any sport on the site." });
    this.meta.updateTag({ property: 'og:title',       content: "College Baseball Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NCAA Baseball picks with 76% moneyline accuracy — the highest-performing model on the site. 237 games tracked." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/college-baseball-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "College Baseball Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free college baseball picks. 76% moneyline accuracy across 237 games using ERA, WHIP, and offense ratings." });
  }
}

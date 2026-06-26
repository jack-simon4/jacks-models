import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-ncaam-seo-page',
  templateUrl: './ncaam-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NcaamSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("College Basketball Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NCAAM basketball predictions from Jack's Models. Offensive/defensive efficiency and pace — 73% moneyline accuracy across 1,203 recorded games. March Madness bracket predictions included." });
    this.meta.updateTag({ property: 'og:title',       content: "College Basketball Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NCAAM picks with 73% moneyline accuracy — the highest of any sport on the site. 1,203 games tracked." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/ncaam-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "College Basketball Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NCAAM picks. 73% moneyline accuracy across 1,203 games. March Madness ready." });
  }
}

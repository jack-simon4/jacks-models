import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-ncaam-seo-page',
  templateUrl: './ncaam-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NcaamSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("College Basketball Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NCAAM basketball predictions from Jack's Models. Offensive/defensive efficiency and pace — 73% moneyline accuracy across 1,203 recorded games. March Madness bracket predictions included." });
    this.meta.updateTag({ property: 'og:title',       content: "College Basketball Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NCAAM picks with 73% moneyline accuracy — the highest of any sport on the site. 1,203 games tracked." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/ncaam-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "College Basketball Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free NCAAM picks. 73% moneyline accuracy across 1,203 games. March Madness ready." });

    this.jsonLd.set('ncaam-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'Why is NCAAM moneyline accuracy the highest at 73%?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'College basketball has the most extreme talent spread of any sport on the site. The model correctly identifies large talent gaps, making it particularly effective for March Madness bracket predictions.' } },
        { '@type': 'Question', 'name': 'Does the model cover women\'s basketball (NCAAW)?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Currently the model covers the men's Division I tournament and regular season. NCAAW support is planned for a future update." } },
        { '@type': 'Question', 'name': 'How many college basketball teams are in the model?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'The model covers all major Division I programs. Select any two teams from the scoreboard dropdown to run an instant prediction.' } },
      ]
    });
  }
}

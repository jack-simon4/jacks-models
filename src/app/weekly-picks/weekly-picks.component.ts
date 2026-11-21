import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { WEEKLY_PICKS } from '../generated/picks-data';
import { CanonicalService } from '../shared/canonical.service';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-weekly-picks',
  templateUrl: './weekly-picks.component.html',
  styleUrls: ['./weekly-picks.component.css'],
})
export class WeeklyPicksComponent {
  data = WEEKLY_PICKS;

  constructor(
    private title: Title,
    private meta: Meta,
    private canonical: CanonicalService,
    private jsonLd: JsonLdService,
  ) {
    this.canonical.set('https://jacksmodels.com/weekly-picks');
    this.title.setTitle(`Computer Model Sports Projections — ${this.data.generatedAt} | Jack's Models`);
    this.meta.updateTag({ name: 'description', content: `Jack\'s Models computer projections for NFL, NCAAF, NBA, NCAAM, and NHL — updated ${this.data.generatedAt}. Projected scores, model vs. Vegas lines, and spread edges.` });
    this.meta.updateTag({ property: 'og:title', content: `Computer Model Sports Projections — ${this.data.generatedAt} | Jack's Models` });
    this.meta.updateTag({ property: 'og:url', content: 'https://jacksmodels.com/weekly-picks' });

    this.jsonLd.set('weekly-picks', {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      'name': `Jack's Models Computer Sports Projections — ${this.data.generatedAt}`,
      'description': 'Stat-driven computer model projections for NFL, college football, NBA, college basketball, and NHL games. Includes projected scores, model line vs. Vegas spread, and edge calculations.',
      'url': 'https://jacksmodels.com/weekly-picks',
      'creator': { '@type': 'Organization', 'name': "Jack's Models", 'url': 'https://jacksmodels.com' },
      'dateModified': this.data.generatedAt,
    });
  }
}

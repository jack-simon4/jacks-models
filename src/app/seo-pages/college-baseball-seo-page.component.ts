import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';

@Component({
  selector: 'app-college-baseball-seo-page',
  templateUrl: './college-baseball-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class CollegeBaseballSeoPageComponent {
  constructor(private meta: Meta, private title: Title, private jsonLd: JsonLdService) {
    this.title.setTitle("College Baseball Predictions | Jack's Models");
    this.meta.updateTag({ name: 'description', content: "Free NCAA Baseball predictions from Jack's Models. ERA, WHIP, and offensive ratings — 76% moneyline accuracy across 237 games, the highest of any sport on the site." });
    this.meta.updateTag({ property: 'og:title',       content: "College Baseball Predictions | Jack's Models" });
    this.meta.updateTag({ property: 'og:description', content: "Free NCAA Baseball picks with 76% moneyline accuracy — the highest-performing model on the site. 237 games tracked." });
    this.meta.updateTag({ property: 'og:url',         content: 'https://jacksmodels.com/college-baseball-predictions' });
    this.meta.updateTag({ name: 'twitter:title',       content: "College Baseball Predictions | Jack's Models" });
    this.meta.updateTag({ name: 'twitter:description', content: "Free college baseball picks. 76% moneyline accuracy across 237 games using ERA, WHIP, and offense ratings." });

    this.jsonLd.set('college-baseball-faq', {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      'mainEntity': [
        { '@type': 'Question', 'name': 'Why is college baseball the most accurate sport on the site?',
          'acceptedAnswer': { '@type': 'Answer', 'text': 'College baseball has larger gaps in team quality than most sports, especially during the NCAA Tournament when top national seeds play smaller conference teams in regional rounds. The model correctly identifies these mismatches at a high rate.' } },
        { '@type': 'Question', 'name': 'How many college baseball teams are supported?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "The model covers all major Division I programs. Select any two teams from the scoreboard's College Baseball dropdown to run a prediction." } },
        { '@type': 'Question', 'name': 'Does the college baseball model account for the starting pitcher?',
          'acceptedAnswer': { '@type': 'Answer', 'text': "Yes — pitcher ERA and WHIP are primary inputs. Weekend ace vs. mid-week starter differences are reflected in the team's pitching stats." } },
      ]
    });
  }
}

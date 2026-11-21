import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';
import { JsonLdService } from '../shared/json-ld.service';
import { CanonicalService } from '../shared/canonical.service';

@Component({
  selector: 'app-about',
  templateUrl: './about.component.html',
  styleUrls: ['./about.component.css']
})
export class AboutComponent {
  constructor(
    private title: Title,
    private meta: Meta,
    private jsonLd: JsonLdService,
    private canonical: CanonicalService,
  ) {
    this.canonical.set('https://jacksmodels.com/about');
    this.title.setTitle("About Jack's Models | Statistical Sports Prediction Models");
    this.meta.updateTag({ name: 'description', content: "Jack's Models is a free statistical sports prediction website built by Jack Simon. Data-driven computer models for NFL, NBA, MLB, NHL, college football, and college basketball — updated daily." });
    this.meta.updateTag({ property: 'og:title', content: "About Jack's Models | Statistical Sports Prediction Models" });
    this.meta.updateTag({ property: 'og:url', content: 'https://jacksmodels.com/about' });

    this.jsonLd.set('organization', {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      'name': "Jack's Models",
      'alternateName': 'JacksModels',
      'url': 'https://jacksmodels.com',
      'logo': "https://jacksmodels.com/assets/Jack's_Models_Logo.png",
      'description': "Jack's Models is a free statistical sports prediction website. Data-driven computer models project scores and spreads for NFL, NBA, MLB, NHL, NCAAF, NCAAM, Soccer, and College Baseball games. The site was founded by Jack Simon in 2024.",
      'founder': {
        '@type': 'Person',
        'name': 'Jack Simon',
        'email': 'jack.e.simon@gmail.com',
      },
      'foundingDate': '2024-01-17',
      'contactPoint': {
        '@type': 'ContactPoint',
        'email': 'jack.e.simon@gmail.com',
        'contactType': 'customer support',
      },
      'sameAs': [
        'https://jacksmodels.com',
      ],
    });
  }
}

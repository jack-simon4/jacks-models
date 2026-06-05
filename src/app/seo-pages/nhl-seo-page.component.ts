import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-nhl-seo-page',
  templateUrl: './nhl-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NhlSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NHL Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Get NHL score predictions for any matchup. Select any two NHL teams and instantly view projected results."
    });
  }
}

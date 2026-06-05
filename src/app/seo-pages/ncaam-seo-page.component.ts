import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-ncaam-seo-page',
  templateUrl: './ncaam-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NcaamSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NCAAM Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Predict any college basketball matchup using Jack’s Models. Select any two NCAAM teams to get score projections."
    });
  }
}

import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-ncaaf-seo-page',
  templateUrl: './ncaaf-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NcaafSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NCAAF Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "NCAAF predictions you can customize. Enter any two college football teams and get instant score predictions."
    });
  }
}

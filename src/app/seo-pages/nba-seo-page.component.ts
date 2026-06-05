import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-nba-seo-page',
  templateUrl: './nba-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NbaSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NBA Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Free NBA predictions from Jack's Models. Choose any two NBA teams and get instant projected scores."
    });
  }
}

import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-nfl-seo-page',
  templateUrl: './nfl-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class NflSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("NFL Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Get free NFL predictions using Jack's Models. Enter any two NFL teams and instantly get AI-powered score predictions."
    });
  }
}


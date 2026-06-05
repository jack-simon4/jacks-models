import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-soccer-seo-page',
  templateUrl: './soccer-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class SoccerSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("Soccer Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Get soccer predictions across multiple leagues. Select any two teams and instantly view projected match results."
    });
  }
}

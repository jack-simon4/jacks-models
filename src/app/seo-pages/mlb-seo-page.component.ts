import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-mlb-seo-page',
  templateUrl: './mlb-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class MlbSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("MLB Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Free MLB game predictions powered by Jack's Models. Choose any two MLB teams and get instant score projections."
    });
  }
}

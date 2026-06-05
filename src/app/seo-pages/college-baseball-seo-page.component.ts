import { Component } from '@angular/core';
import { Meta, Title } from '@angular/platform-browser';

@Component({
  selector: 'app-college-baseball-seo-page',
  templateUrl: './college-baseball-seo-page.component.html',
  styleUrls: ['./seo-page.component.css']
})
export class CollegeBaseballSeoPageComponent {
  constructor(private meta: Meta, private title: Title) {
    this.title.setTitle("College Baseball Predictions | Jack's Models");
    this.meta.updateTag({
      name: 'description',
      content:
        "Free college baseball predictions. Choose any two NCAA baseball teams and get projected scores."
    });
  }
}

import { Component } from '@angular/core';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent {

  topPicks = [
    {
      rank: 1,
      matchup: 'Red Sox vs Yankees',
      prediction: 'Yankees -144',
      confidence: 'Elite'
    },
    {
      rank: 2,
      matchup: 'Cal Poly vs West Virginia',
      prediction: 'West Virginia -1.5',
      confidence: 'Strong'
    },
    {
      rank: 3,
      matchup: 'Knicks vs Spurs',
      prediction: 'Knicks +6.5',
      confidence: 'Lean'
    }
  ];

  topProps = [
    {
      rank: 1,
      name: 'George Springer',
      hitPercent: '89%',
      hrPercent: '38%',
      xBases: '3.26'
    },
    {
      rank: 2,
      name: 'Kyle Schwarber',
      hitPercent: '67%',
      hrPercent: '44%',
      xBases: '2.50'
    },
    {
      rank: 3,
      name: 'Chandler Simpson',
      hitPercent: '89%',
      hrPercent: '<0%',
      xBases: '2.044'
    },
    {
      rank: 4,
      name: 'Jackson Chourio',
      hitPercent: '86%',
      hrPercent: '22%',
      xBases: '2.97'
    },
    {
      rank: 5,
      name: 'Christian Yelich',
      hitPercent: '86%',
      hrPercent: '30%',
      xBases: '2.94'
    }
  ];

}
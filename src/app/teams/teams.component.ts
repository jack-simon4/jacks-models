import { Component, Input } from '@angular/core';

// Define the type for sportsTeams
interface SportsTeams {
  [sport: string]: string[];
}

@Component({
  selector: 'app-teams',
  templateUrl: './teams.component.html',
  styleUrls: ['./teams.component.css']
})
export class TeamsComponent {
  @Input() selectedSport: string = 'Basketball';
  selectedHomeTeam: string = '';
  selectedAwayTeam: string = '';

  homeTeams: string[] = [];
  awayTeams: string[] = [];

  // Define your teams for each sport
  sportsTeams: SportsTeams = {
    'Basketball': ['Team A', 'Team B', 'Team C'],
    'Football': ['Team X', 'Team Y', 'Team Z']
    // Add more sports and their corresponding teams as needed
  };

  updateTeams() {
    this.homeTeams = this.sportsTeams[this.selectedSport];
    this.awayTeams = this.sportsTeams[this.selectedSport];
  }

  ngOnChanges() {
    this.updateTeams();
  }
}


import { Component, EventEmitter, Output } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-ribbon',
  templateUrl: './ribbon.component.html',
  styleUrls: ['./ribbon.component.css']
})
export class RibbonComponent {
  constructor(private router: Router) {}

  openSoccerScoreboard() {
    this.router.navigate(['/soccer']);
  }
  @Output() sportSelected = new EventEmitter<string>();
  selectedSport: string = ''; // Initialize the property with an empty string
  selectedSoccerLeague: string = ''; // Store the selected soccer league

  // Define your sports here (replace these with your actual sports)
  sports: string[] = ['NFL', 'NBA', 'NHL', 'MLB', 'NCAAF', 'NCAAM', 'NCAA-Baseball'];

  // Soccer leagues to be used in the dropdown
  soccerLeagues: string[] = ['EPL', 'La Liga', 'Bundesliga', 'Serie A', 'Ligue 1'];

  selectSport(sport: string) {
    this.selectedSport = sport; // Set the selectedSport property to the clicked sport
    this.sportSelected.emit(sport);
  }

  // Emit the selected soccer league when a league is chosen
  selectSoccerLeague(league: string) {
    this.selectedSoccerLeague = league;
    this.sportSelected.emit(league); // Emit the selected league as a sport selection
  }
}

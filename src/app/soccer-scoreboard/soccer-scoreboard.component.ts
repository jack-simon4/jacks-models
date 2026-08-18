import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { MatDialog } from '@angular/material/dialog';
import { ScoreboardPopupComponent } from '../scoreboard-popup/scoreboard-popup.component';
import { single } from 'rxjs';
import { AngularFirestore } from '@angular/fire/compat/firestore';


interface SoccerStats { 
    [team: string]: { GF: number; GA: number; wGF: number, wGA: number,wLeague:number, HomeAdv: number };
}

interface LeaguesTeams {
    [league: string]: string[];
}

@Component({
  selector: 'app-soccer-scoreboard',
  templateUrl: './soccer-scoreboard.component.html',
  styleUrls: ['./soccer-scoreboard.component.css']
})
export class SoccerScoreboardComponent implements OnInit {
  selectedLeague: string = 'World Cup';
  selectedHomeTeam: string = '';
  selectedAwayTeam: string = '';
  homeTeams: string[] = [];
  awayTeams: string[] = [];
  homeTeamScore: number = 0;
  awayTeamScore: number = 0;
  isNeutralSite: boolean = false;
  soccerStats: SoccerStats = {};
  leaguesTeams: LeaguesTeams = {};

  Leagues: string[] = ['World Cup', 'Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'Champions League', 'MLS'];

  constructor(private http: HttpClient, private dialog: MatDialog,  private firestore: AngularFirestore) { }

  ngOnInit(): void {
    this.loadTeamsData();
    this.loadSoccerStatsData();
  }

  resetScores() {
    this.homeTeamScore = 0;
    this.awayTeamScore = 0;
  }
  

  loadTeamsData() {
    const leagues: string[] = this.Leagues;

    // Fetch CSV data for each league
    const fetchPromises = leagues.map(league => {
      const url = `assets/${league}-Teams.csv`;
      console.log(`Loading data from: ${url}`); // Log the URLs
      return this.http.get(url, { responseType: 'text' }).toPromise();
    });

    // Process CSV data and populate leaguesTeams object
    Promise.all(fetchPromises)
      .then(csvDataArray => {
        csvDataArray.forEach((csvData, index) => {
          const league = leagues[index];
          const teams = csvData ? csvData.split('\n').slice(1).map(row => row.trim()) : [];
          this.leaguesTeams[league] = teams;
        });

        // Set initial teams and scores for the default selected league
        this.updateTeams();
      })
      .catch(error => {
        console.error('Error loading CSV data:', error);
      });
  }

  loadSoccerStatsData() {
    const SoccerStatsUrl = 'assets/Soccer-Stats.csv';
    this.http.get(SoccerStatsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.soccerStats = this.parseSoccerStats(csvData);
      })
      .catch(error => {
        console.error('Error loading Soccer stats data:', error);
      });
  }
  
  
  parseSoccerStats(csvData: string | undefined) {
    const xGoals: { [team: string]: { GF: number; GA: number; wGF: number, wGA: number, wLeague:number,
      HomeAdv: number } } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, GF, GA, wGF, wGA,wLeague, HomeAdv] = line.trim().split(',');
        xGoals[team] = {
          GF: parseFloat(GF), // Convert to number
          GA: parseFloat(GA), // Convert to number
          wGF: parseFloat(wGF), // Convert to number
          wGA: parseFloat(wGA), 
          wLeague:parseFloat(wLeague),// Convert to number
          HomeAdv: parseFloat(HomeAdv), // Convert to number
        };
      });
  
      
    }
  
    return xGoals;
  }

  updateTeams() {
    this.homeTeams = this.leaguesTeams[this.selectedLeague] || [];
    this.awayTeams = this.leaguesTeams[this.selectedLeague] || [];
    this.selectedHomeTeam = this.homeTeams[0] || ''; // Set default home team
    this.selectedAwayTeam = this.awayTeams[0] || ''; // Set default away team
  }

  onLeagueSelected(league: string) {
    this.selectedLeague = league;
    this.updateTeams(); // Update teams when league changes
    this.resetScores(); // Reset scores when league changes
  }

  
  showDetailsButton: boolean = false;

  selectLeague(league: string) {
    this.selectedLeague = league; // Set the selectedLeague property to the clicked league
    this.updateTeams(); // Update teams when a new league is selected
    this.resetScores();
  }
  async runSimulation() {
   
            const homeTeamSoccer = this.soccerStats[this.selectedHomeTeam];
            const awayTeamSoccer = this.soccerStats[this.selectedAwayTeam];
            if (homeTeamSoccer && awayTeamSoccer) {
    
              const homeAdvModifier = this.isNeutralSite ? 0 : homeTeamSoccer.HomeAdv;
          
              // Calculate the home team's total score
              this.homeTeamScore = Number((((homeTeamSoccer.GF * awayTeamSoccer.wGA) +(homeTeamSoccer.wGF * awayTeamSoccer.GA))/2 * ((homeTeamSoccer.wLeague/awayTeamSoccer.wLeague)*(homeTeamSoccer.wLeague/awayTeamSoccer.wLeague)) *(1 + homeAdvModifier)).toFixed(3));
    
              // Calculate the away team's total score
              this.awayTeamScore = Number((((awayTeamSoccer.GF * homeTeamSoccer.wGA) +(awayTeamSoccer.wGF * homeTeamSoccer.GA))/2 * ((awayTeamSoccer.wLeague/homeTeamSoccer.wLeague) * (awayTeamSoccer.wLeague/homeTeamSoccer.wLeague)) *(1- homeAdvModifier)).toFixed(3));
            }
            this.showDetailsButton = true;
            console.log(this.homeTeamScore, homeTeamSoccer.GF, awayTeamSoccer.wGA )
            // await this.savePrediction();  //REMOVE THIS LINE BEFORE DEPLOYING
  }

  openDetailsPopup() {
    // Calculate the winner
    const winner: string = this.homeTeamScore > this.awayTeamScore ? this.selectedHomeTeam : this.selectedAwayTeam;
  
  
    // Calculate the winning percentage (ensure it's above 50%)
    const totalScore = Math.round(this.homeTeamScore + this.awayTeamScore);
    let winningPercentage: number;
          winningPercentage =  Math.round(12.9897 + 26.11665 * this.homeTeamScore + (-9.4232 * this.awayTeamScore));
        winningPercentage = Math.round(100 * (0.495911 + 0.02832 * (this.awayTeamScore - this.homeTeamScore)));
      if (winner === this.selectedHomeTeam) {
        winningPercentage = Math.round((this.homeTeamScore / totalScore) * 100);
      } else {
        winningPercentage = Math.round((this.awayTeamScore / totalScore) * 100);
      }
    
    // Expected odds

    let expectedOdds: number = 0;
        expectedOdds = Math.round((10000 / (100 - winningPercentage) - 100) * -1);

    
  
    // Calculate the margin of victory and round it to 2 decimal places
    let marginOfVictory: number = Math.abs(this.homeTeamScore - this.awayTeamScore);
    marginOfVictory = Number(marginOfVictory.toFixed(2));
  
    // Calculate the total score and round it to 2 decimal places
    let totalScoreRounded: number = totalScore;
    totalScoreRounded = parseFloat(totalScoreRounded.toFixed(2)); // Convert to number with 2 decimal places
  
    
  
  
    // Open the dialog
    const dialogRef = this.dialog.open(ScoreboardPopupComponent, {
      data: {
        winner,
        winningPercentage,
        expectedOdds: expectedOdds,
        marginOfVictory,
        totalScoreRounded,
        homeTeamScore: this.homeTeamScore,
        awayTeamScore: this.awayTeamScore,
      },
      
      
      panelClass: 'scoreboard-popup' // Apply the custom CSS class
    });
  }
  async savePrediction() {
    const gameData = {
      sport: this.selectedLeague,
      homeTeam: this.selectedHomeTeam,
      awayTeam: this.selectedAwayTeam,
      predictedHomeScore: this.homeTeamScore,
      predictedAwayScore: this.awayTeamScore,
      actualHomeScore : 0, // Include actual home score
      actualAwayScore: 0,
      timestamp: new Date() // Record the current time
    };
  
    try {
      await this.firestore.collection('games').add(gameData);
      console.log('Prediction saved successfully:', gameData);
    } catch (error) {
      console.error('Error saving prediction:', error);
    }
  }
  

  
  }
  
  
  


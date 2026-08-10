import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { MatDialog } from '@angular/material/dialog';
import { ScoreboardPopupComponent } from '../scoreboard-popup/scoreboard-popup.component';
import { single } from 'rxjs';
import { AngularFirestore } from '@angular/fire/compat/firestore';
import { TEAM_COLORS } from '../team-colors'; // Import the team colors
import { CommonModule } from '@angular/common';
import * as Papa from 'papaparse'
import { environment } from '../../environments/environment';




interface Goalie {
  name: string;
  gaa: number;
  sv: number;
}

interface NCAAMStats {
  [team: string]: { adjO: number; adjD: number; adjT: number, ORank: number,
     DRank: number, TRank: number, HomeAdv: number };
}

interface SportsTeams {
  [sport: string]: string[];
}
interface Pitcher {
  name: string;
  k_percent: number;
  bb_percent: number;
  xba: number;
  xslg: number;
  xobp: number;
  single_percent: number;
  double_percent: number;
  triple_percent: number;
  home_run_percent: number;
  pa_per_game: number;
  hand: string
  // Add additional properties as needed
}



interface NBAStats { 
  [team: string]: { Off: number; oLastThree: number; oHome: number, oAway: number,
     adjO: number, Def: number, dLastThree: number, dHome: number, dAway: number, adjD: number, 
    Tempo: number, adjT: number };
}

interface BallparkFactors {
  [team: string]: {
    w1B: number;
    w2B: number;
    w3B: number;
    wHR: number;
    wBB: number;
    wSO: number;
    wRest: number;
    wOBP: number;
    TB_R: number
  };
}


interface EPLStats { 
  [team: string]: { GF: number; GA: number; wGF: number, wGA: number,
     HomeAdv: number};
}
interface NCAABaseballStats { 
  [team: string]: { R: number; RA: number; wR: number, wRA: number};
}

interface NCAAFStats { 
  [team: string]: { SOS: number, oRating: number, dRating: number, YdsPlay: number, YdsPlayL3: number, wYdsPlay: number,
    dYdsPlay:number, dYdsPlayL3: number, wdYdsPlay:number, YdsPt:number, YdsPtL3:number, wYdsPt:number
    dYdsPt:number, dYdsPtL3:number, wdYdsPt:number, PlaysGame:number, dPlaysGame:number, HomeAdv:number};
}


interface NFLStats { 
  [team: string]: { RushYdsAtt: number; dRushYdsAtt: number; PassYdsAtt: number, dPassYdsAtt: number,
     oRushPerGame: number, dRushPerGame: number, oPassPerGame: number, dPassPerGame: number,
    oYdsPerPoint: number, dYdsPerPoint: number, oPtsPerPlay: number, dPtsPerPlay: number,
     oPlaysGame: number, dPlaysGame: number,HomeAdv: number};
}

interface NHLStats { [team: string]: {ShotsF:number, PP:number, ShotsA:number, S:number}}

interface Hitter {
  name: string;
  k_percent: number;
  bb_percent: number;
  xba: number;
  xslg: number;
  xobp: number;
  single_percent: number;
  double_percent: number;
  triple_percent: number;
  home_run_percent: number;
  xOPS: number;
  wRops: number;
  wLops: number;
  // Add additional properties as needed
}

@Component({
  selector: 'app-scoreboard',
  templateUrl: './scoreboard.component.html',
  styleUrls: ['./scoreboard.component.css']
})
export class ScoreboardComponent implements OnInit {
  selectedSport: string = 'NFL';
  selectedHomeTeam: string = '';
  selectedAwayTeam: string = '';
  homeTeams: string[] = [];
  awayTeams: string[] = [];
  homeTeamScore: number = 0;
  awayTeamScore: number = 0;
  ncaamStats: NCAAMStats = {}; // Store NCAAM stats from the CSV file
  sportsTeams: SportsTeams = {};
  isNeutralSite: boolean = false;
  selectedHomePitcher: string = '';
  selectedAwayPitcher: string = '';
  pitchersList: Pitcher[] = [];
  selectedHomeGoalie: string = '';
  selectedAwayGoalie: string = '';
  goaliesList: Goalie[] = [];
  nbaStats: NBAStats ={};
  ncaafStats: NCAAFStats = {};
  nflstats: NFLStats = {};
  nhlstats: NHLStats = {};
  ncaamSpreads: { [team: string]: number } = {};
  nbaSpreads: { [team: string]: number } = {};
  nflSpreads: { [team: string]: number } = {};
  nhlOdds: Record<string, number> = {};
  eplStats: EPLStats = {};
  ncaaBaseballStats: NCAABaseballStats = {};
  mlbLineups: { [team: string]: string[] } = {}; // Store lineup players by team
  HittersList: Hitter[]=[];
  awayHitPercent: number [] = [];
  homeHitPercent:number [] = [];
  awayxBases: number [] = [];
  homexBases:number [] = [];
  selectedHomePitcherHand: string = ''; // For the home pitcher's handedness
  selectedAwayPitcherHand: string = '';
  ballparkFactors: BallparkFactors = {};
  HomeSPK: number =0;
  AwaySPK: number=0;
  selectedTeam: string = "Arizona Diamondbacks"; // Example team, update dynamically
  playerProps: any[] = [];
  sortedProps: any[] = [];
  sortDirection: { [key: string]: 'asc' | 'desc' } = {};
  showPlayerProps = false;

  



  getTeamColor(team: string | null | undefined): string {
    if (!team || !TEAM_COLORS[team]) return "#ffffff"; // Default to white if not found
    return TEAM_COLORS[team].primary; // Return the primary team color
  }
  
  getTextOutline(team: string | null | undefined): string {
    if (!team || !TEAM_COLORS[team]) return "none"; // Default if no team found
  
    const secondaryColor = TEAM_COLORS[team].secondary;
    return `
      -.5px -.5px 0 ${secondaryColor}, 
       .5px -.5px 0 ${secondaryColor}, 
      -.5px  .5px 0 ${secondaryColor}, 
       .5px  .5px 0 ${secondaryColor}, 
      -.5px  0px 0 ${secondaryColor}, 
       .5px  0px 0 ${secondaryColor}, 
       0px -.5px 0 ${secondaryColor}, 
       0px  .5px 0 ${secondaryColor}
    `;
  }
  
 // Pitcher searchable dropdown
 searchTextHomePitcher: string = '';
 searchTextAwayPitcher: string = '';
 showHomePitcherDropdown: boolean = false;
 showAwayPitcherDropdown: boolean = false;
 filteredHomePitchers: Pitcher[] = this.pitchersList;
 filteredAwayPitchers: Pitcher[] = this.pitchersList;

 // Team searchable dropdown
 searchTextAwayTeam: string = '';
 searchTextHomeTeam: string = '';
 showAwayTeamDropdown: boolean = false;
 showHomeTeamDropdown: boolean = false;
 filteredAwayTeams: string[] = [];
 filteredHomeTeams: string[] = [];

 // Goalie searchable dropdown
 searchTextAwayGoalie: string = '';
 searchTextHomeGoalie: string = '';
 showAwayGoalieDropdown: boolean = false;
 showHomeGoalieDropdown: boolean = false;
 filteredAwayGoalies: Goalie[] = [];
 filteredHomeGoalies: Goalie[] = [];
  
  
 
 private asciiNorm(name: string): string {
   return (name || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').trim();
 }

 // True log5 formula: combines independent batter/pitcher/league rates correctly.
 // More accurate than simple multiplication at extreme values.
 private log5(b: number, p: number, l: number): number {
   if (l <= 0 || l >= 1 || b <= 0 || p <= 0) return 0;
   const bp = (b * p) / l;
   const neg = ((1 - b) * (1 - p)) / (1 - l);
   return bp / (bp + neg);
 }

 getHTeamColor(): string {
  return TEAM_COLORS[this.selectedHomeTeam]?.primary || '#ffffff'; // Default white if not found
}

 
getATeamColor(): string {
  return TEAM_COLORS[this.selectedAwayTeam]?.primary || '#ffffff'; // Default white if not found
}

  constructor(private http: HttpClient, private dialog: MatDialog,  private firestore: AngularFirestore) {}
  



  ngOnInit() {
    this.loadTeamsData();
    this.loadMLBPitchersData(); // Load pitchers data when the component initializes
    this.loadNHLGoaliesData(); // Load goalies data when the component initializes
    this.loadNCAAMStatsData();
    this.loadNBAStatsData();
    this.loadNCAAFStatsData();
    this.loadNFLStatsData();
    this.loadNHLStatsData();
    this.loadNCAAMSpreadsData();
    this.loadNBASpreadsData();
    this.loadNFLSpreadsData();
    this.loadNCAABaseballStatsData();
    this.loadMLBHittersData();
    this.loadMLBBallparksData();
    this.loadPlayerProps();
    
  
 
  
    this.http.get(environment.mlbLineupsUrl, { responseType: 'text' }).subscribe(data => {
      const lines = data.split('\n');
      lines.forEach(line => {
        const parts = line.split(',');
        const team = parts[0];
        const player = parts[1];
        if (!this.mlbLineups[team]) {
          this.mlbLineups[team] = [];
        }
        this.mlbLineups[team].push(player);
      });
    });
    
  }

  filterHomePitchers() {
    this.filteredHomePitchers = this.pitchersList.filter(pitcher =>
      pitcher.name.toLowerCase().includes(this.searchTextHomePitcher.toLowerCase())
    );
  }
  filterAwayPitchers() {
    this.filteredAwayPitchers = this.pitchersList.filter(pitcher =>
      pitcher.name.toLowerCase().includes(this.searchTextAwayPitcher.toLowerCase())
    );
  }

  selectHomePitcher(pitcherName: string) {
    this.selectedHomePitcher = pitcherName;
    this.searchTextHomePitcher = pitcherName;
    this.showHomePitcherDropdown = false;
  }

  selectAwayPitcher(pitcherName: string) {
    this.selectedAwayPitcher = pitcherName;
    this.searchTextAwayPitcher = pitcherName;
    this.showAwayPitcherDropdown = false;
  }
  hideDropdown(type: string) {
    setTimeout(() => {
      if (type === 'home') {
        this.showHomePitcherDropdown = false;
      } else if (type === 'away') {
        this.showAwayPitcherDropdown = false;
      } else if (type === 'awayTeam') {
        this.showAwayTeamDropdown = false;
        this.searchTextAwayTeam = this.selectedAwayTeam;
      } else if (type === 'homeTeam') {
        this.showHomeTeamDropdown = false;
        this.searchTextHomeTeam = this.selectedHomeTeam;
      } else if (type === 'awayGoalie') {
        this.showAwayGoalieDropdown = false;
        this.searchTextAwayGoalie = this.selectedAwayGoalie;
      } else if (type === 'homeGoalie') {
        this.showHomeGoalieDropdown = false;
        this.searchTextHomeGoalie = this.selectedHomeGoalie;
      }
    }, 200);
  }

  clearInput(type: string) {
    if (type === 'home') {
      this.searchTextHomePitcher = '';
      this.showHomePitcherDropdown = true;
    } else if (type === 'away') {
      this.searchTextAwayPitcher = '';
      this.showAwayPitcherDropdown = true;
    } else if (type === 'awayTeam') {
      this.searchTextAwayTeam = '';
      this.filteredAwayTeams = this.awayTeams;
      this.showAwayTeamDropdown = true;
    } else if (type === 'homeTeam') {
      this.searchTextHomeTeam = '';
      this.filteredHomeTeams = this.homeTeams;
      this.showHomeTeamDropdown = true;
    } else if (type === 'awayGoalie') {
      this.searchTextAwayGoalie = '';
      this.filteredAwayGoalies = this.goaliesList;
      this.showAwayGoalieDropdown = true;
    } else if (type === 'homeGoalie') {
      this.searchTextHomeGoalie = '';
      this.filteredHomeGoalies = this.goaliesList;
      this.showHomeGoalieDropdown = true;
    }
  }

  onDropdownKeydown(event: KeyboardEvent, type: string) {
    if (event.key !== 'Enter' && event.key !== 'Tab') return;
    const isTab = event.key === 'Tab';
    switch (type) {
      case 'awayTeam':
        if (this.filteredAwayTeams.length) { if (!isTab) event.preventDefault(); this.selectAwayTeam(this.filteredAwayTeams[0]); }
        break;
      case 'homeTeam':
        if (this.filteredHomeTeams.length) { if (!isTab) event.preventDefault(); this.selectHomeTeam(this.filteredHomeTeams[0]); }
        break;
      case 'awayGoalie':
        if (this.filteredAwayGoalies.length) { if (!isTab) event.preventDefault(); this.selectAwayGoalie(this.filteredAwayGoalies[0].name); }
        break;
      case 'homeGoalie':
        if (this.filteredHomeGoalies.length) { if (!isTab) event.preventDefault(); this.selectHomeGoalie(this.filteredHomeGoalies[0].name); }
        break;
      case 'awayPitcher':
        if (this.filteredAwayPitchers.length) { if (!isTab) event.preventDefault(); this.selectAwayPitcher(this.filteredAwayPitchers[0].name); }
        break;
      case 'homePitcher':
        if (this.filteredHomePitchers.length) { if (!isTab) event.preventDefault(); this.selectHomePitcher(this.filteredHomePitchers[0].name); }
        break;
    }
  }

  filterAwayTeams() {
    this.filteredAwayTeams = this.awayTeams.filter(team =>
      team.toLowerCase().includes(this.searchTextAwayTeam.toLowerCase())
    );
    this.showAwayTeamDropdown = true;
  }

  filterHomeTeams() {
    this.filteredHomeTeams = this.homeTeams.filter(team =>
      team.toLowerCase().includes(this.searchTextHomeTeam.toLowerCase())
    );
    this.showHomeTeamDropdown = true;
  }

  selectAwayTeam(team: string) {
    this.selectedAwayTeam = team;
    this.searchTextAwayTeam = team;
    this.showAwayTeamDropdown = false;
  }

  selectHomeTeam(team: string) {
    this.selectedHomeTeam = team;
    this.searchTextHomeTeam = team;
    this.showHomeTeamDropdown = false;
  }

  filterAwayGoalies() {
    this.filteredAwayGoalies = this.goaliesList.filter(g =>
      g.name.toLowerCase().includes(this.searchTextAwayGoalie.toLowerCase())
    );
    this.showAwayGoalieDropdown = true;
  }

  filterHomeGoalies() {
    this.filteredHomeGoalies = this.goaliesList.filter(g =>
      g.name.toLowerCase().includes(this.searchTextHomeGoalie.toLowerCase())
    );
    this.showHomeGoalieDropdown = true;
  }

  selectAwayGoalie(name: string) {
    this.selectedAwayGoalie = name;
    this.searchTextAwayGoalie = name;
    this.showAwayGoalieDropdown = false;
  }

  selectHomeGoalie(name: string) {
    this.selectedHomeGoalie = name;
    this.searchTextHomeGoalie = name;
    this.showHomeGoalieDropdown = false;
  }
  

  showDetailsButton: boolean = false;

// Add this function to your component
resetScores() {
  this.homeTeamScore = 0;
  this.awayTeamScore = 0;
}




  loadTeamsData() {
    const sports: string[] = ['NFL', 'NBA', 'MLB', 'NHL', 'NCAAF', 'NCAAM', 'EPL', 'NCAA-Baseball'];

    // Fetch CSV data for each sport
    const fetchPromises = sports.map(sport => {
      const url = `assets/${sport}-Teams.csv`;
      return this.http.get(url, { responseType: 'text' }).toPromise();
    });
    
    // Process CSV data and populate sportsTeams object
    Promise.all(fetchPromises)
      .then(csvDataArray => {
        csvDataArray.forEach((csvData, index) => {
          const sport = sports[index];
          const teams = csvData ? csvData.split('\n').slice(1).map(row => row.trim()) : [];
          this.sportsTeams[sport] = teams;
        });

        // Set initial teams and scores
        this.updateTeams();
      })
      .catch(error => {
        console.error('Error loading CSV data:', error);
      });
  }



  //NFL STUFF 
  
  loadNFLSpreadsData() {
    const nflSpreadsUrl = 'assets/NFL-Spreads.csv';
    this.http.get(nflSpreadsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.nflSpreads = this.parseNFLSpreads(csvData);
      })
      .catch(error => {
        console.error('Error loading NFL spreads data:', error);
      });
  }
  
  parseNFLSpreads(csvData: string | undefined) {
    const spreads: { [team: string]: number } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, spread] = line.trim().split(',');
        spreads[team] = parseFloat(spread); // Convert to number
      });
  
      
    }
  
    return spreads;
  }
  

  loadNFLStatsData() {
    const NFLStatsUrl = 'assets/NFL-Stats.csv';
    this.http.get(NFLStatsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.nflstats = this.parseNFLStats(csvData);
      })
      .catch(error => {
        console.error('Error loading NFL stats data:', error);
      });
  }
  

  parseNFLStats(csvData: string | undefined) {
    const projscore: { [team: string]: { RushYdsAtt: number; dRushYdsAtt: number; PassYdsAtt: number, dPassYdsAtt: number,
      oRushPerGame: number, dRushPerGame: number, oPassPerGame: number, dPassPerGame: number,
     oYdsPerPoint: number, dYdsPerPoint: number, oPtsPerPlay: number, dPtsPerPlay: number,
      oPlaysGame: number, dPlaysGame: number,HomeAdv: number  } } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, RushYdsAtt, dRushYdsAtt, PassYdsAtt, dPassYdsAtt,
          oRushPerGame, dRushPerGame, oPassPerGame, dPassPerGame,
         oYdsPerPoint, dYdsPerPoint, oPtsPerPlay, dPtsPerPlay,
          oPlaysGame, dPlaysGame, HomeAdv] = line.trim().split(',');
        projscore[team] = {
          RushYdsAtt: parseFloat(RushYdsAtt), // Convert to number
          dRushYdsAtt:parseFloat(dRushYdsAtt), // Convert to number
           PassYdsAtt:parseFloat(PassYdsAtt), // Convert to number
            dPassYdsAtt:parseFloat(dPassYdsAtt), // Convert to number
          oRushPerGame:parseFloat(oRushPerGame), // Convert to number
           dRushPerGame:parseFloat(dRushPerGame), // Convert to number
            oPassPerGame:parseFloat(oPassPerGame), // Convert to number
             dPassPerGame:parseFloat(dPassPerGame), // Convert to number
         oYdsPerPoint:parseFloat(oYdsPerPoint), // Convert to number
          dYdsPerPoint:parseFloat(dYdsPerPoint), // Convert to number
           oPtsPerPlay:parseFloat(oPtsPerPlay), // Convert to number
            dPtsPerPlay:parseFloat(dPtsPerPlay), // Convert to number
          oPlaysGame: parseFloat(oPlaysGame), // Convert to number
          dPlaysGame:parseFloat(dPlaysGame), // Convert to number
          HomeAdv:parseFloat(HomeAdv), // Convert to number
      
        };
      });
  
     
    }
  
    return projscore;
  }



  //NCAAF STUFF  
  loadNCAAFStatsData() {
    const NCAAFStatsUrl = 'assets/NCAAF-Stats.csv';
    this.http.get(NCAAFStatsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.ncaafStats = this.parseNCAAFStats(csvData);
      })
      .catch(error => {
        console.error('Error loading NCAAF stats data:', error);
      });
  }
  

  parseNCAAFStats(csvData: string | undefined) {
    const xscore: { [team: string]: {SOS: number, oRating: number, dRating: number, YdsPlay: number, YdsPlayL3: number, wYdsPlay: number,
      dYdsPlay:number, dYdsPlayL3: number, wdYdsPlay:number, YdsPt:number, YdsPtL3:number, wYdsPt:number
      dYdsPt:number, dYdsPtL3: number, wdYdsPt:number, PlaysGame:number, dPlaysGame:number ,HomeAdv:number} } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, SOS, oRating, dRating, YdsPlay, YdsPlayL3, wYdsPlay,
          dYdsPlay, dYdsPlayL3, wdYdsPlay, YdsPt, YdsPtL3, wYdsPt,
          dYdsPt, dYdsPtL3, wdYdsPt, PlaysGame, dPlaysGame, HomeAdv] = line.trim().split(',');
        xscore[team] = {
          SOS: parseFloat(SOS), // Convert to number
          oRating: parseFloat(oRating), // Convert to number
          dRating:parseFloat(dRating), // Convert to number
          YdsPlay:parseFloat(YdsPlay),
          YdsPlayL3: parseFloat(YdsPlayL3), // Convert to number
          wYdsPlay:parseFloat(wYdsPlay), // Convert to number
          dYdsPlay:parseFloat(dYdsPlay),
          dYdsPlayL3: parseFloat(dYdsPlayL3), // Convert to number
          wdYdsPlay:parseFloat(wdYdsPlay), // Convert to number
          YdsPt:parseFloat(YdsPt),
          YdsPtL3: parseFloat(YdsPtL3), // Convert to number
          wYdsPt:parseFloat(wYdsPt), // Convert to number
          dYdsPt: parseFloat(dYdsPt),
          dYdsPtL3: parseFloat(dYdsPtL3), // Convert to number
          wdYdsPt:parseFloat(wdYdsPt), // Convert to number
          PlaysGame:parseFloat(PlaysGame),
          dPlaysGame:parseFloat(dPlaysGame),
          HomeAdv:parseFloat(HomeAdv), // Convert to number
        };
      });
  
     
    }
  
    return xscore;
  }
  


  //NBA STUFF  
  loadNBASpreadsData() {
    const nbaSpreadsUrl = 'assets/NBA-Spreads.csv';
    this.http.get(nbaSpreadsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.nbaSpreads = this.parseNBASpreads(csvData);
      })
      .catch(error => {
        console.error('Error loading NBA spreads data:', error);
      });
  }
  
  parseNBASpreads(csvData: string | undefined) {
    const spreads: { [team: string]: number } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, spread] = line.trim().split(',');
        spreads[team] = parseFloat(spread); // Convert to number
      });
  
      
    }
  
    return spreads;
  }
  



  loadNBAStatsData() {
    const NBAStatsUrl = 'assets/NBA-Stats.csv';
    this.http.get(NBAStatsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.nbaStats = this.parseNBAStats(csvData);
      })
      .catch(error => {
        console.error('Error loading NBA stats data:', error);
      });
  }
  

  parseNBAStats(csvData: string | undefined) {
    const xpoints: { [team: string]: { Off: number; oLastThree: number; oHome: number, oAway: number,
      adjO: number, Def: number, dLastThree: number, dHome: number, dAway: number, adjD: number, 
     Tempo: number, adjT: number } } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, Off, oLastThree, oHome, oAway, adjO, Def, dLastThree,
        dHome, dAway, adjD, Tempo, adjT] = line.trim().split(',');
        xpoints[team] = {
          Off: parseFloat(Off), // Convert to number
          oLastThree: parseFloat(oLastThree), // Convert to number
          oHome: parseFloat(oHome), // Convert to number
          oAway: parseFloat(oAway), // Convert to number
          adjO: parseFloat(adjO), // Convert to number
          Def: parseFloat(Def), // Convert to number
          dLastThree: parseFloat(dLastThree), // Convert to number
          dHome:  parseFloat(dHome), // Convert to number
          dAway: parseFloat(dAway), // Convert to number
          adjD: parseFloat(adjD), // Convert to number
          Tempo: parseFloat(Tempo), // Convert to number
          adjT: parseFloat(adjT), // Convert to number
        };
      });
  
      
    }
  
    return xpoints;
  }
  

// EPL Stuff



//NCAA BASEBALL STUFF

loadNCAABaseballStatsData() {
  const NCAABaseballStatsUrl = 'assets/NCAA-Baseball-Stats.csv';
  this.http.get(NCAABaseballStatsUrl, { responseType: 'text' })
    .toPromise()
    .then(csvData => {
      this.ncaaBaseballStats = this.parseNCAABaseballStats(csvData);
    })
    .catch(error => {
      console.error('Error loading NCAA Baseball stats data:', error);
    });
}


parseNCAABaseballStats(csvData: string | undefined) {
  const xRuns: { [team: string]: { R: number; RA: number; wR: number, wRA: number } } = {};

  if (csvData) {
    const lines = csvData.split('\n').slice(1); // Remove the header row

    lines.forEach(line => {
      const [team, R, RA, wR, wRA] = line.trim().split(',');
      xRuns[team] = {
        R: parseFloat(R), // Convert to number
        RA: parseFloat(RA), // Convert to number
        wR: parseFloat(wR), // Convert to number
        wRA: parseFloat(wRA), // Convert to number
      };
    });

    
  }

  return xRuns;
}


  //NCAAM STUFF  

  loadNCAAMSpreadsData() {
    const ncaamSpreadsUrl = 'assets/NCAAM-Spreads.csv';
    this.http.get(ncaamSpreadsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.ncaamSpreads = this.parseNCAAMSpreads(csvData);
      })
      .catch(error => {
        console.error('Error loading NCAAM spreads data:', error);
      });
  }
  
  parseNCAAMSpreads(csvData: string | undefined) {
    const spreads: { [team: string]: number } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, spread] = line.trim().split(',');
        spreads[team] = parseFloat(spread); // Convert to number
      });
  
      
    }
  
    return spreads;
  }
  
  
  
  loadNCAAMStatsData() {
    const ncaamStatsUrl = 'assets/NCAAM-Stats.csv';
    this.http.get(ncaamStatsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        this.ncaamStats = this.parseNCAAMStats(csvData);
      })
      .catch(error => {
        console.error('Error loading NCAAM stats data:', error);
      });
  }
  
  parseNCAAMStats(csvData: string | undefined) {
    const xpoints: { [team: string]: { adjO: number; adjD: number; adjT: number,
      ORank: number, DRank: number, TRank: number, HomeAdv: number } } = {};
  
    if (csvData) {
      const lines = csvData.split('\n').slice(1); // Remove the header row
  
      lines.forEach(line => {
        const [team, adjO, adjD, adjT, ORank, DRank, TRank, HomeAdv] = line.trim().split(',');
        xpoints[team] = {
          adjO: parseFloat(adjO), // Convert to number
          adjD: parseFloat(adjD), // Convert to number
          adjT: parseFloat(adjT), // Convert to number
          ORank: parseFloat(ORank), // Convert to number
          DRank: parseFloat(DRank), // Convert to number
          TRank: parseFloat(TRank), // Convert to number
          HomeAdv: parseFloat(HomeAdv), // Convert to number
        };
      });
  
      
    }
  
    return xpoints;
  }
  
//MLB STUFF


loadMLBPitchersData() {
  const mlbPitchersUrl = 'assets/MLB-Pitchers.csv';
  this.http
    .get(mlbPitchersUrl, { responseType: 'text' })
    .toPromise()
    .then(csvData => {
      if (csvData) {
      this.pitchersList = this.parseMLBPitchers(csvData);
    }
  })
    .catch(error => {
      console.error('Error loading MLB pitchers data:', error);
    });
}  


parseMLBPitchers(csvData: string) {
  const pitchersList: Pitcher[] = [];

  if (csvData) {
    const lines = csvData.split('\n').slice(1); // Remove the header row

    lines.forEach(line => {
      const [name, k_percent, bb_percent, xba, xslg, xobp, single_percent, double_percent, triple_percent, home_run_percent, pa_per_game, hand] = line.trim().split(',');
      const pitcher: Pitcher = {
        name,
        k_percent: parseFloat(k_percent),
        bb_percent: parseFloat(bb_percent),
        xba: parseFloat(xba),
        xslg: parseFloat(xslg),
        xobp: parseFloat(xobp),
        single_percent: parseFloat(single_percent),
        double_percent: parseFloat(double_percent),
        triple_percent: parseFloat(triple_percent),
        home_run_percent: parseFloat(home_run_percent),
        pa_per_game: parseFloat(pa_per_game),
        hand
        // Add additional properties here based on the data structure of your CSV file
      };
      pitchersList.push(pitcher);
    });
  }
  return pitchersList;
}

loadMLBHittersData() {
  const mlbHittersUrl = 'assets/MLB-Hitters.csv';
  this.http
    .get(mlbHittersUrl, { responseType: 'text' })
    .toPromise()
    .then(csvData => {
      if (csvData) {
      this.HittersList = this.parseMLBHitters(csvData);
    }
  })
    .catch(error => {
      console.error('Error loading MLB Hitters data:', error);
    });
}  

parseMLBHitters(csvData: string) {
  const hittersList: Hitter[] = [];

  if (csvData) {
    const lines = csvData.split('\n').slice(1); // Remove the header row

    lines.forEach(line => {
      const [name, k_percent, bb_percent, xba, xslg, xobp, single_percent, double_percent, triple_percent, home_run_percent, xOPS, wRops, wLops] = line.trim().split(',');
      const hitter: Hitter = {
        name,
        k_percent: parseFloat(k_percent),
        bb_percent: parseFloat(bb_percent),
        xba: parseFloat(xba),
        xslg: parseFloat(xslg),
        xobp: parseFloat(xobp),
        single_percent: parseFloat(single_percent),
        double_percent: parseFloat(double_percent),
        triple_percent: parseFloat(triple_percent),
        home_run_percent: parseFloat(home_run_percent),
        xOPS: parseFloat(xOPS),
        wRops: parseFloat(wRops),
        wLops: parseFloat(wLops),
        // Add additional properties here based on the data structure of your CSV file
      };
      hittersList.push(hitter);
    });
  }
  
  return hittersList;
}


// Load MLB Ballparks data
loadMLBBallparksData() {
  const MLBBallparksUrl = 'assets/MLB-Ballparks.csv';
  this.http.get(MLBBallparksUrl, { responseType: 'text' })
    .toPromise()
    .then(csvData => {
      this.ballparkFactors = this.parseMLBBallparksData(csvData);
    })
    .catch(error => {
      console.error('Error loading Ballparks data:', error);
    });
}



// Parse MLB Ballparks data
parseMLBBallparksData(csvData: string | undefined): BallparkFactors {
  const parks: BallparkFactors = {};

  if (csvData) {
    const lines = csvData.split('\n').slice(1); // Remove the header row

    lines.forEach(line => {
      const [team, w1B, w2B, w3B, wHR, wBB, wSO, wRest, wOBP, TB_R] = line.trim().split(',');
      parks[team] = {
        w1B: parseFloat(w1B),
        w2B: parseFloat(w2B),
        w3B: parseFloat(w3B),
        wHR: parseFloat(wHR),
        wBB: parseFloat(wBB),
        wSO: parseFloat(wSO),
        wRest: parseFloat(wRest),
        wOBP: parseFloat(wOBP),
        TB_R: parseFloat(TB_R)
      };
    });
  }

  return parks;
}

onSportSelected(sport: string) {
  this.selectedSport = sport;
  this.updateTeams(); // Update teams when sport changes
  this.resetScores();
}

onTeamSelected(team: string){
  const homeTeamName = this.selectedHomeTeam
  const awayTeamName = this.selectedAwayTeam
}

  
  
// NHL STUFF

parseNHLOdds(csvData: string | undefined): Record<string, number> {
  if (!csvData) {
    // Handle the case where csvData is undefined (e.g., show an error or return an empty object)
    console.error('CSV data is undefined');
    return {};
  }

  const lines = csvData.split('\n');
  const odds: Record<string, number> = {};

  for (const line of lines) {
    const [team, oddsStr] = line.split(',');
    const oddsValue = parseFloat(oddsStr);
    odds[team.trim()] = oddsValue;
  }

  return odds;
}



loadNHLGoaliesData() {
  const nhlGoaliesUrl = 'assets/NHL-Goalies.csv';
  this.http.get(nhlGoaliesUrl, { responseType: 'text' })
    .toPromise()
    .then(csvData => {
      if (csvData) {
        this.goaliesList = this.parseNHLGoalies(csvData);
      }
    })
    .catch(error => {
      console.error('Error loading NHL goalies data:', error);
    });
}

parseNHLGoalies(csvData: string) {
  const goaliesList: Goalie[] = [];

  if (csvData) {
    const lines = csvData.split('\n').slice(1); // Remove the header row

    lines.forEach(line => {
      const [name, gaaStr, svStr] = line.trim().split(','); // Split using comma as delimiter

      // Convert GAA and SV to numbers
      const gaa = parseFloat(gaaStr);
      const sv = parseFloat(svStr);

      // Check if conversion was successful
      if (!isNaN(gaa) && !isNaN(sv)) {
        goaliesList.push({ name, gaa, sv });
      }
    });
  }

  
  return goaliesList;
}

topPicks = [
  {
    rank: 1,
    matchup: 'Yankees vs Athletics',
    prediction: 'Yankees 5.2 - 3.1',
    confidence: 'Elite'
  },
  {
    rank: 2,
    matchup: 'Dodgers vs Giants',
    prediction: 'Dodgers 6.0 - 4.3',
    confidence: 'Strong'
  },
  {
    rank: 3,
    matchup: 'Phillies vs Mets',
    prediction: 'Phillies 4.8 - 4.0',
    confidence: 'Lean'
  }
];
topProps: any[] = []; 


 //NCAAM STUFF  
 loadNHLStatsData() {
  const nhlStatsUrl = 'assets/NHL-Stats.csv';
  this.http.get(nhlStatsUrl, { responseType: 'text' })
    .toPromise()
    .then(csvData => {
      this.nhlstats = this.parseNHLStats(csvData);
    })
    .catch(error => {
      console.error('Error loading NHL stats data:', error);
    });
}

parseNHLStats(csvData: string | undefined) {
  const xgoals: { [team: string]: { ShotsF:number, PP:number, ShotsA:number, S:number } } = {};

  if (csvData) {
    const lines = csvData.split('\n').slice(1); // Remove the header row

    lines.forEach(line => {
      const [team, ShotsF, PP, ShotsA, S] = line.trim().split(',');
      xgoals[team] = {
        ShotsF: parseFloat(ShotsF), // Convert to number
        PP: parseFloat(PP), // Convert to number
        ShotsA: parseFloat(ShotsA), // Convert to number
        S: parseFloat(S), // Convert to number
      };
    });

    
  }

  return xgoals;
}

  updateTeams() {
    this.homeTeams = this.sportsTeams[this.selectedSport] || [];
    this.awayTeams = this.sportsTeams[this.selectedSport] || [];
    this.selectedHomeTeam = this.homeTeams[0] || '';
    this.selectedAwayTeam = this.awayTeams[0] || '';
    this.searchTextHomeTeam = this.selectedHomeTeam;
    this.searchTextAwayTeam = this.selectedAwayTeam;
    this.filteredHomeTeams = [...this.homeTeams];
    this.filteredAwayTeams = [...this.awayTeams];
    this.selectedHomePitcher = '';
    this.selectedAwayPitcher = '';
  }

  generateRandomNumber(min: number, max: number) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }



  openPlayerProps() {
    this.showPlayerProps = !this.showPlayerProps;
  
    if (this.playerProps.length === 0) {
      this.loadPlayerProps();
    }
  }

  loadPlayerProps() {
    this.http.get(environment.mlbPlayerPropsUrl, { responseType: 'text' })
      .subscribe(data => {
        Papa.parse(data, {
          header: true,
          dynamicTyping: true,
      complete: result => {
  this.playerProps = result.data;
  this.sortedProps = [...this.playerProps];

  this.generateTopProps();
}
        });
      });
  }
  generateTopProps() {

  this.topProps = [...this.playerProps]

    // Remove blank rows
    .filter(player => player.Hitters)

    // Sort highest xBases first
    .sort((a, b) => b.xBases - a.xBases)

    // Take top 5
    .slice(0, 5)

    // Format for homepage display
    .map((player, index) => ({
      rank: index + 1,
      name: player.Hitters,
      hitPercent: (player['Hit%'] * 100).toFixed(0) + '%',
      hrPercent: (player['Homer %'] * 100).toFixed(0) + '%',
      xBases: Number(player.xBases).toFixed(2)
    }));
}
  sortTable(column: string) {
    const currentDirection = this.sortDirection[column];
  
    // Default: first click sorts descending (highest to lowest)
    const newDirection = currentDirection === 'desc' ? 'asc' : 'desc';
    this.sortDirection = { [column]: newDirection }; // clear others
  
    this.sortedProps.sort((a, b) => {
      const valA = a[column];
      const valB = b[column];
  
      if (valA < valB) return newDirection === 'asc' ? -1 : 1;
      if (valA > valB) return newDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }
  
  
  

  async runSimulation() {
    switch (this.selectedSport) {
      
      case 'NFL':
   const homeTeamNFL = this.nflstats[this.selectedHomeTeam];
   const awayTeamNFL = this.nflstats[this.selectedAwayTeam];
   if (homeTeamNFL && awayTeamNFL) {
    // Calculate various intermediate values
    const HrYdsAtt = (.85 * homeTeamNFL.RushYdsAtt * (awayTeamNFL.dRushYdsAtt / 4.44))+(.15* 4.44); //4.45 = avg
    const ArYdsAtt = (.85 * awayTeamNFL.RushYdsAtt * (homeTeamNFL.dRushYdsAtt / 4.44)) + (.15* 4.44); //4.45 = avg
    const HrAtt = (.85 * homeTeamNFL.oRushPerGame * (awayTeamNFL.dRushPerGame / 26.95)) + (.15* 26.95); //27.2 avg
    const ArAtt = (.85 * awayTeamNFL.oRushPerGame * (homeTeamNFL.dRushPerGame / 26.95)) + (.15*26.95); //27.2 avg
    const hRushYds = HrYdsAtt * HrAtt;
    const aRushYds = ArYdsAtt * ArAtt;
    const HpYdsAtt = (.85 * homeTeamNFL.PassYdsAtt * (awayTeamNFL.dPassYdsAtt / 7.175)) + (.15* 7.175); //6.55 = avg
    const ApYdsAtt = (.85 * awayTeamNFL.PassYdsAtt * (homeTeamNFL.dPassYdsAtt / 7.175)) + (.15 * 7.175); //6.55 = avg
    const HpAtt = (.85 * homeTeamNFL.oPassPerGame * (awayTeamNFL.dPassPerGame / 32.69)) + (.15 * 32.69); //33.42 avg
    const ApAtt = (.85 * awayTeamNFL.oPassPerGame * (homeTeamNFL.dPassPerGame / 32.69)) + (.15* 32.69); //33.42 avg
    const hPassYds = HpYdsAtt * HpAtt;
    const aPassYds = ApYdsAtt * ApAtt;
    const homeAdvModifier = this.isNeutralSite ? 0 : homeTeamNFL.HomeAdv/2;
    const hTotalYds = hPassYds + hRushYds;
    const aTotalYds = aPassYds + aRushYds;
    const HoYP = (.85 * homeTeamNFL.oYdsPerPoint * (awayTeamNFL.dYdsPerPoint / 15.053)) + (.15* 15.053); //15.55 = avg
    const AoYP = (.85 * awayTeamNFL.oYdsPerPoint * (homeTeamNFL.dYdsPerPoint / 15.053)) + (.15 * 15.053); //15.55 = avg
    const hYdsScore = hTotalYds / HoYP;
    const AYdsScore = aTotalYds / AoYP;
    const HoPPlay = (.85 * homeTeamNFL.oPtsPerPlay * (awayTeamNFL.dPtsPerPlay / 0.3715)) + (.15 * .3715); // .3493 avg
    const AoPPlay = (.85 * awayTeamNFL.oPtsPerPlay * (homeTeamNFL.dPtsPerPlay / 0.3715)) + (.15 * .3715); // .3493 avg
    const hPlaysGame = (.85 * homeTeamNFL.oPlaysGame * (awayTeamNFL.dPlaysGame / 62.084)) + (.15* 62.084); //63.04 avg
    const aPlaysGame = (.85 * awayTeamNFL.oPlaysGame * (homeTeamNFL.dPlaysGame / 62.084)) + (.15* 62.084); //63.04 avg
    const hPlaysScore = HoPPlay * hPlaysGame;
    const aPlaysScore = AoPPlay * aPlaysGame;
   


    // Calculate the home team's total score
    this.homeTeamScore = Math.floor(((hYdsScore + hPlaysScore) / 2) + homeAdvModifier);

    // Calculate the away team's total score
    this.awayTeamScore = Math.floor(((AYdsScore + aPlaysScore) / 2) - homeAdvModifier);
  }

  this.showDetailsButton = true;
  break;
  
      
      case 'NHL':
        const nhlOddsUrl = 'assets/NHL-Odds.csv';
        this.http.get(nhlOddsUrl, { responseType: 'text' })
          .toPromise()
          .then(csvData => {
            this.nhlOdds = this.parseNHLOdds(csvData);
          })
          .catch(error => {
            console.error('Error loading NHL odds data:', error);
          });
  const selectedHomeGoalieData = this.goaliesList.find(goalie => goalie.name === this.selectedHomeGoalie);
  const selectedAwayGoalieData = this.goaliesList.find(goalie => goalie.name === this.selectedAwayGoalie);

  if (selectedHomeGoalieData && selectedAwayGoalieData) {
    const nhlStatsUrl = 'assets/NHL-Stats.csv';
    this.http.get(nhlStatsUrl, { responseType: 'text' })
      .toPromise()
      .then(csvData => {
        const xGoals = this.parseNHLStats(csvData);

        // Calculate xShots for home team and away team
        const homeTeamStats = this.nhlstats[this.selectedHomeTeam];
        const awayTeamStats = this.nhlstats[this.selectedAwayTeam];
        
        const xShotsHome = homeTeamStats.ShotsF * (awayTeamStats.ShotsA / 28.25);
        const xShotsAway = awayTeamStats.ShotsF * (homeTeamStats.ShotsA / 28.25);
console.log(xShotsHome, )
        // Calculate scores based on selected goalies, xGoals, and xShots
        this.homeTeamScore = Number(((-3.16 + (0.01 * homeTeamStats.PP) + (0.1 * xShotsHome) + (0.31 * (homeTeamStats.S + ((1 - selectedAwayGoalieData.sv) * 100)) / 2) + (0.03 * selectedAwayGoalieData.gaa))).toFixed(2));
        this.awayTeamScore = Number(((-3.16 + (0.01 * awayTeamStats.PP) + (0.1 * xShotsAway) + (0.31 * (awayTeamStats.S + ((1 - selectedHomeGoalieData.sv) * 100)) / 2) + (0.03 * selectedHomeGoalieData.gaa))).toFixed(2));
      })
      
    
      .catch(error => {
        console.error('Error loading NHL stats data:', error);
      });
  }


  this.showDetailsButton = true;
  break;

        case 'MLB':
          const homeBatters = [];
          const awayBatters = [];
          const ParkFactor = this.ballparkFactors[this.selectedHomeTeam];
          const AwayTeam = this.ballparkFactors[this.selectedAwayTeam];
  

          
          
        
          const LG_AVG_PITCHER: Pitcher = {
            name: '', k_percent: 22.7, bb_percent: 8.3, xba: 0.248, xslg: 0.394, xobp: 0.320,
            single_percent: 0.1343, double_percent: 0.0409, triple_percent: 0.00367,
            home_run_percent: 0.02555, pa_per_game: 27.0, hand: 'R'
          };
          const LG_AVG_BATTER: Hitter = {
            name: '', k_percent: 22.7, bb_percent: 8.3, xba: 0.248, xslg: 0.394, xobp: 0.320,
            single_percent: 0.1343, double_percent: 0.0409, triple_percent: 0.00367,
            home_run_percent: 0.02555, xOPS: 0.714, wRops: 1.0, wLops: 1.0
          };
          const fillPitcher = (p: Pitcher | undefined): Pitcher => {
            if (!p) return LG_AVG_PITCHER;
            return {
              ...p,
              xba:           p.xba           || LG_AVG_PITCHER.xba,
              xslg:          p.xslg          || LG_AVG_PITCHER.xslg,
              xobp:          p.xobp          || LG_AVG_PITCHER.xobp,
              single_percent:   p.single_percent   || LG_AVG_PITCHER.single_percent,
              double_percent:   p.double_percent   || LG_AVG_PITCHER.double_percent,
              triple_percent:   p.triple_percent   || LG_AVG_PITCHER.triple_percent,
              home_run_percent: p.home_run_percent || LG_AVG_PITCHER.home_run_percent,
              k_percent:     p.k_percent     || LG_AVG_PITCHER.k_percent,
              bb_percent:    p.bb_percent    || LG_AVG_PITCHER.bb_percent,
            };
          };
          const fillBatter = (b: Hitter): Hitter => ({
            ...b,
            xba:             b.xba             || LG_AVG_BATTER.xba,
            xslg:            b.xslg            || LG_AVG_BATTER.xslg,
            xobp:            b.xobp            || LG_AVG_BATTER.xobp,
            single_percent:  b.single_percent  || LG_AVG_BATTER.single_percent,
            double_percent:  b.double_percent  || LG_AVG_BATTER.double_percent,
            triple_percent:  b.triple_percent  || LG_AVG_BATTER.triple_percent,
            home_run_percent:b.home_run_percent|| LG_AVG_BATTER.home_run_percent,
            k_percent:       b.k_percent       || LG_AVG_BATTER.k_percent,
            bb_percent:      b.bb_percent      || LG_AVG_BATTER.bb_percent,
          });

          for (let i = 1; i <= 9; i++) {
            const homeLineupName = this.asciiNorm(this.mlbLineups[this.selectedHomeTeam + i]?.[0] || '');
            const awayLineupName = this.asciiNorm(this.mlbLineups[this.selectedAwayTeam + i]?.[0] || '');
            const homeBatter = fillBatter(this.HittersList.find(p => this.asciiNorm(p.name) === homeLineupName) ?? LG_AVG_BATTER);
            const awayBatter = fillBatter(this.HittersList.find(p => this.asciiNorm(p.name) === awayLineupName) ?? LG_AVG_BATTER);
            homeBatters.push(homeBatter);
            awayBatters.push(awayBatter);
          }
          const homePitcher = fillPitcher(this.pitchersList.find(player => player.name === this.selectedHomePitcher));
          const awayPitcher = fillPitcher(this.pitchersList.find(player => player.name === this.selectedAwayPitcher));
          
  
const homePitcherHandedness = homePitcher?.hand;
const awayPitcherHandedness = awayPitcher?.hand;
const PA = [4.65, 4.55, 4.43, 4.33, 4.24, 4.13, 4.01, 3.9, 3.77];

// ── SINGLES ───────────────────────────────────────────────────────────────────
const HomeSingle: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomeSingle.push(this.log5(Number(homeBatters[i]?.single_percent), Number(awayPitcher?.single_percent), 0.13425) * platoon * ParkFactor.w1B);
}
const awaySingle: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awaySingle.push(this.log5(Number(awayBatters[i]?.single_percent), Number(homePitcher?.single_percent), 0.13425) * platoon * ParkFactor.w1B);
}

// ── DOUBLES ───────────────────────────────────────────────────────────────────
const HomeDouble: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomeDouble.push(this.log5(Number(homeBatters[i]?.double_percent), Number(awayPitcher?.double_percent), 0.0409) * platoon * ParkFactor.w2B);
}
const awayDouble: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awayDouble.push(this.log5(Number(awayBatters[i]?.double_percent), Number(homePitcher?.double_percent), 0.0409) * platoon * ParkFactor.w2B);
}

// ── TRIPLES ───────────────────────────────────────────────────────────────────
const HomeTriple: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomeTriple.push(this.log5(Number(homeBatters[i]?.triple_percent), Number(awayPitcher?.triple_percent), 0.00367) * platoon * ParkFactor.w3B);
}
const awayTriple: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awayTriple.push(this.log5(Number(awayBatters[i]?.triple_percent), Number(homePitcher?.triple_percent), 0.00367) * platoon * ParkFactor.w3B);
}

// ── HOME RUNS ─────────────────────────────────────────────────────────────────
const HomeHR: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomeHR.push(this.log5(Number(homeBatters[i]?.home_run_percent), Number(awayPitcher?.home_run_percent), 0.02555) * platoon * ParkFactor.wHR);
}
const awayHR: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awayHR.push(this.log5(Number(awayBatters[i]?.home_run_percent), Number(homePitcher?.home_run_percent), 0.02555) * platoon * ParkFactor.wHR);
}

// ── STRIKEOUTS (platoon reversed: same-hand = disadvantage for batter) ────────
const HomeK: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wLops) : Number(homeBatters[i]?.wRops);
  HomeK.push(this.log5(Number(homeBatters[i]?.k_percent) / 100, Number(awayPitcher?.k_percent) / 100, 0.21377) * platoon * ParkFactor.wSO);
}
const awayK: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wLops) : Number(awayBatters[i]?.wRops);
  awayK.push(this.log5(Number(awayBatters[i]?.k_percent) / 100, Number(homePitcher?.k_percent) / 100, 0.21377) * platoon * ParkFactor.wSO);
}

this.HomeSPK = Number(homePitcher?.pa_per_game) / 9 * awayK.reduce((s, v) => s + v, 0);
this.AwaySPK = Number(awayPitcher?.pa_per_game) / 9 * HomeK.reduce((s, v) => s + v, 0);

// ── WALKS & AT-BATS ───────────────────────────────────────────────────────────
const HomeBB: number[] = [];
const HomeAB: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  const bb = this.log5(Number(homeBatters[i]?.bb_percent) / 100, Number(awayPitcher?.bb_percent) / 100, 0.093317) * platoon * ParkFactor.wBB;
  HomeBB.push(bb);
  HomeAB.push(PA[i] * (1 - bb));
}
const awayBB: number[] = [];
const awayAB: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  const bb = this.log5(Number(awayBatters[i]?.bb_percent) / 100, Number(homePitcher?.bb_percent) / 100, 0.093317) * platoon * ParkFactor.wBB;
  awayBB.push(bb);
  awayAB.push(PA[i] * (1 - bb));
}

// ── xBA (log5; park via wRest) ────────────────────────────────────────────────
const HomexbaValues: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomexbaValues.push(this.log5(Number(homeBatters[i]?.xba), Number(awayPitcher?.xba), 0.2407) * platoon * ParkFactor.wRest);
}
const awayXbaValues: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awayXbaValues.push(this.log5(Number(awayBatters[i]?.xba), Number(homePitcher?.xba), 0.2407) * platoon * ParkFactor.wRest);
}

// ── xSLG (multiplicative; NO extra park factor — event rates already park-adjusted) ──
const HomeXslg: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomeXslg.push((Number(homeBatters[i]?.xslg) * (Number(awayPitcher?.xslg) / 0.3878)) * platoon);
}
const awayXslg: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awayXslg.push((Number(awayBatters[i]?.xslg) * (Number(homePitcher?.xslg) / 0.3878)) * platoon);
}

// ── xOBP ─────────────────────────────────────────────────────────────────────
const HomeXobp: number[] = [];
for (let i = 0; i < homeBatters.length; i++) {
  const platoon = awayPitcherHandedness === 'R' ? Number(homeBatters[i]?.wRops) : Number(homeBatters[i]?.wLops);
  HomeXobp.push((Number(homeBatters[i]?.xobp) * (Number(awayPitcher?.xobp) / 0.320657)) * platoon * ParkFactor.wOBP);
}
const awayXobp: number[] = [];
for (let i = 0; i < awayBatters.length; i++) {
  const platoon = homePitcherHandedness === 'R' ? Number(awayBatters[i]?.wRops) : Number(awayBatters[i]?.wLops);
  awayXobp.push((Number(awayBatters[i]?.xobp) * (Number(homePitcher?.xobp) / 0.320657)) * platoon * ParkFactor.wOBP);
}


// Define arrays to store hit percentages
const homeHitPercent: number[] = [];
const awayHitPercent: number[] = [];

// Loop through home batters and calculate hit percentage for each
for (let i = 0; i < homeBatters.length; i++) {
  const hitPercent = Math.round((0.65 * (1 - Math.pow(1 - HomexbaValues[i], HomeAB[i])) + 0.35 * (1 - Math.pow(1 - (HomeSingle[i] + HomeDouble[i] + HomeTriple[i] + HomeHR[i]), PA[i]))) * 100);
  homeHitPercent.push(hitPercent);
}


// Loop through away batters and calculate hit percentage for each
for (let i = 0; i < awayBatters.length; i++) {
  const hitPercent = Math.round((0.65 * (1 - Math.pow(1 - awayXbaValues[i], awayAB[i])) + 0.35 * (1 - Math.pow(1 - (awaySingle[i] + awayDouble[i] + awayTriple[i] + awayHR[i]), PA[i]))) * 100);
  awayHitPercent.push(hitPercent);
}

this.homeHitPercent = homeHitPercent
this.awayHitPercent = awayHitPercent

// Define arrays to store xBases
const homexBases: number[] = [];
const awayxBases: number[] = [];

// Build xBases arrays for display (unchanged formula)
for (let i = 0; i < homeBatters.length; i++) {
  const xBases = Number(((HomeXslg[i] * HomeAB[i]) + ((HomeSingle[i] + (HomeDouble[i] * 2) + (HomeTriple[i] * 3) + (HomeHR[i] * 4)) * PA[i])) / 2 - 0.19).toFixed(2);
  homexBases.push(Number(xBases));
}
for (let i = 0; i < awayBatters.length; i++) {
  const xBases = Number(((awayXslg[i] * awayAB[i]) + ((awaySingle[i] + (awayDouble[i] * 2) + (awayTriple[i] * 3) + (awayHR[i] * 4)) * PA[i])) / 2 - 0.19).toFixed(2);
  awayxBases.push(Number(xBases));
}

// wOBA linear weights → expected runs
// Scale factor 0.411 calibrates sum to ~4.5 R/G for a league-average matchup.
// 0.15 run home field advantage applied to home team.
const LW_BB = 0.69, LW_1B = 0.89, LW_2B = 1.27, LW_3B = 1.62, LW_HR = 2.10;
const WOBA_SCALE = 0.411;

let homeWobaNum = 0;
let awayWobaNum = 0;
for (let i = 0; i < 9; i++) {
  homeWobaNum += PA[i] * (HomeBB[i] * LW_BB + HomeSingle[i] * LW_1B + HomeDouble[i] * LW_2B + HomeTriple[i] * LW_3B + HomeHR[i] * LW_HR);
  awayWobaNum += PA[i] * (awayBB[i] * LW_BB + awaySingle[i] * LW_1B + awayDouble[i] * LW_2B + awayTriple[i] * LW_3B + awayHR[i] * LW_HR);
}

this.homeTeamScore = +(homeWobaNum * WOBA_SCALE + 0.15).toFixed(2);
this.awayTeamScore = +(awayWobaNum * WOBA_SCALE).toFixed(2);

// Assign the arrays to component properties
this.homexBases = homexBases;
this.awayxBases = awayxBases;

console.log(awaySingle[0],awayDouble[0],awayTriple[0],awayHR[0],awayK[0], awayBB[0],awayXbaValues[0],awayXobp[0],awayXslg[0])


  break;
    
      case 'NBA':
        const homeTeamNBA = this.nbaStats[this.selectedHomeTeam];
          const awayTeamNBA = this.nbaStats[this.selectedAwayTeam];
          if (homeTeamNBA && awayTeamNBA) {
            const Poss = (homeTeamNBA.Tempo * awayTeamNBA.adjT);
            const homeAdvModifier = this.isNeutralSite ? 0 : 1.1;
            const HomeOEff = (homeTeamNBA.Off * .17) + (0.18 * homeTeamNBA.oLastThree)+ (0.15 * homeTeamNBA.oHome)
            const AwayDEff = (awayTeamNBA.Def * .17) + (0.18 * awayTeamNBA.dLastThree)+ (0.15 * awayTeamNBA.dAway)
            const AwayOEff = (awayTeamNBA.Off * .17) + (0.18 * awayTeamNBA.oLastThree)+ (0.15 * awayTeamNBA.oAway)
            const HomeDEff = (homeTeamNBA.Def * .17) + (0.18 * homeTeamNBA.dLastThree)+ (0.15 * homeTeamNBA.dHome)
        
            // Calculate the home team's total score
            this.homeTeamScore = Math.floor(((HomeOEff * awayTeamNBA.adjD) + 
            (AwayDEff * homeTeamNBA.adjO)) * Poss + homeAdvModifier)
        
            // Calculate the away team's total score
            this.awayTeamScore = Math.floor(((AwayOEff * homeTeamNBA.adjD) + 
            (HomeDEff * awayTeamNBA.adjO)) * Poss - homeAdvModifier)
          }
        this.showDetailsButton = true
          break;
        
      case 'NCAAF':
            const homeTeamNCAAF = this.ncaafStats[this.selectedHomeTeam];
            const awayTeamNCAAF = this.ncaafStats[this.selectedAwayTeam];
            if (homeTeamNCAAF && awayTeamNCAAF) {
              const homeAdvModifier = this.isNeutralSite ? 0 : homeTeamNCAAF.HomeAdv/2;
              
              // Calculate the home team's total score
              this.homeTeamScore = +(
                (((0.5 * (homeTeamNCAAF.wYdsPlay * awayTeamNCAAF.dRating)) + (0.5 * (awayTeamNCAAF.wdYdsPlay*homeTeamNCAAF.oRating))) * (homeTeamNCAAF.PlaysGame*(awayTeamNCAAF.dPlaysGame/68)))
              / ((awayTeamNCAAF.wdYdsPt+homeTeamNCAAF.wYdsPt)/2) + homeAdvModifier + 1.74)
              .toFixed(2);
          
              // Calculate the away team's total score
              this.awayTeamScore = +(
                (((0.5 * (awayTeamNCAAF.wYdsPlay * homeTeamNCAAF.dRating)) + (0.5 * (homeTeamNCAAF.wdYdsPlay*awayTeamNCAAF.oRating))) * (awayTeamNCAAF.PlaysGame*(homeTeamNCAAF.dPlaysGame/68)))
                / ((homeTeamNCAAF.wdYdsPt+awayTeamNCAAF.wYdsPt)/2) -  homeAdvModifier + 1.74)
                .toFixed(2);
            }
    
            this.showDetailsButton = true;
            break;
          
      case 'NCAAM':
          const homeTeamStats = this.ncaamStats[this.selectedHomeTeam];
          const awayTeamStats = this.ncaamStats[this.selectedAwayTeam];
          if (homeTeamStats && awayTeamStats) {
            const averageAdjT = (homeTeamStats.adjT * awayTeamStats.TRank);
            const homeAdvModifier = this.isNeutralSite ? 0 : homeTeamStats.HomeAdv / 2;
        
            // Calculate the home team's total score
            this.homeTeamScore = Math.floor(((homeTeamStats.adjO * awayTeamStats.DRank) / 100) * averageAdjT + homeAdvModifier + 0.7);
        
            // Calculate the away team's total score
            this.awayTeamScore = Math.floor(((awayTeamStats.adjO * homeTeamStats.DRank) / 100) * averageAdjT - homeAdvModifier + 0.7);
          }
          this.showDetailsButton = true;
          break;

      
            
      case 'NCAA-Baseball':
  const homeTeamNCAABaseball = this.ncaaBaseballStats[this.selectedHomeTeam];
  const awayTeamNCAABaseball = this.ncaaBaseballStats[this.selectedAwayTeam];
  if (homeTeamNCAABaseball && awayTeamNCAABaseball) {
    // Calculate the home team's total score   1.05 Home Team 0.95 Away Team, Fix after OMAHA
    this.homeTeamScore = Number(((((homeTeamNCAABaseball.R * awayTeamNCAABaseball.wRA) + (awayTeamNCAABaseball.RA * homeTeamNCAABaseball.wR)) / 2)).toFixed(2));
    // Calculate the away team's total score
    this.awayTeamScore = Number(((((awayTeamNCAABaseball.R * homeTeamNCAABaseball.wRA) + (homeTeamNCAABaseball.RA * awayTeamNCAABaseball.wR)) / 2)).toFixed(2)); 
  }
  this.showDetailsButton = true;
  break;

          
       

        default:
          this.homeTeamScore = 0;
          this.awayTeamScore = 0;
          break;
  }
  // await this.savePrediction();  //REMOVE THIS LINE BEFORE DEPLOYING
}

openDetailsPopup() {
  // Calculate the winner
  const winner: string = this.homeTeamScore > this.awayTeamScore ? this.selectedHomeTeam : this.selectedAwayTeam;

// NCAAM Spreads
const winnerSpread = this.ncaamSpreads[winner];
const spreadText = winnerSpread ? `Actual Spread: ${winner} ${winnerSpread > 0 ? '+' : ''}${winnerSpread}` : '';



  // Calculate the winning percentage (ensure it's above 50%)
  const totalScore = Math.round(this.homeTeamScore + this.awayTeamScore);
  let winningPercentage: number;

  if (this.selectedSport === 'NHL') {
    if (winner === this.selectedHomeTeam) {
      winningPercentage = 100 - Math.round(48.25 + 14.80869 * this.awayTeamScore + (-14.34707871 * this.homeTeamScore));
    } else {
      winningPercentage = Math.round(48.25 + 14.80869 * this.awayTeamScore + (-14.34707871 * this.homeTeamScore));
    }
  // } else if (this.selectedSport === 'EPL') {
  //       winningPercentage =  Math.round(12.9897 + 26.11665 * this.homeTeamScore + (-9.4232 * this.awayTeamScore));
    
  } else if (this.selectedSport === 'NCAAM') {
    // Calculate winning percentage for NCAAM
    if (winner === this.selectedHomeTeam) {
    winningPercentage = Math.round(100 * (0.495911 + 0.02832 * (this.homeTeamScore - this.awayTeamScore)));
    } else {
      winningPercentage = Math.round(100 * (0.495911 + 0.02832 * (this.awayTeamScore - this.homeTeamScore)));
    }
  } else if (this.selectedSport === 'MLB') {
    // Calculate winning percentage for NCAAM
    if (winner === this.selectedHomeTeam) {
    winningPercentage = 100 - Math.round(48.25 + (14.80869004 * this.awayTeamScore) + (-14.34707871  *this.homeTeamScore));
    } else {
      winningPercentage = Math.round(48.25 + (14.80869004 * this.awayTeamScore) + (-14.34707871  *this.homeTeamScore));
    }
  } else if (this.selectedSport === 'NBA') {
    // Calculate winning percentage for NBA
    if (winner === this.selectedHomeTeam) {
    winningPercentage = Math.round(100 * (0.495911 + 0.02832 * (this.homeTeamScore - this.awayTeamScore)));
    
  } else {
      winningPercentage = Math.round(100 * (0.495911 + 0.02832 * (this.awayTeamScore - this.homeTeamScore)));
    }
  } else {
    if (winner === this.selectedHomeTeam) {
      winningPercentage = Math.round((this.homeTeamScore / totalScore) * 100);
    } else {
      winningPercentage = Math.round((this.awayTeamScore / totalScore) * 100);
    }
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

  

  // NHL ODDS
  const WinnerOdds = this.nhlOdds[winner];
  const oddsText = WinnerOdds ? `Actual Odds: ${winner} ${WinnerOdds > 0 ? '+' : ''}${WinnerOdds}` : '';
 
  // NBASpreads
  const winnerSpreadNBA = this.nbaSpreads[winner];
  const NBAspreadText = winnerSpreadNBA ? `Actual Spread: ${winner} ${winnerSpreadNBA > 0 ? '+' : ''}${winnerSpreadNBA}` : '';


  // NFLSpreads
  const winnerSpreadNFL = this.nflSpreads[winner];
  const NFLspreadText = winnerSpreadNFL ? `Actual Spread: ${winner} ${winnerSpreadNFL > 0 ? '+' : ''}${winnerSpreadNFL}` : '';


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
      ncaamSpreads: this.ncaamSpreads,
      nhlOdds: this.nhlOdds,
      spreadText,
      NBAspreadText,
      NFLspreadText,
      oddsText,
      homeSPK: this.HomeSPK,  // Include HomeSPK
      awaySPK: this.AwaySPK,   // Include AwaySPK
      selectedHomePitcher: this.selectedHomePitcher,
      selectedAwayPitcher: this.selectedAwayPitcher,
      selectedSport: this.selectedSport
    },
    
    
    panelClass: 'scoreboard-popup' // Apply the custom CSS class
  });
}
async savePrediction() {
  const gameData = {
    sport: this.selectedSport,
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

// Function to check if the predicted winner matches the actual winner
isPredictionCorrect(game: any): boolean {
  if (game.actualHomeScore == Number || game.actualAwayScore == Number) {
    // If actual scores are not yet available, return false or neutral
    return false;
  }
  
  const predictedWinner = game.predictedHomeScore > game.predictedAwayScore ? 'home' : 'away';
  const actualWinner = game.actualHomeScore > game.actualAwayScore ? 'home' : 'away';
  
  return predictedWinner === actualWinner;
}

}



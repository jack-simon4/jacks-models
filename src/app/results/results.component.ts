import { Component, OnInit } from '@angular/core';
import { AngularFirestore } from '@angular/fire/compat/firestore';
import { Observable } from 'rxjs';

@Component({
  selector: 'app-results',
  templateUrl: './results.component.html',
  styleUrls: ['./results.component.css']
})
export class ResultsComponent implements OnInit {

  games: any[] = []; // Array to store retrieved games

  constructor(private firestore: AngularFirestore) { }

  ngOnInit(): void {
    this.loadGames(); // Load games when component initializes
  }

  loadGames() {
   // Listen for changes to the 'games' collection in Firestore
   this.firestore.collection('games', ref => ref.orderBy('timestamp', 'desc')) // Order by timestamp descending
   .snapshotChanges()
   .subscribe(logs => {
     this.games = logs.map(log => {
       const data = log.payload.doc.data() as any;
       data.id = log.payload.doc.id; // Add the document ID
       // Convert Firestore Timestamp to JavaScript Date object
       if (data.timestamp && data.timestamp.seconds) {
        data.timestamp = new Date(data.timestamp.seconds * 1000); // Convert to milliseconds
      }return data;


     });
   });
}

// Function to check if the predicted winner matches the actual winner
isPredictionCorrect(game: any): boolean {
  if (game.actualHomeScore == null || game.actualAwayScore == null) {
    // If actual scores are not yet available, return false or neutral
    return false;
  }
  
  const predictedWinner = game.predictedHomeScore > game.predictedAwayScore ? 'home' : 'away';
  const actualWinner = game.actualHomeScore > game.actualAwayScore ? 'home' : 'away';
  
  return predictedWinner === actualWinner;
}
}

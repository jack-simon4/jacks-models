import { BrowserModule } from '@angular/platform-browser';
import { RouterModule } from '@angular/router';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { AppComponent } from './app.component';
import { RibbonComponent } from './ribbon/ribbon.component'; // Make sure it's imported here
import { ScoreboardComponent } from './scoreboard/scoreboard.component';
import { TeamsComponent } from './teams/teams.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { ScoreboardPopupComponent } from './scoreboard-popup/scoreboard-popup.component';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { AboutComponent } from './about/about.component';
import { AppRoutingModule } from './app-routing.module';
import { ResultsComponent } from './results/results.component';
import { SoccerScoreboardComponent } from './soccer-scoreboard/soccer-scoreboard.component';
import { AngularFireModule } from '@angular/fire/compat';
import { AngularFirestoreModule } from '@angular/fire/compat/firestore';
import { environment } from '../environments/environment';
import { CommonModule } from '@angular/common';






@NgModule({
  declarations: [
    AppComponent,
    RibbonComponent,
    ScoreboardComponent,
    TeamsComponent,
    ScoreboardPopupComponent,
    AboutComponent,
    ResultsComponent,
    SoccerScoreboardComponent,
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    BrowserAnimationsModule,
    MatDialogModule,
    MatInputModule,
    MatSelectModule,
    AppRoutingModule, // Ensure this is here
    MatAutocompleteModule,
    AngularFireModule.initializeApp(environment.firebaseConfig),
    AngularFirestoreModule,
    CommonModule
  ],
  providers: [],
  bootstrap: [AppComponent],
})
export class AppModule { }


